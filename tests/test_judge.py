from __future__ import annotations

import json

import pytest
import yaml

from evals.compare import run_comparison
from evals.judge import (
    StubJudge,
    faithfulness_rate,
    judge_agreement,
    judge_faithfulness,
)
from models.provider import StubProvider
from scripts.seed_duckdb import seed_database

_CORRECT_SQL = """
SELECT products.category, CAST(SUM(order_items.quantity * order_items.unit_price) AS DOUBLE) AS revenue
FROM order_items
JOIN orders ON order_items.order_id = orders.order_id
JOIN products ON order_items.product_id = products.product_id
WHERE orders.status = 'completed'
  AND orders.order_ts >= TIMESTAMP '2026-07-01 00:00:00'
  AND orders.order_ts < TIMESTAMP '2026-08-01 00:00:00'
GROUP BY products.category
ORDER BY revenue DESC, category ASC
"""


def _metric_case() -> dict:
    return {
        "case_id": "rev-cat-canonical",
        "question": "What was revenue last month by product category?",
        "role": "viewer",
        "expected_plan": {
            "tool": "query_metric",
            "args": {"metric": "revenue", "dimensions": ["category"], "filters": {"order_month": "last_month"}},
        },
        "expect": {"type": "metric"},
    }


def _refuse_case() -> dict:
    return {
        "case_id": "adv-profit-margin",
        "question": "What was our profit margin last month?",
        "role": "viewer",
        "expected_plan": {"tool": "refuse", "args": {}},
        "expect": {"type": "refuse"},
    }


def test_judge_returns_a_faithful_stub_verdict():
    verdict = judge_faithfulness(
        "What was revenue?",
        '{"revenue": 500}',
        '{"revenue": 500}',
        StubJudge({'"revenue": 500': {"faithful": True, "reason": "matches the result"}}),
    )

    assert verdict == {"faithful": True, "reason": "matches the result"}


def test_judge_returns_a_fabrication_verdict():
    verdict = judge_faithfulness(
        "What was revenue?",
        '{"revenue": 999}',
        '{"revenue": 500}',
        StubJudge({'"revenue": 999': {"faithful": False, "reason": "999 is unsupported"}}),
    )

    assert verdict == {"faithful": False, "reason": "999 is unsupported"}


def test_judge_fails_closed_on_unparseable_output():
    verdict = judge_faithfulness(
        "What was revenue?", '{"revenue": 500}', '{"revenue": 500}', StubJudge({})
    )

    assert verdict == {"faithful": False, "reason": "unparseable judge output"}


def test_faithfulness_rate_over_mixed_items():
    items = [
        {"question": "one", "answer": "faithful answer", "grounded_context": "context"},
        {"question": "two", "answer": "fabricated answer", "grounded_context": "context"},
    ]

    rate = faithfulness_rate(
        items,
        StubJudge(
            {
                "faithful answer": {"faithful": True, "reason": "supported"},
                "fabricated answer": {"faithful": False, "reason": "unsupported"},
            }
        ),
    )

    assert rate == 0.5


def test_judge_agreement_reports_stubbed_hand_label_accuracy():
    labels = [
        {"case_id": "one", "pack": "fixture", "question": "one", "answer": "supported", "ground_truth": "yes", "faithful": True, "note": ""},
        {"case_id": "two", "pack": "fixture", "question": "two", "answer": "invented", "ground_truth": "no", "faithful": False, "note": ""},
    ]

    agreement = judge_agreement(
        labels,
        StubJudge({"supported": {"faithful": True, "reason": "match"}, "invented": {"faithful": False, "reason": "unsupported"}}),
    )

    assert agreement["labeled_cases"] == 2
    assert agreement["agreement_rate"] == 1.0


@pytest.fixture()
def seeded_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")
    return tmp_path / "grounded.duckdb"


def _providers():
    def governed_provider_factory(_model: str):
        return StubProvider(
            {
                _metric_case()["question"]: '{"tool":"query_metric","args":{"metric":"revenue","dimensions":["category"],"filters":{"order_month":"last_month"}}}',
                _refuse_case()["question"]: '{"tool":"refuse","args":{}}',
            }
        )

    def ungoverned_provider_factory(_model: str):
        return StubProvider(
            {
                _metric_case()["question"]: _CORRECT_SQL,
                _refuse_case()["question"]: "SELECT 42 AS profit_margin",
            }
        )

    return governed_provider_factory, ungoverned_provider_factory


def test_compare_omits_faithfulness_when_no_judge_is_supplied(seeded_database, tmp_path):
    golden_path = tmp_path / "golden.yml"
    golden_path.write_text(yaml.safe_dump([_metric_case(), _refuse_case()]), encoding="utf-8")
    governed_provider_factory, ungoverned_provider_factory = _providers()

    card = run_comparison(
        ["stub"],
        golden=golden_path,
        governed_provider_factory=governed_provider_factory,
        ungoverned_provider_factory=ungoverned_provider_factory,
        db_path=str(seeded_database),
        output_path=tmp_path / "model_card.json",
    )

    assert "faithfulness_rate" not in card["model_cards"]["stub"]["governed"]
    assert "faithfulness_rate" not in card["model_cards"]["stub"]["ungoverned"]


def test_compare_adds_governed_and_ungoverned_faithfulness(seeded_database, tmp_path):
    golden_path = tmp_path / "golden.yml"
    golden_path.write_text(yaml.safe_dump([_metric_case(), _refuse_case()]), encoding="utf-8")
    governed_provider_factory, ungoverned_provider_factory = _providers()
    judge = StubJudge(
        {
            '"rows": [{"category": "Electronics"': {"faithful": True, "reason": "grounded rows"},
            '"refusal": "No governed answer was produced."': {"faithful": True, "reason": "safe refusal"},
            "profit_margin": {"faithful": False, "reason": "unsupported metric"},
        }
    )

    card = run_comparison(
        ["stub"],
        golden=golden_path,
        governed_provider_factory=governed_provider_factory,
        ungoverned_provider_factory=ungoverned_provider_factory,
        judge_provider=judge,
        db_path=str(seeded_database),
        output_path=tmp_path / "model_card.json",
    )

    model_card = card["model_cards"]["stub"]
    assert model_card["governed"]["faithfulness_rate"] == 1.0
    assert model_card["ungoverned"]["faithfulness_rate"] == 0.5
    persisted = json.loads((tmp_path / "model_card.json").read_text(encoding="utf-8"))
    assert persisted["model_cards"]["stub"]["governed"]["faithfulness_rate"] == 1.0
    assert persisted["model_cards"]["stub"]["ungoverned"]["faithfulness_rate"] == 0.5
    assert "governed_samples" not in persisted["model_cards"]["stub"]
