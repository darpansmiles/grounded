from __future__ import annotations

import ast
import inspect
import json

import pytest

from evals import offline_scoring
from evals.offline_scoring import (
    _METRIC_TOLERANCES,
    _aliases_for_metric,
    captured_rows_match,
    evaluator_self_test,
    independent_rows,
    rows_content_hash,
    rows_match,
    score_capture_files,
    score_record,
)
from scripts.seed_duckdb import seed_database


def _metric_record() -> dict:
    plan = {
        "tool": "query_metric",
        "args": {
            "metric": "revenue",
            "dimensions": [],
            "filters": {"order_month": "last_month"},
        },
    }
    return {
        "record_type": "case",
        "case_id": "rev-total-lastmonth",
        "model": "stub",
        "run": 1,
        "category": "total",
        "role": "viewer",
        "expect": {"type": "metric"},
        "expected_plan": plan,
        "produced_plan": plan,
        "schema_valid": True,
        "governed_executed": True,
        "governed_rows": [{"revenue": 1185.0}],
        "policy_decisions": [],
        "evidence": {
            "metric_definition": {"measure": "sum"},
            "lineage_citation": "revenue ← fixture lineage",
            "verification": [],
            "verify_status": "pass",
        },
        "ungoverned": {
            "raw_sql": "```sql\nSELECT 1185 AS revenue\n```",
            "rows": [{"revenue": 1185.0}],
            "schema_break": False,
        },
    }


def test_independent_truth_is_direct_sql_not_the_resolver(tmp_path):
    database = tmp_path / "fixture.duckdb"
    seed_database(str(database))

    rows = independent_rows(
        "fixture", _metric_record()["expected_plan"], "viewer", db_path=database
    )

    assert rows == [{"revenue": 1185}]
    tree = ast.parse(inspect.getsource(offline_scoring))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(name.startswith(("governed", "resolver")) for name in imported_modules)


def test_rows_match_preserves_duplicates_and_ignores_row_order():
    expected = [{"revenue": 1}, {"revenue": 2}]
    assert rows_match([{"revenue": 2}, {"revenue": 1}], expected)
    assert not rows_match([{"revenue": 1}, {"revenue": 1}], expected)


def test_rows_match_only_accepts_declared_metric_aliases():
    expected = [{"revenue": 1185}]

    assert rows_match(
        [{"total_revenue": 1185}],
        expected,
        alias_map=_aliases_for_metric("revenue"),
        metric="revenue",
    )
    assert not rows_match(
        [{"made_up_revenue": 1185}],
        expected,
        alias_map=_aliases_for_metric("revenue"),
        metric="revenue",
    )


def test_rows_match_distinguishes_null_zero_and_empty_result():
    assert rows_match([], [], metric="revenue")
    assert not rows_match(None, [])
    assert not rows_match([], [{"revenue": None}], metric="revenue")
    assert not rows_match([{"revenue": None}], [{"revenue": 0}], metric="revenue")
    assert not rows_match([{"revenue": 0}], [{"revenue": ""}], metric="revenue")


def test_compact_capture_hash_preserves_full_multiset_comparison():
    expected = [{"revenue": 1}, {"revenue": 2}, {"revenue": 2}]
    preview = expected[:1]
    assert captured_rows_match(
        preview,
        expected,
        row_count=3,
        content_hash=rows_content_hash(expected, alias_map=_aliases_for_metric("revenue")),
        alias_map=_aliases_for_metric("revenue"),
        metric="revenue",
    )
    assert not captured_rows_match(
        preview,
        expected,
        row_count=2,
        content_hash=rows_content_hash(expected, alias_map=_aliases_for_metric("revenue")),
        alias_map=_aliases_for_metric("revenue"),
        metric="revenue",
    )


def test_offline_score_uses_compact_capture_metadata_for_both_arms(tmp_path):
    database = tmp_path / "fixture.duckdb"
    seed_database(str(database))
    record = _metric_record()
    rows = [{"revenue": 1185.0}]
    row_hash = rows_content_hash(rows, alias_map=_aliases_for_metric("revenue"))
    record["governed_rows"] = rows[:1]
    record["governed_row_count"] = len(rows)
    record["governed_rows_hash"] = row_hash
    record["ungoverned"]["rows"] = [{"total_revenue": 1185.0}]
    record["ungoverned"]["row_count"] = len(rows)
    record["ungoverned"]["rows_hash"] = row_hash

    sample = score_record(record, dataset="fixture", db_path=database)

    assert sample["governed"]["answer_correctness"] == "correct"
    assert sample["ungoverned"]["answer_correctness"] == "correct"


