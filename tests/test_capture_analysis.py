from __future__ import annotations

import json

from evals.capture_analysis import analyze_capture, classify_ungoverned_record
from scripts.seed_duckdb import seed_database


def _record(**ungoverned):
    return {
        "record_type": "case",
        "case_id": "revenue-total",
        "model": "stub",
        "run": 1,
        "role": "viewer",
        "expect": {"type": "metric"},
        "expected_plan": {
            "tool": "query_metric",
            "args": {
                "metric": "revenue",
                "dimensions": [],
                "filters": {"order_month": "last_month"},
            },
        },
        "ungoverned": ungoverned,
    }


def test_capture_analysis_classifies_fence_and_schema_failures_without_a_database():
    fenced = _record(
        raw_sql="```sql\nSELECT 1185 AS revenue\n```",
        error="only one SELECT statement is allowed",
        failure_reason="unsafe_or_nonselect_sql",
    )
    schema = _record(
        raw_sql="SELECT made_up_revenue FROM gold.fct_lineitem",
        error='Binder Error: Referenced column "made_up_revenue" not found',
        failure_reason="wrong_column",
    )

    assert classify_ungoverned_record(fenced, dataset="tpch") == "fenced_rejection"
    assert classify_ungoverned_record(schema, dataset="tpch") == "schema_hallucination"


def test_capture_analysis_detects_a_documented_alias_comparison_artifact(tmp_path):
    database = tmp_path / "fixture.duckdb"
    seed_database(str(database))
    alias = _record(
        raw_sql="SELECT 1185 AS total_revenue",
        rows=[{"total_revenue": 1185.0}],
        error=None,
        failure_reason=None,
    )

    assert (
        classify_ungoverned_record(alias, dataset="fixture", db_path=database)
        == "alias_mismatch"
    )


def test_capture_analysis_streams_jsonl_and_reports_review_only_buckets(tmp_path, monkeypatch):
    capture = tmp_path / "capture.jsonl"
    fenced = _record(
        raw_sql="```sql\nSELECT 1185 AS revenue\n```",
        error="only one SELECT statement is allowed",
        failure_reason="unsafe_or_nonselect_sql",
    )
    capture.write_text(
        "\n".join(
            [
                json.dumps({"record_type": "manifest", "dataset": "fixture"}),
                json.dumps(fenced),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "evals.capture_analysis.Path.read_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("capture analysis must stream files")
        ),
    )

    report = analyze_capture(capture)

    assert report["classification"] == "post_collection_diagnostic_not_a_benchmark_score"
    assert report["counts"] == {"fenced_rejection": 1}
    assert report["samples"][0]["case_id"] == "revenue-total"
