"""Pure governed MCP tool functions; transport registration lives in ``mcp.server``."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import yaml

from governed.service import governed_customers, governed_query
from harness.citation import render_citation
from harness.graph_lineage import graph_lineage_for_metric
from harness.graph_lineage import impact_of as graph_impact_of
from packlib import active_pack
from policy.engine import check_policy as evaluate_policy
from rag.retriever import search
from resolver.metric_resolver import _load_definition


def _definitions() -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    pack = active_pack()
    for definition_path in sorted(pack.semantics.metrics if pack.semantics else ()):
        with definition_path.open(encoding="utf-8") as definition_file:
            definitions.append(yaml.safe_load(definition_file))
    return definitions


def _metric_definition(metric: str) -> dict[str, Any]:
    return _load_definition(metric)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def list_metrics() -> list[dict]:
    """List the governed metrics available to an agent, excluding entity reads."""
    return [
        {
            "metric": definition["metric"],
            "label": definition["label"],
            "description": definition["description"],
            "owner": definition["owner"],
        }
        for definition in _definitions()
        if definition.get("metric")
    ]


def describe_metric(metric: str) -> dict:
    """Describe a governed metric, its rules, and its Contract-B lineage citation."""
    definition = _metric_definition(metric)
    graph_lineage = graph_lineage_for_metric(definition)
    return {
        "metric": metric,
        "definition": definition["definition"],
        "dimensions": definition["dimensions"],
        "policies": definition["policies"],
        "verification": definition["verification"],
        "lineage_citation": render_citation(definition),
        "lineage_graph_verified": graph_lineage["verified"],
        "lineage_graph": {
            "nodes": graph_lineage["nodes"],
            "edges": graph_lineage["edges"],
        },
    }


def query_metric(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict | None = None,
    role: str = "viewer",
) -> dict:
    """Run one governed metric query with policy, verification, audit, and lineage."""
    result = governed_query(metric, dimensions, filters, role)
    definition = result["resolved_definition"]
    graph_lineage = graph_lineage_for_metric(definition)
    result.update(
        {
            "metric_definition": {
                key: value
                for key, value in definition["definition"].items()
                if key in {"measure", "grain", "filter", "derived", "numerator", "denominator"}
            },
            "lineage_citation": render_citation(definition),
            "lineage_graph_verified": graph_lineage["verified"],
            "lineage_graph": {
                "nodes": graph_lineage["nodes"],
                "edges": graph_lineage["edges"],
            },
        }
    )
    return _json_safe(result)


def query_customers(role: str = "viewer") -> dict:
    """Run the governed customer-directory read used by the masking demonstration."""
    return _json_safe(governed_customers(role))


def impact_of(dataset: str) -> dict:
    """Return graph-derived downstream datasets and governed metric impact."""
    return graph_impact_of(dataset)


def check_policy(target: str, role: str) -> dict:
    """Explain the declared governance decision for a target column and role."""
    for definition in _definitions():
        policy_targets = {policy.get("applies_to") for policy in definition.get("policies", [])}
        column_targets = {column.get("source") for column in definition.get("columns", [])}
        if target in policy_targets or target in column_targets:
            return evaluate_policy(target, role, definition)
    return {
        "target": target,
        "rule": "allow",
        "decision": "allow",
        "reason": "no policy applies",
    }


def search_docs(query: str, k: int = 3) -> list[dict]:
    """Retrieve cited definition and governance prose; never use it for numbers."""
    return [
        {
            "doc": result["doc"],
            "chunk": {"heading": result["heading"], "text": result["text"]},
            "score": result["score"],
        }
        for result in search(query, k)
    ]
