"""Aggregate taxonomy labels into a persisted evaluation error-analysis report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.runner import run_evals
from evals.taxonomy import LABELS, classify
from evals.trace import read_traces


def error_report(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Count taxonomy labels and separate real failures from known gaps."""
    cases_by_label = {label: [] for label in LABELS}
    known_gap_cases: list[str] = []
    real_failures: list[str] = []
    for trace in traces:
        label = classify(trace)
        case_id = trace["case_id"]
        cases_by_label[label].append(case_id)
        if trace.get("known_gap", False):
            known_gap_cases.append(case_id)
        if label != "correct" and not trace.get("known_gap", False):
            real_failures.append(case_id)
    return {
        "label_counts": {label: len(cases_by_label[label]) for label in LABELS},
        "cases_by_label": cases_by_label,
        "known_gap_cases": known_gap_cases,
        "real_failures": real_failures,
    }


def render_error_report(report: dict[str, Any]) -> str:
    """Render label counts and their cases as a markdown table."""
    lines = ["| label | count | case_ids |", "| --- | --- | --- |"]
    lines.extend(
        f"| {label} | {report['label_counts'][label]} | "
        f"{', '.join(report['cases_by_label'][label]) or 'none'} |"
        for label in LABELS
    )
    return "\n".join(lines)


def write_error_report(
    report: dict[str, Any], path: str | Path = "evals/error_analysis.json"
) -> None:
    """Persist the structured taxonomy report for later evaluation analysis."""
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_error_report(
    golden_path: str | Path = "evals/golden.yml",
    traces_path: str | Path = "evals/traces.jsonl",
    report_path: str | Path = "evals/error_analysis.json",
) -> dict[str, Any]:
    """Run fresh golden traces, classify them, print, and persist the report."""
    existing_trace_count = len(read_traces(traces_path))
    run_evals(golden_path, traces_path)
    report = error_report(read_traces(traces_path)[existing_trace_count:])
    print(render_error_report(report))
    write_error_report(report, report_path)
    return report


if __name__ == "__main__":
    run_error_report()
