"""Compute ungoverned-control answer keys through the existing governed resolver."""

from __future__ import annotations

from typing import Any

from governed.service import governed_query


def ground_truth_for_case(case: dict[str, Any], db_path: str = "grounded.duckdb") -> dict[str, Any]:
    """Return governed metric rows or the deliberate no-valid-answer refusal ground truth."""
    expected_type = case["expect"]["type"]
    if expected_type == "refuse":
        return {"type": "refuse", "rows": None}
    if expected_type != "metric":
        raise ValueError(f"Ungoverned control has no ground truth for {expected_type!r} cases.")
    args = case["expected_plan"]["args"]
    result = governed_query(
        args["metric"],
        args.get("dimensions", []),
        args.get("filters", {}),
        case["role"],
        db_path=db_path,
    )
    return {"type": "metric", "rows": result["rows"]}


def control_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep metric and refusal cases; harness-specific meta-tool cases are excluded."""
    return [case for case in cases if case["expect"]["type"] in {"metric", "refuse"}]
