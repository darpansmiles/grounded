"""Merge disjoint partial model-card runs without inventing a new measurement."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.compare import render_model_card


def _dataset(card: dict[str, Any]) -> str:
    dataset = card.get("dataset")
    if not isinstance(dataset, str) or not dataset:
        raise ValueError("Each partial card must name its dataset")
    return dataset


def merge_model_cards(cards: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge same-dataset cards only when their model sets are disjoint.

    A merged timing block retains the individual measurements and reports their
    duration sum; that sum is work performed, not claimed wall-clock elapsed.
    """
    if not cards:
        raise ValueError("At least one partial model card is required")
    dataset = _dataset(cards[0])
    models: list[str] = []
    model_cards: dict[str, Any] = {}
    partial_timings: list[dict[str, Any]] = []
    for card in cards:
        if _dataset(card) != dataset:
            raise ValueError("Partial cards must use the same dataset")
        for model in card.get("models", []):
            if model in model_cards:
                raise ValueError(f"Partial cards overlap on model {model!r}")
            models.append(model)
            model_cards[model] = card["model_cards"][model]
        timing = card.get("timing")
        if not isinstance(timing, dict):
            raise TypeError("Partial cards must contain 046 timing metadata")
        partial_timings.append(timing)
    first = cards[0]
    merged = {
        key: value
        for key, value in first.items()
        if key not in {"models", "model_cards", "timing"}
    }
    merged.update(
        {
            "models": models,
            "model_cards": model_cards,
            "timing": {
                "started_at": min(timing["started_at"] for timing in partial_timings),
                "ended_at": max(timing["ended_at"] for timing in partial_timings),
                "total_duration_s": sum(
                    float(timing["total_duration_s"]) for timing in partial_timings
                ),
                "partial_runs": partial_timings,
                "duration_note": "total_duration_s is the sum of independent partial-run durations, not elapsed wall time across any gaps.",
            },
        }
    )
    return merged


def merge_card_files(paths: list[str | Path], output_path: str | Path) -> dict[str, Any]:
    """Read persisted result records, merge their cards, and write one result record."""
    records = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    cards = [record.get("model_card", record) for record in records]
    if not all(isinstance(card, dict) for card in cards):
        raise ValueError("Each input must be a model-card JSON record")
    merged = merge_model_cards(cards)
    result = {
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "dataset": merged["dataset"],
            "models": merged["models"],
            "merged_from": [str(path) for path in paths],
        },
        "model_card": merged,
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(
        "# Grounded merged benchmark result\n\n" + render_model_card(merged) + "\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge disjoint partial Grounded model cards.")
    parser.add_argument("--output", required=True)
    parser.add_argument("cards", nargs="+")
    arguments = parser.parse_args()
    merge_card_files(arguments.cards, arguments.output)
