"""Validate an LLM's proposed call against the active pack's governed surface."""

from __future__ import annotations

import json
from typing import Any

from models.provider import LLMProvider
from packlib import active_pack
from semantics.loader import load_expanded_definition

_REFUSAL = {"tool": "refuse", "args": {}}
_ALLOWED_TOOLS = {
    "list_metrics",
    "describe_metric",
    "query_metric",
    "query_customers",
    "check_policy",
    "impact_of",
    "search_docs",
}


def planner_vocabulary() -> dict[str, Any]:
    """Read the active pack's public planner vocabulary from Contract-B assets."""
    pack = active_pack()
    metrics: dict[str, dict[str, Any]] = {}
    policy_targets: list[str] = []
    sensitive_policy_targets: list[str] = []
    impact_datasets: list[str] = []
    for metric_path in pack.semantics.metrics if pack.semantics else ():
        definition = load_expanded_definition(metric_path.stem)
        metric = definition["metric"]
        dimensions = [dimension["name"] for dimension in definition.get("dimensions", [])]
        metrics[metric] = {
            "dimensions": dimensions,
            "filters": {"order_month": ["last_month"]}
            if "order_month" in dimensions
            else {},
            "label": definition.get("label", metric),
        }
        for policy in definition.get("policies", []):
            target = policy.get("applies_to")
            if isinstance(target, str) and target and target not in policy_targets:
                policy_targets.append(target)
            if (
                isinstance(target, str)
                and policy.get("rule") in {"mask", "deny"}
                and target not in sensitive_policy_targets
            ):
                sensitive_policy_targets.append(target)
        for dataset in definition.get("lineage", {}).get("tables", []):
            if isinstance(dataset, str) and dataset.count(".") == 1 and dataset not in impact_datasets:
                impact_datasets.append(dataset)
    if not metrics:
        raise ValueError(f"Active pack {pack.name!r} declares no planner metrics")
    return {
        "metrics": metrics,
        "policy_targets": policy_targets,
        "sensitive_policy_targets": sensitive_policy_targets,
        "impact_datasets": impact_datasets,
    }


def system_prompt() -> str:
    """Render generic planner instructions from the active pack's Contract-B."""
    vocabulary = planner_vocabulary()
    metrics = vocabulary["metrics"]
    metric_names = list(metrics)
    all_dimensions = sorted(
        {dimension for item in metrics.values() for dimension in item["dimensions"]}
    )
    filter_names = sorted(
        {filter_name for item in metrics.values() for filter_name in item["filters"]}
    )
    metric_lines = [
        "Declared metric vocabulary:",
        *[
            f"- {metric}: dimensions {json.dumps(item['dimensions'])}; "
            f"filters {json.dumps(item['filters'], sort_keys=True)}"
            for metric, item in metrics.items()
        ],
    ]
    policy_targets = vocabulary["policy_targets"] or ["a declared policy target"]
    impact_datasets = vocabulary["impact_datasets"] or ["a declared lineage dataset"]
    example_metric = metric_names[0]
    example_plan = {
        "tool": "query_metric",
        "args": {
            "metric": example_metric,
            "dimensions": metrics[example_metric]["dimensions"][:1],
            "filters": {},
        },
    }
    return "\n".join(
        [
            "You are a planner for Grounded. Return one JSON object with exactly",
            '{"tool": "...", "args": {...}}. The only allowed tools and argument schemas are:',
            "- list_metrics: {}",
            f"- describe_metric: {{\"metric\": one of {json.dumps(metric_names)}}}",
            "- query_metric: {\"metric\": a declared metric, \"dimensions\": a subset of that metric's declared dimensions (or []), \"filters\": only that metric's declared filter vocabulary}",
            f"  dimensions: a subset of {json.dumps(all_dimensions)} (or [])",
            (
                '  filters: {} or {"order_month": "last_month"}'
                if "order_month" in filter_names
                else "  filters: {}"
            ),
            "- query_customers: {}",
            f"- check_policy: {{\"target\": one of {json.dumps(policy_targets)}, \"role\": a role name}}",
            f"- impact_of: {{\"dataset\": one of {json.dumps(impact_datasets)}}}",
            "- search_docs: {\"query\": a question, \"k\": optional positive integer}",
            *metric_lines,
            "",
            "Examples demonstrate the governed surface, not a benchmark answer key:",
            "Question: Break down a declared metric by a permitted dimension.",
            json.dumps(example_plan, separators=(",", ":")),
            "Question: Explain a declared metric definition.",
            json.dumps(
                {"tool": "describe_metric", "args": {"metric": example_metric}},
                separators=(",", ":"),
            ),
            "Question: Forecast next year's demand.",
            '{"tool":"refuse","args":{}}',
            "",
            "For query_metric, use only the declared metrics, dimensions, and filters above. Never emit SQL, database commands, extra arguments, or tools outside this list. If the question cannot be mapped to one call, respond {\"tool\":\"refuse\",\"args\":{}}.",
            f"The active dimensions are {json.dumps(all_dimensions)} and the active filter names are {json.dumps(filter_names)}.",
        ]
    )


