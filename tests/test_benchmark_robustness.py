from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

from evals.benchmark import (
    DEFAULT_MODEL_TIMEOUT_SECONDS,
    DEFAULT_REQUEST_CONCURRENCY,
    resolve_model_timeout_seconds,
    resolve_request_concurrency,
    run_benchmark,
)
from evals.compare import _json_value, main, render_model_card
from evals.resources import ProcessResourceSampler
from models.provider import StubProvider


def test_card_values_with_date_datetime_and_decimal_serialize_to_json():
    value = {
        "day": date(2026, 8, 19),
        "timestamp": datetime(2026, 8, 19, 12, 30, tzinfo=UTC),
        "revenue": Decimal("1185.00"),
    }

    serialized = json.dumps(_json_value(value), sort_keys=True)

    assert json.loads(serialized) == {
        "day": "2026-08-19",
        "timestamp": "2026-08-19T12:30:00+00:00",
        "revenue": 1185.0,
    }


def test_model_timeout_precedence_is_cli_then_environment_then_default(monkeypatch):
    monkeypatch.delenv("GROUNDED_MODEL_TIMEOUT", raising=False)
    assert DEFAULT_MODEL_TIMEOUT_SECONDS == 1800
    assert resolve_model_timeout_seconds() == 1800.0

    monkeypatch.setenv("GROUNDED_MODEL_TIMEOUT", "3600")
    assert resolve_model_timeout_seconds() == 3600.0
    assert resolve_model_timeout_seconds(1200) == 1200.0


def test_request_concurrency_precedence_is_cli_then_environment_then_default(monkeypatch):
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    assert DEFAULT_REQUEST_CONCURRENCY == 2
    assert resolve_request_concurrency() == 2

    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "4")
    assert resolve_request_concurrency() == 4
    assert resolve_request_concurrency(3) == 3


class _StubSampler:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> dict:
        assert self.started
        return {
            "available": True,
            "cpu_pct": {"mean": 12.5},
            "mem_rss_mb": {"mean": 48.0, "peak": 64.0},
        }


def test_benchmark_persists_deterministic_timing_and_resources(tmp_path):
    golden = tmp_path / "golden.yml"
    golden.write_text(
        """- case_id: refuse
  question: Forecast revenue
  role: viewer
  expected_plan: {tool: refuse, args: {}}
  expect: {type: refuse}
""",
        encoding="utf-8",
    )
    monotonic_values = iter([0.0, 1.0, 4.0, 5.0])
    wall_clock_values = iter(
        [
            datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
            datetime(2026, 8, 19, 12, 0, 5, tzinfo=UTC),
        ]
    )

    benchmark = run_benchmark(
        ["stub"],
        runs=1,
        golden=golden,
        provider_factory=lambda _model: StubProvider({}),
        output_path=tmp_path / "benchmark.json",
        monotonic_clock=lambda: next(monotonic_values),
        wall_clock=lambda: next(wall_clock_values),
        resource_sampler_factory=_StubSampler,
    )

    assert benchmark["timing"] == {
        "started_at": "2026-08-19T12:00:00+00:00",
        "ended_at": "2026-08-19T12:00:05+00:00",
        "total_duration_s": 5.0,
    }
    assert benchmark["scorecards"]["stub"]["timing"] == {"duration_s": 3.0}
    assert benchmark["scorecards"]["stub"]["resources"]["mem_rss_mb"]["peak"] == 64.0
    rendered = render_model_card(
        {
            "models": ["stub"],
            "timing": benchmark["timing"],
            "model_cards": {
                "stub": {
                    "status": "skipped",
                    "timing": benchmark["scorecards"]["stub"]["timing"],
                    "resources": benchmark["scorecards"]["stub"]["resources"],
                }
            },
        }
    )
    assert "duration 5.000s" in rendered
    assert "CPU mean 12.5%; RSS mean 48.0 MB, peak 64.0 MB" in rendered


def test_resource_sampler_degrades_to_timing_only_without_psutil(monkeypatch):
    monkeypatch.setattr("evals.resources.psutil", None)

    sampler = ProcessResourceSampler()
    sampler.start()

    assert sampler.stop() == {"available": False, "reason": "psutil unavailable"}


def test_comparison_cli_reports_missing_database_without_traceback(monkeypatch, capsys):
    import duckdb

    monkeypatch.setattr(
        "evals.compare.run_comparison",
        lambda **_kwargs: (_ for _ in ()).throw(duckdb.IOException("missing")),
    )

    assert main(["--dataset", "fixture"]) == 2

    captured = capsys.readouterr()
    assert "make spine DATASET=fixture" in captured.err
    assert "Traceback" not in captured.err
