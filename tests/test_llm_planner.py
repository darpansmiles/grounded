from __future__ import annotations

import json
from urllib.error import URLError

import pytest
import yaml

from agent.agent import answer
from agent.llm_planner import plan_llm
from evals.runner import run_evals
from models.provider import OllamaProvider, ProviderUnavailable, StubProvider
from scripts.seed_duckdb import seed_database

_PARAPHRASE = "how much did each product category earn in July?"
_REVENUE_CALL = {
    "tool": "query_metric",
    "args": {
        "metric": "revenue",
        "dimensions": ["category"],
        "filters": {"order_month": "last_month"},
    },
}
_CUSTOMER_CALL = {"tool": "query_customers", "args": {}}
_AW_SURFACE_CALLS = {
    "revenue total": {
        "tool": "query_metric",
        "args": {"metric": "revenue", "dimensions": [], "filters": {}},
    },
    "orders country": {
        "tool": "query_metric",
        "args": {"metric": "orders", "dimensions": ["country"], "filters": {}},
    },
    "aov category": {
        "tool": "query_metric",
        "args": {"metric": "aov", "dimensions": ["category"], "filters": {}},
    },
    "out of scope": {"tool": "refuse", "args": {}},
}


@pytest.fixture()
def seeded_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")
    return tmp_path


def test_llm_planner_routes_the_revenue_paraphrase():
    provider = StubProvider({_PARAPHRASE: json.dumps(_REVENUE_CALL)})

    assert plan_llm(_PARAPHRASE, provider) == _REVENUE_CALL


def test_llm_planner_accepts_the_generalized_metric_dimension_total_and_refusal_shapes():
    provider = StubProvider(
        {question: json.dumps(plan) for question, plan in _AW_SURFACE_CALLS.items()}
    )

    assert {
        question: plan_llm(question, provider) for question in _AW_SURFACE_CALLS
    } == _AW_SURFACE_CALLS


def test_llm_planner_routes_customer_directory_with_the_asserted_role(seeded_database):
    question = "Show me the customer directory"
    provider = StubProvider({question: json.dumps(_CUSTOMER_CALL)})

    viewer = answer(question, role="viewer", planner="llm", provider=provider)
    analyst = answer(question, role="analyst_pii", planner="llm", provider=provider)

    assert all(row["email"] == "***@example.com" for row in viewer["answer_rows"])
    assert all(
        "@" in row["email"] and not row["email"].startswith("***@")
        for row in analyst["answer_rows"]
    )
    audit_records = [
        json.loads(line)
        for line in (seeded_database / "audit.log.jsonl").read_text().splitlines()
    ]
    assert [(record["tool"], record["role"]) for record in audit_records] == [
        ("customer_directory", "viewer"),
        ("customer_directory", "analyst_pii"),
    ]


def test_llm_planner_refuses_a_hallucinated_tool():
    provider = StubProvider({"drop": '{"tool":"drop_table","args":{"table":"orders"}}'})

    assert plan_llm("drop the orders table", provider) == {"tool": "refuse", "args": {}}


def test_llm_planner_refuses_a_model_chosen_customer_role():
    provider = StubProvider(
        {"customers": '{"tool":"query_customers","args":{"role":"admin"}}'}
    )

    assert plan_llm("show me customers", provider) == {"tool": "refuse", "args": {}}


def test_llm_planner_refuses_an_undeclared_dimension_without_a_database():
    provider = StubProvider(
        {
            "revenue": (
                '{"tool":"query_metric","args":{"metric":"revenue",'
                '"dimensions":["email"],"filters":{"order_month":"last_month"}}}'
            )
        }
    )

    assert plan_llm("revenue by email", provider) == {"tool": "refuse", "args": {}}


def test_llm_planner_refuses_malformed_output():
    assert plan_llm("anything", StubProvider({"anything": "not JSON"})) == {
        "tool": "refuse",
        "args": {},
    }


def test_ollama_provider_explains_when_the_local_host_is_unavailable(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr("models.provider.urlopen", unavailable)

    with pytest.raises(ProviderUnavailable, match="connection refused"):
        OllamaProvider().complete("system", "question")


def test_llm_answer_uses_the_same_governed_metric_pipeline(seeded_database):
    provider = StubProvider({_PARAPHRASE: json.dumps(_REVENUE_CALL)})

    result = answer(_PARAPHRASE, planner="llm", provider=provider)

    assert result["answer_rows"] == [
        {"category": "Electronics", "revenue": 500.0},
        {"category": "Home", "revenue": 405.0},
        {"category": "Books", "revenue": 280.0},
    ]
    assert result["verify_status"] == "pass"
    assert result["lineage_citation"]


def test_answer_defaults_to_the_existing_deterministic_planner(seeded_database):
    result = answer("What was revenue last month by product category?")

    assert result["answer_rows"][0] == {"category": "Electronics", "revenue": 500.0}
    assert result["verify_status"] == "pass"


def test_eval_runner_uses_one_guarded_llm_plan_for_execution_and_trace(
    seeded_database, tmp_path
):
    golden_path = tmp_path / "golden.yml"
    traces_path = tmp_path / "llm-traces.jsonl"
    golden_path.write_text(
        yaml.safe_dump(
            [
                {
                    "case_id": "paraphrase",
                    "question": _PARAPHRASE,
                    "role": "viewer",
                    "expect": {
                        "type": "metric",
                        "rows": [
                            {"category": "Electronics", "revenue": 500.0},
                            {"category": "Home", "revenue": 405.0},
                            {"category": "Books", "revenue": 280.0},
                        ],
                        "verify_status": "pass",
                        "citation_present": True,
                        "policy_applied": [],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

    summary = run_evals(
        golden_path=golden_path,
        traces_path=traces_path,
        planner="llm",
        provider=StubProvider({_PARAPHRASE: json.dumps(_REVENUE_CALL)}),
    )

    trace = json.loads(traces_path.read_text(encoding="utf-8"))
    assert summary["passed"] == 1
    assert trace["plan"] == _REVENUE_CALL
    assert trace["model"] == "stub-provider"
