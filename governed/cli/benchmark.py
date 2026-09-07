"""Optional benchmark hook for the guided tour."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

Input = Callable[[str], str]
Output = Callable[[str], None]
CommandRunner = Callable[..., Any]


def offer_benchmark(
    dataset: str,
    model: str,
    *,
    input_func: Input = input,
    output: Output = print,
    runner: CommandRunner = subprocess.run,
) -> int:
    """Run the existing measured comparison only after explicit consent."""
    try:
        answer = input_func("\nPart 3 of 3 · The proof (optional). Run the measured benchmark now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer not in {"y", "yes"}:
        output("Benchmark skipped. The interactive comparison above is one observation, not a scorecard.")
        return 0
    output(f"Running the existing governed-versus-ungoverned benchmark for {model}...")
    try:
        result = runner(["make", "benchmark", f"DATASET={dataset}", f"GROUNDED_MODELS={model}"], check=False)
    except OSError:
        result = None
    if result is None or result.returncode != 0:
        output("Benchmark did not complete. The tour can still clean up safely.")
        return 2
    output("Benchmark complete. Its scorecard was printed above and persisted by the existing evaluator.")
    return 0
