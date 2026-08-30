"""Execute Grounded's golden set and score structured evaluation traces."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

import yaml

from agent.agent import _execute_tool_call, plan
from agent.llm_planner import plan_llm
from evals.trace import Trace, write_traces
from models.provider import LLMProvider


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {"check": name, "status": "pass" if passed else "fail", "detail": detail}


def _metric_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"category": row.get("category"), "revenue": float(row.get("revenue"))}
        for row in rows
    ]


def _score_metric(answer_payload: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, str]]:
    actual_rows = _metric_rows(answer_payload.get("answer_rows", []))
    expected_rows = _metric_rows(expected["rows"])
    citation_present = bool(answer_payload.get("lineage_citation"))
    return [
        _check("rows", actual_rows == expected_rows, f"actual={actual_rows!r}; expected={expected_rows!r}"),
        _check(
            "verify_status",
            answer_payload.get("verify_status") == expected["verify_status"],
            f"actual={answer_payload.get('verify_status')!r}; expected={expected['verify_status']!r}",
        ),
        _check(
            "lineage_citation",
            citation_present == expected["citation_present"],
            f"present={citation_present}; expected={expected['citation_present']}",
        ),
        _check(
            "policy_applied",
            answer_payload.get("policy_applied", []) == expected["policy_applied"],
            f"actual={answer_payload.get('policy_applied', [])!r}; expected={expected['policy_applied']!r}",
        ),
    ]


def _score_customers(answer_payload: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, str]]:
    rows = answer_payload.get("answer_rows", [])
    emails = [row.get("email") for row in rows]
    if expected["emails_masked"]:
        emails_match = all(email == "***@example.com" for email in emails)
    else:
        emails_match = all(
            isinstance(email, str) and "@" in email and not email.startswith("***@")
            for email in emails
        )
    decisions = answer_payload.get("policy_applied", [])
    decision_match = len(decisions) == 1 and decisions[0].get("decision") == expected["policy_decision"]
    return [
        _check(
            "emails_masked",
            emails_match,
            f"emails={emails!r}; expected_masked={expected['emails_masked']}",
        ),
        _check(
            "policy_decision",
            decision_match,
            f"actual={decisions!r}; expected={expected['policy_decision']!r}",
        ),
    ]


def _score_describe(answer_payload: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, str]]:
    citation_present = bool(answer_payload.get("lineage_citation"))
    return [
        _check(
            "metric_definition",
            answer_payload.get("metric_definition") is not None,
            f"present={answer_payload.get('metric_definition') is not None}",
        ),
        _check(
            "lineage_citation",
            citation_present == expected["citation_present"],
            f"present={citation_present}; expected={expected['citation_present']}",
        ),
    ]


def _score_refuse(
    answer_payload: dict[str, Any], tool_plan: dict[str, Any]
) -> list[dict[str, str]]:
    message = answer_payload.get("message")
    message_lists_metrics = (
        isinstance(message, str) and "governed metrics" in message and "revenue" in message
    )
    return [
        _check("plan", tool_plan.get("tool") == "refuse", f"tool={tool_plan.get('tool')!r}"),
        _check("answer_rows", answer_payload.get("answer_rows", []) == [], "answer rows are empty"),
        _check("refusal_message", message_lists_metrics, f"message={message!r}"),
    ]


def _score(
    answer_payload: dict[str, Any], tool_plan: dict[str, Any], expected: dict[str, Any]
) -> list[dict[str, str]]:
    match expected["type"]:
        case "metric":
            return _score_metric(answer_payload, expected)
        case "customers":
            return _score_customers(answer_payload, expected)
        case "describe":
            return _score_describe(answer_payload, expected)
        case "refuse":
            return _score_refuse(answer_payload, tool_plan)
        case unexpected_type:
            raise ValueError(f"Unsupported golden expectation type: {unexpected_type}")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _planner_label(planner: str, provider: LLMProvider | None) -> str:
    if planner == "deterministic":
        return "deterministic-planner"
    model = getattr(provider, "model", None)
    return f"ollama:{model}" if isinstance(model, str) else "stub-provider"


def run_evals(
    golden_path: str | Path = "evals/golden.yml",
    traces_path: str | Path = "evals/traces.jsonl",
    planner: str = "deterministic",
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Run every PM-authored golden case with a deterministic or guarded LLM planner."""
    if planner not in {"deterministic", "llm"}:
        raise ValueError("planner must be either 'deterministic' or 'llm'.")
    if planner == "llm" and provider is None:
        raise ValueError("The LLM planner requires an LLMProvider.")
    with Path(golden_path).open(encoding="utf-8") as golden_file:
        golden_cases = yaml.safe_load(golden_file)

    traces: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for case in golden_cases:
        tool_plan = (
            plan(case["question"])
            if planner == "deterministic"
            else plan_llm(case["question"], provider)
        )
        started = time.perf_counter()
        answer_payload = _execute_tool_call(tool_plan, case["role"])
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        expected = case["expect"]
        checks = _score(answer_payload, tool_plan, expected)
        outcome = "pass" if all(check["status"] == "pass" for check in checks) else "fail"
        trace = Trace(
            trace_id=str(uuid4()),
            timestamp=_utc_timestamp(),
            case_id=case["case_id"],
            question=case["question"],
            role=case["role"],
            plan=tool_plan,
            answer_rows=answer_payload.get("answer_rows", []),
            policy_applied=answer_payload.get("policy_applied", []),
            verify_status=answer_payload.get("verify_status"),
            lineage_citation=answer_payload.get("lineage_citation"),
            latency_ms=latency_ms,
            model=_planner_label(planner, provider),
            cost_usd=0.0,
            expected=expected,
            checks=checks,
            outcome=outcome,
            known_gap=bool(case.get("known_gap", False)),
        ).to_dict()
        traces.append(trace)
        cases.append(
            {
                "case_id": case["case_id"],
                "outcome": outcome,
                "known_gap": bool(case.get("known_gap", False)),
            }
        )

    write_traces(traces, traces_path)
    failed = sum(case["outcome"] == "fail" for case in cases)
    known_gaps = sum(
        case["outcome"] == "fail" and case["known_gap"] for case in cases
    )
    unexpected_failures = sum(
        case["outcome"] == "fail" and not case["known_gap"] for case in cases
    )
    summary = {
        "total": len(cases),
        "passed": len(cases) - failed,
        "failed": failed,
        "known_gaps": known_gaps,
        "unexpected_failures": unexpected_failures,
        "cases": cases,
    }

    print("case_id | outcome | known_gap")
    for case in cases:
        print(f"{case['case_id']} | {case['outcome']} | {case['known_gap']}")
    print(
        f"{summary['passed']}/{summary['total']} passed; {summary['known_gaps']} known gaps; "
        f"{summary['unexpected_failures']} unexpected failures"
    )
    return summary


if __name__ == "__main__":
    run_evals()
