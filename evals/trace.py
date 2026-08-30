"""Trace schema and append-only JSONL storage for golden-set evaluations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Trace:
    trace_id: str
    timestamp: str
    case_id: str
    question: str
    role: str
    plan: dict[str, Any]
    answer_rows: list[dict[str, Any]]
    policy_applied: list[dict[str, Any]]
    verify_status: str | None
    lineage_citation: str | None
    latency_ms: float
    model: str
    cost_usd: float
    expected: dict[str, Any]
    checks: list[dict[str, str]]
    outcome: str
    known_gap: bool
    raw_model_output: str | None = None
    parsed_plan: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the trace with the persisted JSONL schema's exact keys."""
        return asdict(self)


def write_traces(traces: list[dict], path: str | Path = "evals/traces.jsonl") -> None:
    """Append one serialized trace per line without rewriting earlier traces."""
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as trace_file:
        for trace in traces:
            trace_file.write(json.dumps(trace, sort_keys=True) + "\n")


def read_traces(path: str | Path) -> list[dict]:
    """Read the append-only JSONL trace file for tests and later eval slices."""
    trace_path = Path(path)
    if not trace_path.exists():
        return []
    with trace_path.open(encoding="utf-8") as trace_file:
        return [json.loads(line) for line in trace_file if line.strip()]
