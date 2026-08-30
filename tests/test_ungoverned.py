from __future__ import annotations

import json

import duckdb
import pytest
import yaml

from agent.ungoverned import answer_ungoverned
from evals.compare import render_model_card, run_comparison, ungoverned_correct
from evals.ground_truth import ground_truth_for_case
from models.provider import ProviderUnavailable, StubProvider
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
_WRONG_SQL = """
SELECT products.category, CAST(SUM(order_items.quantity * order_items.unit_price) AS DOUBLE) AS revenue
FROM order_items
JOIN orders ON order_items.order_id = orders.order_id
JOIN products ON order_items.product_id = products.product_id
WHERE orders.status = 'completed'
GROUP BY products.category
"""


class RepairingProvider:
    """Returns a bad query once, then a repaired query after error feedback."""

    def __init__(self, bad_sql: str, repaired_sql: str) -> None:
        self.bad_sql = bad_sql
        self.repaired_sql = repaired_sql
        self.prompts: list[str] = []

    def complete(self, system: str, _question: str) -> str:
        self.prompts.append(system)
        return self.repaired_sql if len(self.prompts) > 1 else self.bad_sql


@pytest.fixture()
def seeded_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")
    return tmp_path / "grounded.duckdb"


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


def test_ground_truth_uses_the_governed_metric_path(seeded_database):
    truth = ground_truth_for_case(_metric_case(), str(seeded_database))

    assert truth == {
        "type": "metric",
        "rows": [
            {"category": "Electronics", "revenue": 500.0},
            {"category": "Home", "revenue": 405.0},
            {"category": "Books", "revenue": 280.0},
        ],
    }


def test_ungoverned_select_can_match_governed_truth(seeded_database):
    result = answer_ungoverned(
        _metric_case()["question"], StubProvider({_metric_case()["question"]: _CORRECT_SQL}), str(seeded_database)
    )

    assert ungoverned_correct(result, ground_truth_for_case(_metric_case(), str(seeded_database)))


def test_wrong_number_sql_is_incorrect_and_a_hallucination_in_the_card(seeded_database, tmp_path):
    golden_path = tmp_path / "golden.yml"
    golden_path.write_text(yaml.safe_dump([_metric_case(), _refuse_case()]), encoding="utf-8")

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
                _metric_case()["question"]: _WRONG_SQL,
                _refuse_case()["question"]: "SELECT 42 AS profit_margin",
            }
        )

    card = run_comparison(
        ["stub"],
        runs=1,
        golden=golden_path,
        governed_provider_factory=governed_provider_factory,
        ungoverned_provider_factory=ungoverned_provider_factory,
        db_path=str(seeded_database),
        output_path=tmp_path / "model_card.json",
    )

    ungoverned = card["model_cards"]["stub"]["ungoverned"]
    assert ungoverned["correct_answer_rate"] == 0.0
    assert ungoverned["hallucination_rate"] > 0


def test_non_select_is_never_executed_and_leaves_tables_intact(seeded_database):
    result = answer_ungoverned("Delete orders", StubProvider({"Delete orders": "DROP TABLE orders"}), str(seeded_database))

    assert result["schema_break"] is True
    connection = duckdb.connect(str(seeded_database), read_only=True)
    try:
        assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 8
    finally:
        connection.close()


def test_ungoverned_retries_execution_errors_and_captures_steelman_metadata(seeded_database):
    provider = RepairingProvider("SELECT missing_column FROM orders", "SELECT COUNT(*) AS orders FROM orders")

    result = answer_ungoverned("Count orders", provider, str(seeded_database))

    assert result["rows"] == [{"orders": 8}]
    assert result["attempts"] == 2
    assert result["execution_success"] is True
    assert "Previous SQL failed with:" in provider.prompts[1]


