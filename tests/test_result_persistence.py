from __future__ import annotations

import json

import pytest
import yaml

from evals.compare import (
    compact_comparison_card,
    render_model_card,
    run_comparison,
    write_failure_exemplars,
)
from evals.scorecard import render_scorecard
from scripts.seed_duckdb import seed_database

_METRIC_CASE = {
    "case_id": "revenue",
    "question": "What was revenue last month by product category?",
    "role": "viewer",
    "expected_plan": {
        "tool": "query_metric",
        "args": {"metric": "revenue", "dimensions": ["category"], "filters": {"order_month": "last_month"}},
    },
    "expect": {"type": "metric"},
}
_REFUSE_CASE = {
    "case_id": "profit",
    "question": "What was our profit margin last month?",
    "role": "viewer",
    "expected_plan": {"tool": "refuse", "args": {}},
    "expect": {"type": "refuse"},
}
_GOVERNED = {
    _METRIC_CASE["question"]: json.dumps(_METRIC_CASE["expected_plan"]),
    _REFUSE_CASE["question"]: json.dumps(_REFUSE_CASE["expected_plan"]),
}
_CORRECT_SQL = """SELECT products.category, CAST(SUM(order_items.quantity * order_items.unit_price) AS DOUBLE) AS revenue
FROM order_items JOIN orders ON order_items.order_id = orders.order_id
JOIN products ON order_items.product_id = products.product_id
WHERE orders.status = 'completed' AND orders.order_ts >= TIMESTAMP '2026-07-01 00:00:00'
AND orders.order_ts < TIMESTAMP '2026-08-01 00:00:00'
GROUP BY products.category ORDER BY revenue DESC, category ASC"""


@pytest.fixture()
def comparison_inputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")
    golden_path = tmp_path / "golden.yml"
    golden_path.write_text(yaml.safe_dump([_METRIC_CASE, _REFUSE_CASE]), encoding="utf-8")
    return golden_path, tmp_path / "grounded.duckdb"


def test_compare_rejects_the_retired_constructed_answer_quality_path():
    with pytest.raises(RuntimeError, match="retired"):
        run_comparison()


def test_percentage_rendering_changes_display_not_scorecard_math():
    scorecard = {
        "model": "stub",
        "counts": {"total_cases": 3},
        "quality": {"correctness_rate_incl_gaps": 2 / 3},
        "operational": {"latency_ms": {"p50": 12.3, "p95": 45.6, "max": 45.6}, "cost_usd": {"total": 0.0, "mean": 0.0}},
        "known_gap_cases": [],
    }
    card = {
        "models": ["stub"],
        "model_cards": {
            "stub": {
                "status": "completed",
                "governed": {"hallucination_rate": 0.0},
                "ungoverned": {"hallucination_rate": 0.5},
            }
        },
    }

    assert "66.7%" in render_scorecard(scorecard)
    assert "latency_ms.p50 | 12.3" in render_scorecard(scorecard)
    assert "| hallucination_rate | 0.0% | 50.0% |" in render_model_card(card)


def test_compact_card_caps_raw_exemplars_without_changing_aggregates_or_failure_proof(tmp_path):
    raw_output = "SELECT invented_column FROM orders\n" + ("x" * 250_000)
    error = "Referenced column invented_column was not found" + ("e" * 1_000)
    governed_samples = [
        {
            "case_id": f"governed-{number}",
            "run": 1,
            "label": "over_refusal",
            "raw_model_output": raw_output,
        }
        for number in range(8)
    ]
    ungoverned_samples = [
        {
            "case_id": f"ungoverned-{number}",
            "run": 1,
            "label": "schema_break",
            "result": {
                "raw_sql": raw_output,
                "error": error,
                "rejection_reason": error,
            },
        }
        for number in range(8)
    ]
    card = {
        "models": ["stub"],
        "model_cards": {
            "stub": {
                "status": "completed",
                "governed": {"hallucination_rate": 0.0, "over_refusal_rate": 1.0},
                "ungoverned": {"hallucination_rate": 0.0, "schema_break_rate": 1.0},
                "statistics": {"mcnemar_exact": {"hallucination": {"p_value": 1.0}}},
                "governed_samples": governed_samples,
                "samples": ungoverned_samples,
            }
        },
    }
    questions = {
        **{sample["case_id"]: "Governed failure question" for sample in governed_samples},
        **{sample["case_id"]: "Ungoverned failure question" for sample in ungoverned_samples},
    }

    compacted = compact_comparison_card(card, questions)
    compact_model = compacted["model_cards"]["stub"]
    failures_path = tmp_path / "benchmark-fixture-stub-failures.md"
    write_failure_exemplars(card, failures_path, dataset="fixture", questions=questions)

    assert compact_model["governed"] == card["model_cards"]["stub"]["governed"]
    assert compact_model["ungoverned"] == card["model_cards"]["stub"]["ungoverned"]
    assert compact_model["statistics"] == card["model_cards"]["stub"]["statistics"]
    assert "governed_samples" not in compact_model
    assert "samples" not in compact_model
    assert len(compact_model["exemplars"]["governed"]) == 5
    assert len(compact_model["exemplars"]["ungoverned"]) == 5
    exemplar = compact_model["exemplars"]["ungoverned"][0]
    assert exemplar["raw_model_output"].endswith("… [truncated: kept 2000 of 250035 chars]")
    assert exemplar["error"].endswith("… [truncated: kept 500 of 1047 chars]")
    assert len(json.dumps(compacted)) < 50 * 1024 * 1024
    assert len(json.dumps(compacted)) < len(json.dumps(card)) * 0.01
    failures = failures_path.read_text(encoding="utf-8")
    assert "## schema_break" in failures
    assert "SELECT invented_column FROM orders" in failures
    assert "… [truncated: kept 500 of 1047 chars]" in failures
