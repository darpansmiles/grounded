from __future__ import annotations

import json

from agent.llm_planner import SYSTEM_PROMPT, plan_llm, system_prompt
from agent.ungoverned import answer_ungoverned
from evals.benchmark import run_benchmark
from models.provider import StubProvider

_REVENUE_PLAN = {
    "tool": "query_metric",
    "args": {
        "metric": "revenue",
        "dimensions": ["category"],
        "filters": {"order_month": "last_month"},
    },
}


def test_planner_accepts_fenced_reasoning_wrapped_and_bare_json():
    responses = {
        "fenced": "```json\n" + json.dumps(_REVENUE_PLAN) + "\n```",
        "reasoning": "I will use the governed metric.\n"
        + json.dumps(_REVENUE_PLAN)
        + "\nThis is safe.",
        "bare": json.dumps(_REVENUE_PLAN),
    }
    provider = StubProvider(responses)

    assert plan_llm("fenced", provider) == _REVENUE_PLAN
    assert plan_llm("reasoning", provider) == _REVENUE_PLAN
    assert plan_llm("bare", provider) == _REVENUE_PLAN


def test_planner_keeps_refusing_hallucinated_undeclared_and_unparseable_responses():
    provider = StubProvider(
        {
            "hallucinated": '```json\n{"tool":"drop_table","args":{"table":"orders"}}\n```',
            "undeclared": '```json\n{"tool":"query_metric","args":{"metric":"revenue","dimensions":["email"],"filters":{}}}\n```',
            "unparseable": "I cannot provide a plan.",
        }
    )

    assert plan_llm("hallucinated", provider) == {"tool": "refuse", "args": {}}
    assert plan_llm("undeclared", provider) == {"tool": "refuse", "args": {}}
    assert plan_llm("unparseable", provider) == {"tool": "refuse", "args": {}}


def test_system_prompt_has_tool_schemas_and_active_pack_vocabulary():
    assert "query_metric:" in SYSTEM_PROMPT
    assert "check_policy:" in SYSTEM_PROMPT
    assert "describe_metric:" in SYSTEM_PROMPT
    assert 'one of ["revenue", "orders", "aov"]' in SYSTEM_PROMPT
    assert 'dimensions: a subset of ["category", "country", "order_month"] (or [])' in SYSTEM_PROMPT
    assert 'filters: {} or {"order_month": "last_month"}' in SYSTEM_PROMPT
    assert '"metric":"revenue","dimensions":["category"],"filters":{}' in SYSTEM_PROMPT
    assert "Forecast next year's demand." in SYSTEM_PROMPT
    assert system_prompt() == SYSTEM_PROMPT


def test_benchmark_and_ungoverned_traces_keep_raw_outputs_and_reasons(tmp_path):
    golden_path = tmp_path / "golden.yml"
    golden_path.write_text(
        """- case_id: revenue
  question: Revenue by category
  role: viewer
  expected_plan:
    tool: query_metric
    args:
      metric: revenue
      dimensions: [category]
      filters: {order_month: last_month}
  expect: {type: metric}
""",
        encoding="utf-8",
    )
    raw_response = "reasoning\n```json\n" + json.dumps(_REVENUE_PLAN) + "\n```"
    benchmark = run_benchmark(
        ["stub"],
        golden=golden_path,
        provider_factory=lambda _model: StubProvider(
            {"Revenue by category": raw_response}
        ),
        output_path=tmp_path / "benchmark.json",
    )
    sample = benchmark["scorecards"]["stub"]["per_run"][0]["samples"][0]
    ungoverned = answer_ungoverned(
        "write", StubProvider({"write": "DROP TABLE orders"})
    )

    assert sample["raw_model_output"] == raw_response
    assert sample["parsed_plan"] == _REVENUE_PLAN
    assert ungoverned["raw_sql"] == "DROP TABLE orders"
    assert ungoverned["rejection_reason"] == "only one SELECT statement is allowed"
