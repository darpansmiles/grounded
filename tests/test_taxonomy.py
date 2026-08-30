from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from evals.error_report import error_report, render_error_report, write_error_report
from evals.runner import run_evals
from evals.taxonomy import LABELS, classify
from evals.trace import read_traces
from scripts.seed_duckdb import seed_database


_GOLDEN_PATH = Path(__file__).resolve().parents[1] / "evals" / "golden.yml"


@pytest.fixture()
def golden_traces(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")
    traces_path = tmp_path / "traces.jsonl"
    run_evals(_GOLDEN_PATH, traces_path)
    return read_traces(traces_path)


def _trace(expected: dict, **overrides) -> dict:
    trace = {
        "case_id": "crafted",
        "expected": expected,
        "outcome": "fail",
        "plan": {"tool": "query_metric"},
        "answer_rows": [{"category": "Electronics", "revenue": 500.0}],
        "policy_applied": [],
        "verify_status": "pass",
        "lineage_citation": "citation",
    }
    trace.update(overrides)
    return trace


def test_real_golden_traces_have_expected_error_analysis(golden_traces):
    report = error_report(golden_traces)

    assert report["label_counts"] == {
        "correct": 7,
        "over_refusal": 1,
        "under_refusal": 0,
        "policy_violation": 0,
        "verification_failure": 0,
        "wrong_number": 0,
        "missing_citation": 0,
        "uncategorized": 0,
    }
    assert report["cases_by_label"]["over_refusal"] == ["paraphrase-known-gap"]
    assert report["known_gap_cases"] == ["paraphrase-known-gap"]
    assert report["real_failures"] == []


@pytest.mark.parametrize(
    ("trace", "label"),
    [
        (_trace({"type": "metric", "rows": []}, outcome="pass"), "correct"),
        (_trace({"type": "refuse"}), "under_refusal"),
        (_trace({"type": "metric", "rows": []}, plan={"tool": "refuse"}), "over_refusal"),
        (
            _trace(
                {
                    "type": "customers",
                    "emails_masked": True,
                    "policy_decision": "mask",
                },
                answer_rows=[{"email": "alice@example.com"}],
                policy_applied=[{"decision": "allow"}],
            ),
            "policy_violation",
        ),
        (_trace({"type": "metric", "rows": []}, verify_status="fail"), "verification_failure"),
        (
            _trace(
                {
                    "type": "metric",
                    "rows": [{"category": "Electronics", "revenue": 500.0}],
                    "policy_applied": [],
                },
                answer_rows=[{"category": "Electronics", "revenue": 499.0}],
            ),
            "wrong_number",
        ),
        (
            _trace(
                {
                    "type": "metric",
                    "rows": [],
                    "policy_applied": [],
                    "citation_present": True,
                },
                lineage_citation=None,
            ),
            "missing_citation",
        ),
    ],
)
def test_classify_crafted_traces_for_each_non_uncategorized_label(trace, label):
    assert classify(deepcopy(trace)) == label


def test_uncategorized_fallback_and_report_rendering(golden_traces, tmp_path):
    uncategorized = _trace({"type": "describe", "citation_present": False})
    assert classify(uncategorized) == "uncategorized"

    report = error_report(golden_traces)
    rendered = render_error_report(report)
    assert all(label in rendered for label in LABELS)

    report_path = tmp_path / "error_analysis.json"
    write_error_report(report, report_path)
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