def test_metric_tolerances_are_declared_per_metric_and_not_a_global_cushion():
    assert {"revenue", "orders", "aov"} <= set(_METRIC_TOLERANCES)
    assert _METRIC_TOLERANCES["revenue"] == 0
    assert _METRIC_TOLERANCES["orders"] == 0
    assert _METRIC_TOLERANCES["aov"] == 0
    assert rows_match([{"revenue": 1.00}], [{"revenue": 1}], metric="revenue")
    assert not rows_match([{"revenue": 1.01}], [{"revenue": 1}], metric="revenue")


def test_offline_score_uses_symmetric_fenced_sql_extraction(tmp_path):
    database = tmp_path / "fixture.duckdb"
    seed_database(str(database))
    record = _metric_record()
    record["ungoverned"]["raw_sql"] = "```sql\nSELECT 1185 AS total_revenue\n```"
    record["ungoverned"]["rows"] = [{"total_revenue": 1185.0}]
    capture = tmp_path / "capture.jsonl"
    capture.write_text(
        "\n".join(
            [
                json.dumps({"record_type": "manifest", "dataset": "fixture"}),
                json.dumps(record),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = score_capture_files([capture], db_path=database)
    sample = report["models"]["stub"]["samples"][0]

    assert report["evaluator_self_test"]["passed"] is True
    assert sample["governed"]["answer_correctness"] == "correct"
    assert sample["ungoverned"]["answer_correctness"] == "correct"
    assert sample["ungoverned"]["interface_compliance"] == "compliant"
    rate = report["models"]["stub"]["groups"]["in_catalog"]["governed"]["answer_correctness_when_answered"]
    assert rate == {"numerator": 1, "denominator": 1, "rate": 1.0}


def test_offline_score_streams_jsonl_without_calling_path_read_text(tmp_path, monkeypatch):
    database = tmp_path / "fixture.duckdb"
    seed_database(str(database))
    capture = tmp_path / "capture.jsonl"
    capture.write_text(
        "\n".join(
            [
                json.dumps({"record_type": "manifest", "dataset": "fixture"}),
                json.dumps(_metric_record()),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "evals.offline_scoring.Path.read_text",
        lambda *_args, **_kwargs: pytest.fail("capture scoring must stream files"),
    )

    report = score_capture_files([capture], db_path=database)

    assert report["dataset"] == "fixture"
    assert report["models"]["stub"]["samples"][0]["expected_row_count"] == 1
    assert "expected_rows" not in report["models"]["stub"]["samples"][0]


def test_offline_score_marks_a_valid_but_wrong_call_wrong_and_missing_evidence_incomplete(
    tmp_path,
):
    database = tmp_path / "fixture.duckdb"
    seed_database(str(database))
    record = _metric_record()
    record["governed_rows"] = [{"revenue": 1635.0}]
    record["evidence"] = None

    sample = score_record(record, dataset="fixture", db_path=database)

    assert sample["governed"]["answer_correctness"] == "wrong"
    assert sample["governed"]["summary_label"] == "wrong_answer"
    assert sample["governed"]["evidence_completeness"] == "incomplete"


def test_evaluator_self_test_catches_every_required_seeded_failure():
    assert evaluator_self_test() == {
        "wrong_metric": True,
        "wrong_period": True,
        "duplicate_result": True,
        "missing_evidence": True,
        "forbidden_scope": True,
    }


def test_offline_scoring_refuses_to_produce_a_report_if_the_self_test_fails(
    tmp_path, monkeypatch
):
    capture = tmp_path / "capture.jsonl"
    capture.write_text(
        json.dumps({"record_type": "manifest", "dataset": "fixture"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        offline_scoring,
        "evaluator_self_test",
        lambda: {
            "wrong_metric": True,
            "wrong_period": True,
            "duplicate_result": False,
            "missing_evidence": True,
            "forbidden_scope": True,
        },
    )

    with pytest.raises(RuntimeError, match="Evaluator self-test failed"):
        score_capture_files([capture])


def test_offline_card_is_not_valid_when_independent_truth_is_unavailable(tmp_path):
    record = _metric_record()
    record["expected_plan"] = {
        "tool": "query_metric",
        "args": {"metric": "not_declared", "dimensions": [], "filters": {}},
    }
    capture = tmp_path / "capture.jsonl"
    capture.write_text(
        "\n".join(
            [
                json.dumps({"record_type": "manifest", "dataset": "fixture"}),
                json.dumps(record),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = score_capture_files([capture], db_path=tmp_path / "missing.duckdb")

    assert report["evaluator_self_test"]["passed"] is True
    assert report["models"]["stub"]["valid"] is False
