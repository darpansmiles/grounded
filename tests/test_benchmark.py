from __future__ import annotations

import json
import time

import yaml

from evals.benchmark import (
    CAPTURE_ROW_PREVIEW_LIMIT,
    CaptureWriter,
    render_comparison,
    run_benchmark,
)
from evals.offline_scoring import rows_content_hash
from evals.routing import score_routing
from models.provider import ProviderUnavailable, StubProvider
from scripts.seed_duckdb import seed_database

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


def test_capture_path_persists_executed_governed_and_ungoverned_records(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    database = tmp_path / "grounded.duckdb"
    seed_database(str(database))
    golden_path = tmp_path / "golden.yml"
    capture_path = tmp_path / "capture.jsonl"
    metric_plan = {
        "tool": "query_metric",
        "args": {
            "metric": "revenue",
            "dimensions": ["category"],
            "filters": {"order_month": "last_month"},
        },
    }
    policy_plan = {
        "tool": "check_policy",
        "args": {"target": "customers.email", "role": "viewer"},
    }
    refusal_plan = {"tool": "refuse", "args": {}}
    cases = [
        {
            "case_id": "metric",
            "question": "Revenue by category",
            "role": "viewer",
            "expected_plan": metric_plan,
            "expect": {"type": "metric"},
        },
        {
            "case_id": "policy",
            "question": "What policy protects email?",
            "role": "viewer",
            "expected_plan": policy_plan,
            "expect": {"type": "policy", "decision": "mask"},
        },
        {
            "case_id": "refusal",
            "question": "Forecast revenue",
            "role": "viewer",
            "expected_plan": refusal_plan,
            "expect": {"type": "refuse"},
        },
    ]
    golden_path.write_text(yaml.safe_dump(cases), encoding="utf-8")

    class CaptureProvider:
        def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
            del temperature
            if system.startswith("Answer the user's question by returning one SQL"):
                return "SELECT 1 AS raw_value"
            return json.dumps(
                {
                    "Revenue by category": metric_plan,
                    "What policy protects email?": policy_plan,
                    "Forecast revenue": refusal_plan,
                }[user]
            )

    benchmark = run_benchmark(
        ["capture-stub"],
        runs=1,
        golden=golden_path,
        provider_factory=lambda _model: CaptureProvider(),
        output_path=tmp_path / "benchmark.json",
        capture_path=capture_path,
        db_path=str(database),
    )

    records = [json.loads(line) for line in capture_path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["record_type"] == "manifest"
    assert records[0]["schema_version"] == 2
    by_case = {record["case_id"]: record for record in records[1:]}
    metric = by_case["metric"]
    assert metric["governed_executed"] is True
    assert metric["governed_rows"]
    assert metric["governed_row_count"] == len(metric["governed_rows"])
    assert isinstance(metric["governed_rows_hash"], str)
    assert "governed_response" not in metric
    assert metric["policy_decisions"] == []
    assert metric["evidence"]["lineage_citation"]
    assert metric["ungoverned_sql"] == "SELECT 1 AS raw_value"
    assert metric["ungoverned_rows"] == [{"raw_value": 1}]
    assert metric["ungoverned_row_count"] == 1
    assert isinstance(metric["ungoverned_rows_hash"], str)
    assert metric["ungoverned_error"] is None
    assert by_case["policy"]["governed_executed"] is True
    assert by_case["policy"]["policy_decisions"][0]["decision"] == "mask"
    assert by_case["refusal"]["governed_executed"] is False
    assert by_case["refusal"]["ungoverned"]["schema_break"] is False
    assert benchmark["capture_path"] == str(capture_path)


def test_capture_writer_bounds_large_rows_but_retains_count_and_full_content_hash(tmp_path):
    capture_path = tmp_path / "capture.jsonl"
    rows = [{"category": f"category-{index}", "revenue": index} for index in range(137)]
    record = {
        "case_id": "large-result",
        "expected_plan": _METRIC_PLAN,
        "governed_rows": rows,
        "governed_response": {"answer_rows": rows, "large_duplicate": rows},
        "ungoverned_rows": rows,
        "ungoverned": {"raw_sql": "SELECT 1", "rows": rows, "schema_break": False},
    }
    writer = CaptureWriter(capture_path, {"dataset": "fixture"})
    writer.write(record)

    persisted = [json.loads(line) for line in capture_path.open(encoding="utf-8")][1]
    expected_hash = rows_content_hash(rows, alias_map={})
    assert persisted["governed_rows"] == rows[:CAPTURE_ROW_PREVIEW_LIMIT]
    assert persisted["governed_row_count"] == len(rows)
    assert persisted["governed_rows_hash"] == expected_hash
    assert "governed_response" not in persisted
    assert persisted["ungoverned_rows"] == rows[:CAPTURE_ROW_PREVIEW_LIMIT]
    assert persisted["ungoverned_row_count"] == len(rows)
    assert persisted["ungoverned_rows_hash"] == expected_hash
    assert persisted["ungoverned"]["rows"] == rows[:CAPTURE_ROW_PREVIEW_LIMIT]
    assert persisted["ungoverned"]["row_count"] == len(rows)
    assert persisted["ungoverned"]["rows_hash"] == expected_hash
