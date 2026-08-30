"""Compare a planner's governed tool call with a Golden-v2 expected call."""

from __future__ import annotations

from typing import Any


def _normalized_args(args: Any) -> dict[str, Any] | None:
    """Normalize optional metric dimensions and filters before exact argument comparison."""
    if not isinstance(args, dict):
        return None
    normalized = dict(args)
    dimensions = normalized.get("dimensions", [])
    filters = normalized.get("filters", {})
    if not isinstance(dimensions, list) or not isinstance(filters, dict):
        return None
    normalized["dimensions"] = sorted(dimensions)
    normalized["filters"] = filters
    return normalized


def score_routing(produced_plan: dict[str, Any], expected_plan: dict[str, Any]) -> bool:
    """Return whether one plan selects the expected governed call and arguments.

    Dimension order does not change a metric query. Missing dimensions or filters
    mean the same thing as empty collections. Refusal is a distinct terminal plan:
    it can only match an expected refusal.
    """
    produced_tool = produced_plan.get("tool") if isinstance(produced_plan, dict) else None
    expected_tool = expected_plan.get("tool") if isinstance(expected_plan, dict) else None
    if produced_tool != expected_tool:
        return False
    if expected_tool == "refuse":
        return produced_tool == "refuse"

    produced_args = _normalized_args(produced_plan.get("args"))
    expected_args = _normalized_args(expected_plan.get("args"))
    return produced_args is not None and produced_args == expected_args
