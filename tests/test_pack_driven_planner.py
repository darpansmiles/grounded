from __future__ import annotations

from agent.agent import plan
from agent.llm_planner import system_prompt, validate_model_output
from evals.benchmark import run_benchmark


class RecordingProvider:
    """Minimal provider double that captures the prompt received by the benchmark."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, system: str, _question: str) -> str:
        self.prompts.append(system)
        return '{"tool":"refuse","args":{}}'


def test_spider_planner_uses_its_declared_metric_and_dimension(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "spider_world1")

    prompt = system_prompt()
    metric_plan = {
        "tool": "query_metric",
        "args": {
            "metric": "total_population",
            "dimensions": ["continent"],
            "filters": {},
        },
    }

    assert '"total_population"' in prompt
    assert '"continent"' in prompt
    assert '"revenue"' not in prompt
    assert validate_model_output(metric_plan) == metric_plan
    assert plan("Show total population by continent.") == metric_plan
    assert validate_model_output({"tool": "refuse", "args": {}}) == {
        "tool": "refuse",
        "args": {},
    }


def test_bird_planner_uses_its_declared_metrics_and_dimension(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "bird_ca_schools")
    plans = [
        {
            "tool": "query_metric",
            "args": {"metric": metric, "dimensions": ["county"], "filters": {}},
        }
        for metric in ("school_count", "total_enrollment")
    ]

    prompt = system_prompt()

    assert '"school_count"' in prompt
    assert '"total_enrollment"' in prompt
    assert '"county"' in prompt
    assert [validate_model_output(plan) for plan in plans] == plans
    assert plan("Count schools by county.") == plans[0]


def test_adventureworks_prompt_and_validation_keep_its_declared_surface(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "adventureworks")
    plan = {
        "tool": "query_metric",
        "args": {
            "metric": "revenue",
            "dimensions": ["category"],
            "filters": {"order_month": "last_month"},
        },
    }

    assert 'one of ["revenue", "orders", "aov"]' in system_prompt()
    assert validate_model_output(plan) == plan


def test_benchmark_renders_the_active_pack_prompt(tmp_path):
    provider = RecordingProvider()

    run_benchmark(
        ["recording"],
        runs=1,
        dataset="spider_world1",
        provider_factory=lambda _model: provider,
        output_path=tmp_path / "benchmark.json",
    )

    assert provider.prompts
    assert all('"total_population"' in prompt for prompt in provider.prompts)
    assert all('"revenue"' not in prompt for prompt in provider.prompts)
