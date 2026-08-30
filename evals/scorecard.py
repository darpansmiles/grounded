"""Render and persist evaluation scorecards from fresh golden-set traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.metrics import compute_scorecard
from evals.runner import run_evals
from evals.trace import read_traces


def _display_value(metric: str, value: Any) -> str:
    """Format rate values for people while leaving the scorecard data untouched."""
    if "rate" in metric and isinstance(value, (int, float)):
        return f"{value:.1%}"
    return str(value)


def render_scorecard(scorecard: dict[str, Any]) -> str:
    """Render one model's quality and operational metrics as a markdown table."""
    rows = [
        ("model", scorecard["model"]),
        *scorecard["counts"].items(),
        *scorecard["quality"].items(),
        ("latency_ms.p50", scorecard["operational"]["latency_ms"]["p50"]),
        ("latency_ms.p95", scorecard["operational"]["latency_ms"]["p95"]),
        ("latency_ms.max", scorecard["operational"]["latency_ms"]["max"]),
        ("cost_usd.total", scorecard["operational"]["cost_usd"]["total"]),
        ("cost_usd.mean", scorecard["operational"]["cost_usd"]["mean"]),
        ("known_gap_cases", ", ".join(scorecard["known_gap_cases"]) or "none"),
    ]
    lines = ["| metric | value |", "| --- | --- |"]
    lines.extend(f"| {metric} | {_display_value(metric, value)} |" for metric, value in rows)
    return "\n".join(lines)


def write_scorecard(
    scorecard: dict[str, Any], path: str | Path = "evals/scorecard.json"
) -> None:
    """Persist a structured scorecard for later comparison across model versions."""
    scorecard_path = Path(path)
    scorecard_path.parent.mkdir(parents=True, exist_ok=True)
    scorecard_path.write_text(
        json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_scorecard(
    golden_path: str | Path = "evals/golden.yml",
    traces_path: str | Path = "evals/traces.jsonl",
    scorecard_path: str | Path = "evals/scorecard.json",
) -> dict[str, Any]:
    """Run fresh evaluations, score only that run, print, and persist the scorecard."""
    existing_trace_count = len(read_traces(traces_path))
    run_evals(golden_path, traces_path)
    fresh_traces = read_traces(traces_path)[existing_trace_count:]
    scorecard = compute_scorecard(fresh_traces)
    print(render_scorecard(scorecard))
    write_scorecard(scorecard, scorecard_path)
    return scorecard


if __name__ == "__main__":
    run_scorecard()
