"""Queue pack benchmarks unattended and persist a resumable summary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from packlib import PACKS_DIRECTORY, load_pack, source_is_available

DEFAULT_SUMMARY_PATH = Path("evals/results/benchmark-all-summary.json")


class SourceUnavailable(RuntimeError):
    """A third-party local source has not yet been fetched for its pack."""


def dataset_names() -> list[str]:
    """Return every shipped pack, excluding the deliberately invalid template."""
    return sorted(
        manifest.parent.name
        for manifest in PACKS_DIRECTORY.glob("*/pack.yml")
        if manifest.parent.name != "_template"
    )


def run_benchmark_queue(
    datasets: list[str],
    run_dataset: Callable[[str], list[str]],
    summary_path: str | Path,
    *,
    resume: bool = True,
) -> dict[str, Any]:
    """Run every pack in order, retaining prior completed cards on resume."""
    output = Path(summary_path)
    previous: dict[str, Any] = {}
    if resume and output.is_file():
        previous = json.loads(output.read_text(encoding="utf-8")).get("datasets", {})
    results: dict[str, Any] = {}
    for dataset in datasets:
        prior = previous.get(dataset)
        if prior and prior.get("status") == "completed" and all(
            Path(path).is_file() for path in prior.get("cards", [])
        ):
            results[dataset] = {**prior, "status": "resumed"}
            continue
        try:
            results[dataset] = {"status": "completed", "cards": run_dataset(dataset)}
        except SourceUnavailable as exc:
            results[dataset] = {"status": "skipped", "reason": str(exc), "cards": []}
        except Exception as exc:  # noqa: BLE001 - one pack must not stop the unattended queue
            results[dataset] = {"status": "failed", "reason": str(exc), "cards": []}
    summary = {"datasets": results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _run_dataset(dataset: str) -> list[str]:
    """Bring up one pack's containers, benchmark it, and always tear them down."""
    pack = load_pack(dataset)
    if not source_is_available(pack):
        raise SourceUnavailable(
            f"{dataset}: skipped — source not present; see datasets/{dataset}/source/README.md"
        )
    try:
        if pack.source.type == "postgres":
            subprocess.run(["make", "source-up", f"DATASET={dataset}"], check=True)
        if pack.semantics and pack.semantics.backend == "cube":
            subprocess.run(["make", "cube-up", f"DATASET={dataset}"], check=True)
        subprocess.run(["make", "preflight-benchmark", f"DATASET={dataset}"], check=True)
        results_dir = Path("evals/results")
        before = set(results_dir.glob(f"benchmark-{dataset}-*.json"))
        completed = subprocess.run(
            [sys.executable, "-m", "evals.compare", "--dataset", dataset],
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(f"benchmark command exited {completed.returncode}")
        return [str(path) for path in sorted(set(results_dir.glob(f"benchmark-{dataset}-*.json")) - before)]
    finally:
        subprocess.run(["make", "down", f"DATASET={dataset}"], check=False)


def _render_summary(summary: dict[str, Any]) -> str:
    lines = ["# Grounded benchmark-all summary", "", "| dataset | status | cards |", "| --- | --- | --- |"]
    for dataset, result in summary["datasets"].items():
        status = result["status"]
        if result.get("reason"):
            status = f"{status} — {result['reason']}"
        lines.append(f"| {dataset} | {status} | {', '.join(result.get('cards', [])) or '—'} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run every Grounded pack benchmark unattended.")
    parser.add_argument("--summary", default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--no-resume", action="store_true")
    arguments = parser.parse_args()
    summary = run_benchmark_queue(
        dataset_names(), _run_dataset, arguments.summary, resume=not arguments.no_resume
    )
    Path(arguments.summary).with_suffix(".md").write_text(_render_summary(summary), encoding="utf-8")
    print(_render_summary(summary), end="")
