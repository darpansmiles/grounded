from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.metrics import compute_scorecard
from evals.runner import run_evals
from evals.scorecard import render_scorecard, write_scorecard
from evals.trace import read_traces
from scripts.seed_duckdb import seed_database


_GOLDEN_PATH = Path(__file__).resolve().parents[1] / "evals" / "golden.yml"


@pytest.fixture()
def scorecard_and_traces(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")
    traces_path = tmp_path / "traces.jsonl"
    run_evals(_GOLDEN_PATH, traces_path)
    traces = read_traces(traces_path)
    return compute_scorecard(traces), traces


def test_scorecard_has_pm_authored_quality_rates(scorecard_and_traces):
    scorecard, _ = scorecard_and_traces

    assert scorecard["model"] == "deterministic-planner"
    assert scorecard["counts"] == {
        "total_cases": 8,
        "non_gap_cases": 7,
        "known_gaps": 1,
        "unexpected_failures": 0,
    }
    assert scorecard["quality"] == {
        "correctness_rate_excl_gaps": 1.0,
        "correctness_rate_incl_gaps": 0.875,
        "citation_correctness_excl_gaps": 1.0,
        "citation_correctness_incl_gaps": 0.75,
        "policy_compliance_excl_gaps": 1.0,
        "appropriate_refusal_rate": 1.0,
        "over_refusals": 1,
    }


def test_paraphrase_is_the_single_over_refusal(scorecard_and_traces):
    scorecard, traces = scorecard_and_traces

    over_refusals = [
        trace
        for trace in traces
        if trace["expected"]["type"] != "refuse" and trace["plan"]["tool"] == "refuse"
    ]
    assert scorecard["quality"]["over_refusals"] == 1
    assert [trace["case_id"] for trace in over_refusals] == ["paraphrase-known-gap"]
    assert scorecard["counts"]["unexpected_failures"] == 0


def test_operational_metrics_are_distributions_with_zero_deterministic_cost(scorecard_and_traces):
    scorecard, _ = scorecard_and_traces

    latency = scorecard["operational"]["latency_ms"]
    assert latency["max"] >= latency["p95"] >= latency["p50"] >= 0
    assert scorecard["operational"]["cost_usd"] == {"total": 0.0, "mean": 0.0}


def test_scorecard_renders_and_persists_json(scorecard_and_traces, tmp_path):
    scorecard, _ = scorecard_and_traces

    rendered = render_scorecard(scorecard)
    for metric_name in scorecard["quality"]:
        assert metric_name in rendered
    assert rendered.startswith("| metric | value |")

    output_path = tmp_path / "scorecard.json"
    write_scorecard(scorecard, output_path)
    assert json.loads(output_path.read_text(encoding="utf-8")) == scorecard