# Compatibility for callers that inspect the default AdventureWorks prompt at import time.
SYSTEM_PROMPT = system_prompt()


def _is_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _extract_json_object(raw_response: Any) -> str | None:
    """Extract the first balanced JSON object from a raw model response."""
    if not isinstance(raw_response, str):
        return None
    response_without_fences = "\n".join(
        line
        for line in raw_response.splitlines()
        if line.strip().casefold() not in {"```", "```json"}
    )
    start = response_without_fences.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index, character in enumerate(response_without_fences[start:], start):
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                continue
            if character == '"':
                in_string = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return response_without_fences[start : index + 1]
        start = response_without_fences.find("{", start + 1)
    return None


def parse_model_output(raw_response: Any) -> dict[str, Any] | None:
    """Parse the first JSON object, tolerating fences, prose, and trailing text."""
    extracted = _extract_json_object(raw_response)
    if extracted is None:
        return None
    try:
        parsed = json.loads(extracted)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _valid_query_metric_args(args: dict[str, Any]) -> bool:
    if set(args) - {"metric", "dimensions", "filters"} or not _is_string(
        args.get("metric")
    ):
        return False
    dimensions = args.get("dimensions", [])
    filters = args.get("filters", {})
    if not isinstance(dimensions, list) or not all(
        isinstance(dimension, str) for dimension in dimensions
    ):
        return False
    if not isinstance(filters, dict) or not all(
        isinstance(name, str) for name in filters
    ):
        return False
    declaration = planner_vocabulary()["metrics"].get(args["metric"])
    if declaration is None or any(
        dimension not in declaration["dimensions"] for dimension in dimensions
    ):
        return False
    return all(
        filter_value in declaration["filters"].get(filter_name, [])
        for filter_name, filter_value in filters.items()
    )


def _valid_tool_call(tool_call: Any) -> bool:
    if not isinstance(tool_call, dict) or set(tool_call) != {"tool", "args"}:
        return False
    tool = tool_call["tool"]
    args = tool_call["args"]
    if tool not in _ALLOWED_TOOLS or not isinstance(args, dict):
        return False
    vocabulary = planner_vocabulary()
    if tool == "list_metrics":
        return not args
    if tool == "describe_metric":
        return set(args) == {"metric"} and args["metric"] in vocabulary["metrics"]
    if tool == "query_metric":
        return _valid_query_metric_args(args)
    if tool == "query_customers":
        return not args
    if tool == "check_policy":
        return (
            set(args) == {"target", "role"}
            and args["target"] in vocabulary["policy_targets"]
            and _is_string(args["role"])
        )
    if tool == "impact_of":
        return set(args) == {"dataset"} and args["dataset"] in vocabulary["impact_datasets"]
    if tool == "search_docs":
        if set(args) - {"query", "k"} or not _is_string(args.get("query")):
            return False
        k = args.get("k", 3)
        return isinstance(k, int) and not isinstance(k, bool) and k > 0
    return False


def validate_model_output(parsed_plan: dict[str, Any] | None) -> dict[str, Any]:
    """Return one validated governed call, refusing malformed or ungoverned plans."""
    if parsed_plan is None or not _valid_tool_call(parsed_plan):
        return dict(_REFUSAL)
    return parsed_plan


def plan_llm(question: str, provider: LLMProvider) -> dict:
    """Return a validated governed call, refusing malformed or ungoverned proposals."""
    return validate_model_output(
        parse_model_output(provider.complete(system_prompt(), question))
    )
