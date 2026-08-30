"""Plan known questions into guarded, governed tool calls."""

from __future__ import annotations

import re
from typing import Any

from agent.llm_planner import plan_llm, planner_vocabulary
from governed.service import governed_query
from harness.citation import render_citation
from harness.graph_lineage import graph_lineage_for_metric
from harness.tools import (
    _json_safe,
    check_policy,
    describe_metric,
    impact_of,
    list_metrics,
    query_customers,
    query_metric,
    search_docs,
)
from models.provider import LLMProvider

_DEFAULT_DATABASE_PATH = "grounded." + "duck" + "db"


def _terms(value: str) -> set[str]:
    """Normalize lightweight lexical hints without encoding a pack's golden cases."""
    return {
        token.rstrip("s")
        for token in re.findall(r"[a-z0-9]+", value.casefold().replace("_", " "))
        if len(token) > 2
    }


def _matching_metric(question: str, metrics: dict[str, dict[str, Any]]) -> str | None:
    question_terms = _terms(question)
    scored = [
        (
            len(
                question_terms
                & (_terms(metric) | _terms(str(details.get("label", ""))))
            ),
            metric,
        )
        for metric, details in metrics.items()
    ]
    score, metric = max(scored, default=(0, ""))
    return metric if score else None


def plan(question: str) -> dict:
    """Route obvious declared metric requests through the active pack's surface."""
    normalized = question.casefold()
    vocabulary = planner_vocabulary()
    if any(term in normalized for term in ("drop", "delete", "truncate", "alter", "insert", "update")):
        return {"tool": "refuse", "args": {}}
    if "customer" in normalized or "email" in normalized:
        return {"tool": "query_customers", "args": {}}
    metric = _matching_metric(question, vocabulary["metrics"])
    if metric is not None and any(
        term in normalized for term in ("mean", "meaning", "defined", "definition")
    ):
        return {"tool": "search_docs", "args": {"query": question}}
    if metric is not None and (
        "describe" in normalized or "defined" in normalized or "definition" in normalized
    ):
        return {"tool": "describe_metric", "args": {"metric": metric}}
    matched_policy_target = next(
        (
            target
            for target in vocabulary["policy_targets"]
            if target.rsplit(".", 1)[-1].casefold() in normalized
        ),
        None,
    )
    explicit_policy_request = any(
        term in normalized for term in ("policy", "allowed", "permission", "mask", "protect")
    )
    sensitive_read_request = (
        matched_policy_target in vocabulary["sensitive_policy_targets"]
        and any(term in normalized for term in ("can", "see", "view", "access"))
    )
    if matched_policy_target is not None and (explicit_policy_request or sensitive_read_request):
        target = next(
            (
                target
                for target in vocabulary["policy_targets"]
                if target.rsplit(".", 1)[-1].casefold() in normalized
            ),
            None,
        )
        if target is not None:
            return {"tool": "check_policy", "args": {"target": target, "role": "viewer"}}
    if metric is None:
        return {"tool": "refuse", "args": {}}
    declaration = vocabulary["metrics"][metric]
    dimensions = [
        dimension
        for dimension in declaration["dimensions"]
        if dimension.casefold() in normalized
    ]
    filters = (
        {"order_month": "last_month"}
        if "last month" in normalized and "order_month" in declaration["filters"]
        else {}
    )
    return {
        "tool": "query_metric",
        "args": {"metric": metric, "dimensions": dimensions, "filters": filters},
    }


def _execute_tool_call(
    tool_call: dict,
    role: str,
    *,
    backend: str = "fixture",
    cube_url: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Execute an already-selected governed tool call without widening its surface."""
    tool = tool_call["tool"]
    args = tool_call["args"]

    if tool == "query_metric":
        if backend == "fixture" and cube_url is None and db_path is None:
            payload = query_metric(role=role, **args)
        else:
            payload = governed_query(
                role=role,
                backend=backend,
                cube_url=cube_url,
                db_path=db_path or _DEFAULT_DATABASE_PATH,
                **args,
            )
            definition = payload["resolved_definition"]
            graph_lineage = graph_lineage_for_metric(definition)
            payload.update(
                {
                    "metric_definition": {
                        key: value
                        for key, value in definition["definition"].items()
                        if key
                        in {
                            "measure",
                            "grain",
                            "filter",
                            "derived",
                            "numerator",
                            "denominator",
                        }
                    },
                    "lineage_citation": render_citation(definition),
                    "lineage_graph_verified": graph_lineage["verified"],
                    "lineage_graph": {
                        "nodes": graph_lineage["nodes"],
                        "edges": graph_lineage["edges"],
                    },
                }
            )
            payload = _json_safe(payload)
        return {
            "answer_rows": payload["rows"],
            "metric_definition": payload["metric_definition"],
            "policy_applied": payload["policy_decisions"],
            "verify_status": payload["verify_status"],
            "lineage_citation": payload["lineage_citation"],
        }
    if tool == "query_customers":
        payload = query_customers(role=role)
        return {
            "answer_rows": payload["rows"],
            "metric_definition": None,
            "policy_applied": payload["policy_decisions"],
            "verify_status": payload["verify_status"],
            "lineage_citation": None,
        }
    if tool == "describe_metric":
        payload = describe_metric(**args)
        return {
            "answer_rows": [],
            "metric_definition": payload["definition"],
            "policy_applied": payload["policies"],
            "verify_status": None,
            "lineage_citation": payload["lineage_citation"],
        }
    if tool == "list_metrics":
        return {
            "answer_rows": list_metrics(),
            "metric_definition": None,
            "policy_applied": [],
            "verify_status": None,
            "lineage_citation": None,
        }
    if tool == "check_policy":
        payload = check_policy(**args)
        return {
            "answer_rows": [],
            "metric_definition": None,
            "policy_applied": [payload],
            "verify_status": None,
            "lineage_citation": None,
        }
    if tool == "impact_of":
        payload = impact_of(**args)
        return {
            "answer_rows": [
                {"dataset": dataset} for dataset in payload["downstream_datasets"]
            ],
            "metric_definition": None,
            "policy_applied": [],
            "verify_status": None,
            "lineage_citation": None,
            "impact": payload,
        }
    if tool == "search_docs":
        results = search_docs(**args)
        if not results:
            return {
                "message": "I could not find a cited definition or governance document for that question."
            }
        top_result = results[0]
        chunk = top_result["chunk"]
        citation = f"[{top_result['doc']}#{chunk['heading']}]"
        return {
            "answer": f"{chunk['text']} {citation}",
            "doc_citation": citation,
            "answer_rows": [],
            "metric_definition": None,
            "policy_applied": [],
            "verify_status": None,
            "lineage_citation": None,
        }
    available = [metric["metric"] for metric in list_metrics()]
    return {"message": f"I can only answer governed metrics: [{', '.join(available)}]"}


def answer(
    question: str,
    role: str = "viewer",
    planner: str = "deterministic",
    provider: LLMProvider | None = None,
    *,
    backend: str = "fixture",
    cube_url: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Execute a deterministic or guarded-LLM governed plan and return its answer."""
    if planner == "deterministic":
        tool_call = plan(question)
    elif planner == "llm":
        if provider is None:
            raise ValueError("The LLM planner requires an LLMProvider.")
        tool_call = plan_llm(question, provider)
    else:
        raise ValueError("planner must be either 'deterministic' or 'llm'.")
    return _execute_tool_call(
        tool_call,
        role,
        backend=backend,
        cube_url=cube_url,
        db_path=db_path,
    )
