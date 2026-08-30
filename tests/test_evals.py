from __future__ import annotations

from pathlib import Path

import pytest

from evals.runner import run_evals
from evals.trace import read_traces
from scripts.seed_duckdb import seed_database


_GOLDEN_PATH = Path(__file__).resolve().parents[1] / "evals" / "golden.yml"


@pytest.fixture()
def evaluation_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")
    traces_path = tmp_path / "traces.jsonl"
    summary = run_evals(_GOLDEN_PATH, traces_path)
    return summary, read_traces(traces_path), traces_path


def test_runner_keeps_known_gap_out_of_health_metric(evaluation_run):
    summary, traces, _ = evaluation_run

    assert summary["total"] == 8
    assert summary["unexpected_failures"] == 0
    assert summary["known_gaps"] == 1
    assert all(
        case["outcome"] == "pass" for case in summary["cases"] if not case["known_gap"]
    )
    gap_trace = next(trace for trace in traces if trace["case_id"] == "paraphrase-known-gap")
    assert gap_trace["outcome"] == "fail"
    assert gap_trace["known_gap"] is True


def test_metric_trace_contains_governed_rows_and_citation(evaluation_run):
    _, traces, _ = evaluation_run

    trace = next(trace for trace in traces if trace["case_id"] == "rev-cat-viewer")
    assert trace["answer_rows"] == [
        {"category": "Electronics", "revenue": 500.0},
        {"category": "Home", "revenue": 405.0},
        {"category": "Books", "revenue": 280.0},
    ]
    assert trace["lineage_citation"]
    assert trace["model"] == "deterministic-planner"
    assert trace["cost_usd"] == 0.0
    assert isinstance(trace["latency_ms"], float)


def test_customer_cases_score_their_masking_and_grant(evaluation_run):
    _, traces, _ = evaluation_run

    masked = next(trace for trace in traces if trace["case_id"] == "customers-masked-viewer")
    unmasked = next(trace for trace in traces if trace["case_id"] == "customers-unmasked-analyst")
    assert masked["outcome"] == "pass"
    assert unmasked["outcome"] == "pass"
    assert {row["email"] for row in masked["answer_rows"]} == {"***@example.com"}
    assert all(not row["email"].startswith("***@") for row in unmasked["answer_rows"])


def test_refusals_pass_without_a_database_tool(evaluation_run):
    _, traces, _ = evaluation_run

    refuses = [trace for trace in traces if trace["expected"]["type"] == "refuse"]
    assert len(refuses) == 2
    assert all(trace["outcome"] == "pass" for trace in refuses)
    assert all(trace["plan"]["tool"] == "refuse" for trace in refuses)
    assert all(trace["answer_rows"] == [] for trace in refuses)


def test_traces_round_trip_and_append(evaluation_run):
    _, traces, traces_path = evaluation_run

    assert len(traces) == 8
    run_evals(_GOLDEN_PATH, traces_path)
    assert len(read_traces(traces_path)) == 16
