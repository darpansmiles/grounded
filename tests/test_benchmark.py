from __future__ import annotations

import json
import time

import yaml

from evals.benchmark import render_comparison, run_benchmark
from evals.routing import score_routing
from models.provider import ProviderUnavailable, StubProvider

_METRIC_PLAN = {
    "tool": "query_metric",
    "args": {
        "metric": "revenue",
        "dimensions": ["category"],
        "filters": {"order_month": "last_month"},
    },
}
_REFUSE_PLAN = {"tool": "refuse", "args": {}}


def _golden_cases() -> list[dict]:
    return [
        {
            "case_id": "answerable",
            "question": "Revenue by category",
            "role": "viewer",
            "expected_plan": _METRIC_PLAN,
            "expect": {"type": "metric"},
        },
        {
            "case_id": "out-of-scope",
            "question": "Profit margin",
            "role": "viewer",
            "expected_plan": _REFUSE_PLAN,
            "expect": {"type": "refuse"},
        },
    ]


def test_score_routing_normalizes_dimensions_and_optional_metric_args():
    assert score_routing(
        {
            "tool": "query_metric",
            "args": {"metric": "revenue", "dimensions": ["country", "category"], "filters": {}},
        },
        {
            "tool": "query_metric",
            "args": {"metric": "revenue", "dimensions": ["category", "country"]},
        },
    )
    assert not score_routing(_METRIC_PLAN, {"tool": "describe_metric", "args": {"metric": "revenue"}})
    assert not score_routing(_METRIC_PLAN, {"tool": "query_metric", "args": {"metric": "profit"}})
    assert score_routing(_REFUSE_PLAN, {"tool": "refuse", "args": {"why": "out of scope"}})
    assert not score_routing(_REFUSE_PLAN, _METRIC_PLAN)


def test_benchmark_scores_stub_models_and_persists_per_model_distributions(tmp_path):
    golden_path = tmp_path / "golden.yml"
    output_path = tmp_path / "benchmark.json"
    golden_path.write_text(yaml.safe_dump(_golden_cases()), encoding="utf-8")

    def provider_factory(model: str):
        if model == "stub-A":
            return StubProvider(
                {
                    "Revenue by category": json.dumps(_METRIC_PLAN),
                    "Profit margin": json.dumps(_REFUSE_PLAN),
                }
            )
        return StubProvider({})

    benchmark = run_benchmark(
        ["deterministic", "stub-A", "stub-B"],
        runs=2,
        golden=golden_path,
        provider_factory=provider_factory,
        output_path=output_path,
    )

    good = benchmark["scorecards"]["stub-A"]
    refusing = benchmark["scorecards"]["stub-B"]
    assert good["scorecard"]["routing_accuracy"] == 1.0
    assert good["scorecard"]["over_refusal_rate"] == 0.0
    assert refusing["scorecard"]["appropriate_refusal_rate"] == 1.0
    assert refusing["scorecard"]["routing_accuracy"] == 0.0
    assert len(good["per_run"]) == 2
    assert {"routing_accuracy", "appropriate_refusal_rate", "over_refusal_rate", "schema_compliance_rate", "latency_ms"} <= set(good["scorecard"])
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["scorecards"]["stub-A"]["scorecard"] == good["scorecard"]
    assert persisted["scorecards"]["stub-A"]["per_run"] == [
        {"run": 1, "scorecard": good["per_run"][0]["scorecard"], "sample_count": 2},
        {"run": 2, "scorecard": good["per_run"][1]["scorecard"], "sample_count": 2},
    ]
    assert "samples" not in persisted["scorecards"]["stub-A"]["per_run"][0]
    assert "raw_model_output" not in output_path.read_text(encoding="utf-8")
    assert "deterministic" in render_comparison(benchmark)
    assert "stub-A" in render_comparison(benchmark)


def test_benchmark_records_unavailable_models_as_skipped(tmp_path):
    golden_path = tmp_path / "golden.yml"
    golden_path.write_text(yaml.safe_dump(_golden_cases()), encoding="utf-8")

    def unavailable(_model: str):
        raise ProviderUnavailable("local model not pulled")

    benchmark = run_benchmark(
        ["deterministic", "missing-model"],
        golden=golden_path,
        provider_factory=unavailable,
        output_path=tmp_path / "benchmark.json",
    )

    assert benchmark["scorecards"]["deterministic"]["status"] == "completed"
    assert {
        key: benchmark["scorecards"]["missing-model"][key]
        for key in ("status", "model", "reason", "per_run")
    } == {
        "status": "skipped",
        "model": "missing-model",
        "reason": "local model not pulled",
        "per_run": [],
    }
    assert benchmark["scorecards"]["missing-model"]["skip_reason"] == "request_error"
    assert "skipped (request_error: local model not pulled)" in render_comparison(benchmark)


def test_benchmark_marks_timed_out_model_incomplete_and_persists(tmp_path, monkeypatch):
    golden_path = tmp_path / "golden.yml"
    output_path = tmp_path / "benchmark.json"
    golden_path.write_text(yaml.safe_dump(_golden_cases()), encoding="utf-8")

    def slow_provider_run(*_args, **_kwargs):
        time.sleep(0.05)
        return []

    monkeypatch.setattr("evals.benchmark._provider_run", slow_provider_run)
    monkeypatch.setattr("evals.benchmark._release_model", lambda _model: None)

    benchmark = run_benchmark(
        ["deterministic", "slow"],
        golden=golden_path,
        output_path=output_path,
        model_timeout_seconds=0.01,
    )

    assert benchmark["scorecards"]["deterministic"]["status"] == "completed"
    assert {
        key: benchmark["scorecards"]["slow"][key]
        for key in ("status", "model", "reason", "per_run")
    } == {
        "status": "incomplete",
        "model": "slow",
        "reason": "timeout",
        "per_run": [],
    }
    assert benchmark["scorecards"]["slow"]["skip_reason"] == "timeout"
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["scorecards"]["slow"] == benchmark["scorecards"]["slow"]
    assert "samples" not in persisted["scorecards"]["deterministic"]["per_run"][0]
    assert "incomplete (timeout)" in render_comparison(benchmark)


def test_benchmark_marks_zero_sample_provider_with_a_specific_skip_reason(tmp_path, monkeypatch):
    golden_path = tmp_path / "golden.yml"
    golden_path.write_text(yaml.safe_dump(_golden_cases()), encoding="utf-8")
    monkeypatch.setattr("evals.benchmark._provider_run", lambda *_args, **_kwargs: [])

    benchmark = run_benchmark(
        ["zero"],
        golden=golden_path,
        output_path=tmp_path / "benchmark.json",
    )

    zero = benchmark["scorecards"]["zero"]
    assert zero["status"] == "skipped"
    assert zero["skip_reason"] == "zero_samples"
    assert "skipped (zero_samples)" in render_comparison(benchmark)