def test_ungoverned_buckets_unrepaired_fabricated_columns(seeded_database):
    result = answer_ungoverned(
        "Broken", StubProvider({"Broken": "SELECT made_up FROM orders"}), str(seeded_database)
    )

    assert result["attempts"] == 2
    assert result["execution_success"] is False
    assert result["failure_reason"] == "wrong_column"


def test_governed_misrouting_is_an_over_refusal_not_a_hallucination(seeded_database, tmp_path):
    golden_path = tmp_path / "golden.yml"
    golden_path.write_text(yaml.safe_dump([_metric_case(), _refuse_case()]), encoding="utf-8")

    def governed_provider_factory(_model: str):
        return StubProvider(
            {
                _metric_case()["question"]: "not JSON",
                _refuse_case()["question"]: '{"tool":"refuse","args":{}}',
            }
        )

    def ungoverned_provider_factory(_model: str):
        return StubProvider(
            {
                _metric_case()["question"]: _CORRECT_SQL,
                _refuse_case()["question"]: "I can't answer that.",
            }
        )

    card = run_comparison(
        ["stub"],
        golden=golden_path,
        governed_provider_factory=governed_provider_factory,
        ungoverned_provider_factory=ungoverned_provider_factory,
        db_path=str(seeded_database),
        output_path=tmp_path / "model_card.json",
    )

    governed = card["model_cards"]["stub"]["governed"]
    ungoverned = card["model_cards"]["stub"]["ungoverned"]
    assert governed["hallucination_rate"] == 0.0
    assert governed["over_refusal_rate"] == 0.5
    assert governed["answer_correctness_when_answered"] == 1.0
    assert ungoverned["correct_refusal_rate"] == 0.5


def test_comparison_builds_round_trippable_governed_vs_ungoverned_card(seeded_database, tmp_path):
    golden_path = tmp_path / "golden.yml"
    output_path = tmp_path / "model_card.json"
    golden_path.write_text(yaml.safe_dump([_metric_case(), _refuse_case()]), encoding="utf-8")

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
                _refuse_case()["question"]: "DROP TABLE orders",
            }
        )

    card = run_comparison(
        ["stub"],
        runs=2,
        golden=golden_path,
        governed_provider_factory=governed_provider_factory,
        ungoverned_provider_factory=ungoverned_provider_factory,
        db_path=str(seeded_database),
        output_path=output_path,
    )

    model_card = card["model_cards"]["stub"]
    assert model_card["governed"]["answer_correctness_when_answered"] == 1.0
    assert model_card["governed"]["correct_refusal_rate"] == 0.5
    assert model_card["governed"]["hallucination_rate"] == 0.0
    assert model_card["ungoverned"]["schema_break_rate"] > 0
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["model_cards"]["stub"]["governed"] == model_card["governed"]
    assert persisted["model_cards"]["stub"]["ungoverned"] == model_card["ungoverned"]
    assert "governed_samples" not in persisted["model_cards"]["stub"]
    assert "samples" not in persisted["model_cards"]["stub"]
    assert len(persisted["model_cards"]["stub"]["exemplars"]["ungoverned"]) == 4
    assert "stub · governed" in render_model_card(card)


def test_comparison_persists_request_error_skip_reason(seeded_database, tmp_path):
    golden_path = tmp_path / "golden.yml"
    output_path = tmp_path / "model_card.json"
    golden_path.write_text(yaml.safe_dump([_metric_case(), _refuse_case()]), encoding="utf-8")

    def unavailable(_model: str):
        raise ProviderUnavailable("Ollama request failed: model requires more system memory")

    card = run_comparison(
        ["oom-model"],
        golden=golden_path,
        governed_provider_factory=unavailable,
        db_path=str(seeded_database),
        output_path=output_path,
    )

    model_card = card["model_cards"]["oom-model"]
    assert model_card["skip_reason"] == "request_error"
    assert "skipped (request_error: Ollama request failed" in render_model_card(card)
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["model_cards"]["oom-model"]["skip_reason"] == "request_error"
