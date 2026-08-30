"""Deterministic statistical summaries over recorded benchmark samples."""

from __future__ import annotations

from math import comb
from random import Random

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 42


def bootstrap_rate_ci(values: list[bool]) -> dict[str, float]:
    """Return a seeded percentile 95% bootstrap interval for a binary rate."""
    if not values:
        return {"rate": 0.0, "lo": 0.0, "hi": 0.0}
    generator = Random(BOOTSTRAP_SEED)
    size = len(values)
    samples = sorted(
        sum(values[generator.randrange(size)] for _ in range(size)) / size
        for _ in range(BOOTSTRAP_RESAMPLES)
    )
    return {
        "rate": sum(values) / size,
        "lo": samples[int(0.025 * BOOTSTRAP_RESAMPLES)],
        "hi": samples[int(0.975 * BOOTSTRAP_RESAMPLES) - 1],
    }


def mcnemar_exact(left: list[bool], right: list[bool]) -> dict[str, float | int]:
    """Exact two-sided McNemar test for paired binary outcomes."""
    if len(left) != len(right):
        raise ValueError("McNemar vectors must have equal length")
    b = sum(not first and second for first, second in zip(left, right, strict=True))
    c = sum(first and not second for first, second in zip(left, right, strict=True))
    discordant = b + c
    tail = sum(comb(discordant, value) for value in range(min(b, c) + 1)) / 2**discordant if discordant else 1.0
    return {"b": b, "c": c, "p_value": min(1.0, 2 * tail)}


def run_variance(values: list[float]) -> float:
    """Population variance across recorded benchmark runs."""
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)
