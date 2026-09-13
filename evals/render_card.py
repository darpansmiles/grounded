"""Render publishable four-dimension result cards from offline review JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

_PACKS: dict[str, dict[str, str]] = {
    "adventureworks": {
        "title": "AdventureWorks",
        "capture": "aw-final-r3.jsonl",
        "review": "aw-final-r3-review-066.json",
        "card": "benchmark-adventureworks-runs3.md",
        "dataset_path": "datasets/adventureworks",
        "prose": "Correct is conditional on answered in-catalog cases. Wrong, interface, and\nevidence use all 213 in-catalog cases. Policy has 15 applicable cases.",
    },
    "tpch": {
        "title": "TPC-H",
        "capture": "tpch-final-r3.jsonl",
        "review": "tpch-final-r3-review-066.json",
        "card": "benchmark-tpch-runs3.md",
        "dataset_path": "datasets/tpch",
        "prose": "Correct is conditional on answered in-catalog cases. Wrong, interface, and\nevidence use all 228 in-catalog cases. Policy has 3 applicable cases.",
    },
    "spider_world1": {
        "title": "Spider world_1",
        "capture": "spider-final-r3.jsonl",
        "review": "spider-final-r3-review-066.json",
        "card": "benchmark-spider_world1-runs3.md",
        "dataset_path": "datasets/spider_world1",
        "prose": "Correct is conditional on answered in-catalog cases. Wrong, interface, and\nevidence use all 93 in-catalog cases. Policy has 3 applicable cases.",
    },
    "bird_ca_schools": {
        "title": "BIRD california_schools",
        "capture": "bird-final-r3.jsonl",
        "review": "bird-final-r3-review-066.json",
        "card": "benchmark-bird_ca_schools-runs3.md",
        "dataset_path": "datasets/bird_ca_schools",
        "prose": "Correct is conditional on answered in-catalog cases. Wrong, interface, and\nevidence use all 69 in-catalog cases. There are no applicable policy cases.",
    },
    "fixture": {
        "title": "Fixture",
        "capture": "fixture-final-r3.jsonl",
        "review": "fixture-final-r3-review-066.json",
        "card": "benchmark-fixture-runs3.md",
        "dataset_path": "datasets/fixture",
        "prose": "This deterministic pack has 30 in-catalog cases per model. Its small\ndenominators make it a harness test surface, not a workload claim. Correct is\nconditional on answered in-catalog cases; policy has 3 applicable cases.\n\nApplicable denominators range from 3 to 30 cases per model, so the near-100%\ngoverned figures are low-N and should not be read as workload evidence.",
    },
}

_COLUMNS = (
    ("governed", "answer_correctness_when_answered"),
    ("governed", "wrong_answer_rate"),
    ("governed", "interface_compliance_rate"),
    ("governed", "policy_compliance_rate"),
    ("governed", "evidence_completeness_rate"),
    ("ungoverned", "answer_correctness_when_answered"),
    ("ungoverned", "wrong_answer_rate"),
)


def _short_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short=7", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _tree_revision(dataset_path: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{dataset_path}"],
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _display_model(model: str) -> str:
    return model.removesuffix(":latest")


def _rate_cell(value: dict[str, Any]) -> str:
    numerator = value.get("numerator")
    denominator = value.get("denominator")
    rate = value.get("rate")
    if denominator in (None, 0) or rate is None:
        return "NA (0/0)"
    if not isinstance(numerator, int) or not isinstance(denominator, int):
        raise TypeError(f"Invalid rate denominator: {value!r}")
    return f"{float(rate) * 100:.1f}% ({numerator}/{denominator})"


def render_card(
    review: dict[str, Any],
    *,
    capture_path: Path,
    review_path: Path,
    scoring_commit: str,
    dataset_tree: str,
) -> str:
    """Render one result card from a self-tested offline-score review."""
    dataset = review.get("dataset")
    if dataset not in _PACKS:
        raise ValueError(f"No card configuration for dataset {dataset!r}")
    if review.get("evaluator_self_test", {}).get("passed") is not True:
        raise ValueError("Refusing to render a card without a passing evaluator self-test.")
    metadata = _PACKS[dataset]
    capture_sha = hashlib.sha256(capture_path.read_bytes()).hexdigest()
    sample_runs = [
        sample.get("run", 0)
        for model in review.get("models", {}).values()
        for sample in model.get("samples", [])
        if isinstance(sample.get("run", 0), int)
    ]
    runs = max(sample_runs, default=0)
    if runs != 3:
        raise ValueError(f"Expected a runs=3 review, found runs={runs}.")
    lines = [
        f"# {metadata['title']} benchmark result",
        "",
        f"- dataset: {metadata['title']}",
        "- runs: 3",
        "- evaluator self-test: passed",
        "- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth",
        "- collection commit: `1f1f58a`",
        f"- scoring commit: `{scoring_commit}`",
        f"- capture SHA-256: `{capture_sha}`",
        f"- dataset snapshot: `{metadata['dataset_path']}` tree `{dataset_tree}`",
        (
            "- reproduction: "
            f"`.venv/bin/python -m evals.benchmark --dataset {dataset} --runs 3 "
            f"--capture-path .grounded/captures/{capture_path.name} && "
            f".venv/bin/python -m evals.compare --capture-path .grounded/captures/{capture_path.name} "
            f"--offline-output .grounded/scores/{review_path.name}`"
        ),
        "",
        metadata["prose"],
        "",
        "| Model | Gov. correct | Gov. wrong | Interface | Policy | Evidence | Raw SQL correct | Raw SQL wrong |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model_name in sorted(review["models"]):
        groups = review["models"][model_name].get("groups", {})
        in_catalog = groups.get("in_catalog")
        if not isinstance(in_catalog, dict):
            raise TypeError(f"{dataset}/{model_name} has no in_catalog group.")
        cells = [_rate_cell(in_catalog[arm][metric]) for arm, metric in _COLUMNS]
        lines.append(f"| {_display_model(model_name)} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def render_all(
    *, scores_dir: Path = Path(".grounded/scores"),
    captures_dir: Path = Path(".grounded/captures"),
    results_dir: Path = Path("evals/results"),
    scoring_commit: str | None = None,
) -> list[Path]:
    """Render all five 066-reviewed cards and return their output paths."""
    revision = scoring_commit or _short_revision()
    written: list[Path] = []
    for metadata in _PACKS.values():
        review_path = scores_dir / metadata["review"]
        capture_path = captures_dir / metadata["capture"]
        review = json.loads(review_path.read_text(encoding="utf-8"))
        rendered = render_card(
            review,
            capture_path=capture_path,
            review_path=review_path,
            scoring_commit=revision,
            dataset_tree=_tree_revision(metadata["dataset_path"]),
        )
        output = results_dir / metadata["card"]
        output.write_text(rendered, encoding="utf-8")
        written.append(output)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render runs=3 result cards from offline reviews.")
    parser.add_argument("--scores-dir", type=Path, default=Path(".grounded/scores"))
    parser.add_argument("--captures-dir", type=Path, default=Path(".grounded/captures"))
    parser.add_argument("--results-dir", type=Path, default=Path("evals/results"))
    parser.add_argument("--scoring-commit")
    arguments = parser.parse_args(argv)
    for path in render_all(
        scores_dir=arguments.scores_dir,
        captures_dir=arguments.captures_dir,
        results_dir=arguments.results_dir,
        scoring_commit=arguments.scoring_commit,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
