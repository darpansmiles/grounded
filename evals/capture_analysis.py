"""Classify raw-SQL control failures from an existing capture JSONL file.

This is deliberately post-collection analysis.  It does not call a model, the
governed service, Cube, or the resolver.  Where a local DuckDB path is supplied,
it uses the independent scorer only to distinguish a column-alias comparison
artifact from a genuinely different row set.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evals.offline_scoring import (
    TruthUnavailable,
    _aliases_for_metric,
    independent_rows,
    rows_match,
)

_SCHEMA_FAILURE_MARKERS = (
    "binder error",
    "catalog error",
    "referenced column",
    "column",
    "table",
    "does not exist",
    "no such",
    "join",
)


def _ungoverned(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("ungoverned")
    return value if isinstance(value, dict) else {}


def _raw_sql(record: dict[str, Any]) -> str:
    raw = _ungoverned(record)
    candidate = raw.get("raw_sql") or record.get("ungoverned_sql") or raw.get("sql") or ""
    return candidate if isinstance(candidate, str) else ""


def _error(record: dict[str, Any]) -> str:
    raw = _ungoverned(record)
    candidate = (
        raw.get("error")
        or raw.get("rejection_reason")
        or record.get("ungoverned_error")
        or ""
    )
    return candidate if isinstance(candidate, str) else ""


def _rows(record: dict[str, Any]) -> list[dict[str, Any]] | None:
    raw = _ungoverned(record)
    candidate = raw.get("rows") if raw else record.get("ungoverned_rows")
    return candidate if isinstance(candidate, list) else None


def _is_fenced_rejection(record: dict[str, Any]) -> bool:
    return (
        _raw_sql(record).strip().startswith("```")
        and "only one select statement" in _error(record).casefold()
    )


def _is_schema_hallucination(record: dict[str, Any]) -> bool:
    raw = _ungoverned(record)
    reason = raw.get("failure_reason")
    if reason in {"wrong_column", "wrong_table", "wrong_join"}:
        return True
    error = _error(record).casefold()
    return bool(error) and any(marker in error for marker in _SCHEMA_FAILURE_MARKERS)


def _comparison_detail(
    actual: list[dict[str, Any]] | None, expected: list[dict[str, Any]]
) -> dict[str, Any]:
    """Keep enough mismatch context for a reviewer without dumping a capture."""
    return {
        "expected_row_count": len(expected),
        "actual_row_count": len(actual) if actual is not None else None,
        "expected_preview": expected[:3],
        "actual_preview": actual[:3] if actual is not None else None,
    }


def _is_alias_mismatch(
    record: dict[str, Any], dataset: str, db_path: str | Path | None
) -> bool:
    """Find equivalent values whose only disagreement is a documented alias."""
    if record.get("expect", {}).get("type") != "metric":
        return False
    actual = _rows(record)
    plan = record.get("expected_plan")
    if not isinstance(plan, dict) or actual is None:
        return False
    metric = plan.get("args", {}).get("metric")
    if not isinstance(metric, str):
        return False
    try:
        expected = independent_rows(dataset, plan, str(record.get("role", "")), db_path=db_path)
    except TruthUnavailable:
        return False
    return not rows_match(actual, expected, metric=metric) and rows_match(
        actual,
        expected,
        alias_map=_aliases_for_metric(metric),
        metric=metric,
    )


def diagnose_ungoverned_record(
    record: dict[str, Any], *, dataset: str, db_path: str | Path | None = None
) -> tuple[str, dict[str, Any]]:
    """Return one mutually exclusive diagnosis and reviewable mismatch details."""
    if _is_fenced_rejection(record):
        return "fenced_rejection", {}
    if _is_schema_hallucination(record):
        return "schema_hallucination", {}
    if _error(record):
        return "other_failure", {}
    if record.get("expect", {}).get("type") != "metric":
        return "not_a_failure", {}
    actual = _rows(record)
    plan = record.get("expected_plan")
    if not isinstance(plan, dict) or actual is None:
        return "unclassified", {}
    metric = plan.get("args", {}).get("metric")
    if not isinstance(metric, str):
        return "unclassified", {}
    try:
        expected = independent_rows(dataset, plan, str(record.get("role", "")), db_path=db_path)
    except TruthUnavailable as exc:
        return "unclassified", {"truth_error": str(exc)}
    aliases = _aliases_for_metric(metric)
    if rows_match(actual, expected, alias_map=aliases, metric=metric):
        if _is_alias_mismatch(record, dataset, db_path):
            return "correct_but_rounding_or_shape", {
                "mismatch_kind": "documented_alias",
                **_comparison_detail(actual, expected),
            }
        return "not_a_failure", {}
    sql = _raw_sql(record).casefold()
    filters = plan.get("args", {}).get("filters", {})
    if filters and not any(token in sql for token in ("date", "month", "year", "2026", "2025")):
        bucket = "wrong_business_definition_filter_period"
    elif any(token in sql for token in (" join ", "sum(", "avg(", "count(", "group by")):
        bucket = "incorrect_aggregation_or_join"
    else:
        bucket = "unclassified"
    return bucket, _comparison_detail(actual, expected)


def classify_ungoverned_record(
    record: dict[str, Any], *, dataset: str, db_path: str | Path | None = None
) -> str:
    """Compatibility wrapper returning only the primary diagnostic bucket."""
    return diagnose_ungoverned_record(record, dataset=dataset, db_path=db_path)[0]


def analyze_capture(
    capture_path: str | Path,
    *,
    db_path: str | Path | None = None,
    sample_limit: int = 20,
    max_records: int | None = None,
) -> dict[str, Any]:
    """Read one capture JSONL and return review-only diagnostics by failure bucket."""
    manifest: dict[str, Any] | None = None
    samples: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    processed = 0
    with Path(capture_path).open(encoding="utf-8") as capture_file:
        for line in capture_file:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("record_type") == "manifest":
                manifest = item
            elif item.get("record_type") == "case":
                if not isinstance(manifest, dict) or not isinstance(
                    manifest.get("dataset"), str
                ):
                    raise TypeError("Capture manifest must precede case records.")
                dataset = manifest["dataset"]
                processed += 1
                bucket, mismatch = diagnose_ungoverned_record(item, dataset=dataset, db_path=db_path)
                counts[bucket] += 1
                if len(samples) < sample_limit and bucket != "not_a_failure":
                    samples.append(
                    {
                        "case_id": item.get("case_id"),
                        "model": item.get("model"),
                        "run": item.get("run"),
                        "bucket": bucket,
                        "failure_reason": _ungoverned(item).get("failure_reason"),
                        "error": _error(item) or None,
                        "sql": _raw_sql(item) or None,
                        "mismatch": mismatch or None,
                    }
                )
                if max_records is not None and processed >= max_records:
                    break
    if not isinstance(manifest, dict) or not isinstance(manifest.get("dataset"), str):
        raise TypeError("Capture analysis requires one manifest with a dataset.")
    dataset = manifest["dataset"]
    return {
        "dataset": dataset,
        "source": "captured_jsonl",
        "classification": "post_collection_diagnostic_not_a_benchmark_score",
        "counts": dict(sorted(counts.items())),
        "samples": samples,
        "processed_records": processed,
        "complete": max_records is None or processed < max_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify raw-SQL failures in an existing benchmark capture."
    )
    parser.add_argument("--capture-path", required=True, help="Existing capture JSONL to inspect.")
    parser.add_argument(
        "--db-path",
        help="Optional local DuckDB file for alias-mismatch checks; read-only and no services required.",
    )
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Bound a review sample without claiming whole-capture counts.",
    )
    arguments = parser.parse_args()
    print(
        json.dumps(
            analyze_capture(
                arguments.capture_path,
                db_path=arguments.db_path,
                sample_limit=arguments.sample_limit,
                max_records=arguments.max_records,
            ),
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
