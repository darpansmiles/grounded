"""Run every available dataset spine while releasing each pack's services."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.orchestration import dataset_names
from packlib import load_pack, source_is_available


class SourceUnavailable(RuntimeError):
    """A pack's intentionally local third-party source has not been fetched."""


def run_spine_queue(datasets: list[str], run_dataset: Callable[[str], None]) -> list[str]:
    """Run available packs in order, retaining skip-with-status behavior."""
    completed: list[str] = []
    for dataset in datasets:
        try:
            run_dataset(dataset)
        except SourceUnavailable as exc:
            print(exc)
            continue
        completed.append(dataset)
    return completed


def _run_dataset(dataset: str) -> None:
    """Run one pack and always release its Compose project before the next."""
    pack = load_pack(dataset)
    if not source_is_available(pack):
        raise SourceUnavailable(
            f"{dataset}: skipped — source not present; see datasets/{dataset}/source/README.md"
        )
    try:
        print(f"\n=== Grounded spine-all: {dataset} ===")
        subprocess.run(["make", "spine", f"DATASET={dataset}"], check=True)
    finally:
        subprocess.run(["make", "down", f"DATASET={dataset}"], check=False)


if __name__ == "__main__":
    run_spine_queue(dataset_names(), _run_dataset)
