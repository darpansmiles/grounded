"""Render publishable four-dimension result cards from offline review JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import yaml

_PACKS: dict[str, dict[str, str]] = {
    "adventureworks": {
        "title": "AdventureWorks",
        "capture": "aw-final-r3.jsonl",
        "review": "aw-final-r3-review-069.json",
        "card": "benchmark-adventureworks-runs3.md",
        "dataset_path": "datasets/adventureworks",
        "prose": "Correct is conditional on answered in-catalog cases. Wrong, interface, and\nevidence use all 213 in-catalog cases. Policy has 15 applicable cases.",
    },
    "tpch": {
        "title": "TPC-H",
        "capture": "tpch-final-r3.jsonl",
        "review": "tpch-final-r3-review-069.json",
        "card": "benchmark-tpch-runs3.md",
        "dataset_path": "datasets/tpch",
        "prose": "Correct is conditional on answered in-catalog cases. Wrong, interface, and\nevidence use all 228 in-catalog cases. Policy has 3 applicable cases.",
    },
    "spider_world1": {
        "title": "Spider world_1",
        "capture": "spider-final-r3.jsonl",
        "review": "spider-final-r3-review-069.json",
        "card": "benchmark-spider_world1-runs3.md",
        "dataset_path": "datasets/spider_world1",
        "prose": "Correct is conditional on answered in-catalog cases. Wrong, interface, and\nevidence use all 93 in-catalog cases. Policy has 3 applicable cases.",
    },
    "bird_ca_schools": {
        "title": "BIRD california_schools",
        "capture": "bird-final-r3.jsonl",
        "review": "bird-final-r3-review-069.json",
        "card": "benchmark-bird_ca_schools-runs3.md",
        "dataset_path": "datasets/bird_ca_schools",
        "prose": "Correct is conditional on answered in-catalog cases. Wrong, interface, and\nevidence use all 69 in-catalog cases. There are no applicable policy cases.",
    },
    "fixture": {
        "title": "Fixture",
        "capture": "fixture-final-r3.jsonl",
        "review": "fixture-final-r3-review-069.json",
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


def _display_model(model: str) -> str:
    return model.removesuffix(":latest")


def _rate_cell(value: dict[str, Any]) -> str:
    numerator = value.get("numerator")
    denominator = value.get("denominator")
    rate = value.get("rate")
    if denominator in (None, 0) or rate is None:
        if rate is not None or numerator not in (None, 0) or denominator not in (None, 0):
            raise ValueError(f"Invalid NA rate: {value!r}")
        return "NA (0/0)"
    if not isinstance(numerator, int) or not isinstance(denominator, int):
        raise TypeError(f"Invalid rate denominator: {value!r}")
    if not isinstance(rate, (int, float)) or not 0 <= numerator <= denominator:
        raise ValueError(f"Invalid rate value: {value!r}")
    if not math.isclose(float(rate), numerator / denominator, rel_tol=0, abs_tol=1e-12):
        raise ValueError(f"Rate does not equal numerator/denominator: {value!r}")
    return f"{float(rate) * 100:.1f}% ({numerator}/{denominator})"


def _capture_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as capture_file:
        for chunk in iter(lambda: capture_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _capture_inventory(path: Path) -> dict[str, Any]:
    """Read the manifest and observed case/run matrix without loading JSONL."""
    manifest: dict[str, Any] | None = None
    models: dict[str, dict[str, list[int]]] = {}
    with path.open(encoding="utf-8") as capture_file:
        for line in capture_file:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("record_type") == "manifest":
                manifest = item
                continue
            if item.get("record_type") != "case":
                continue
            model = item.get("model")
            case_id = item.get("case_id")
            run = item.get("run")
            if not isinstance(model, str) or not isinstance(case_id, str) or not isinstance(run, int):
                raise TypeError("Capture case lacks a valid model, case_id, or run.")
            models.setdefault(model, {}).setdefault(case_id, []).append(run)
    if not isinstance(manifest, dict):
        raise TypeError("Capture has no manifest.")
    runs = manifest.get("runs")
    roster = manifest.get("models")
    if not isinstance(runs, int) or runs < 1:
        raise ValueError("Capture manifest has no positive runs value.")
    if not isinstance(roster, list) or not all(isinstance(model, str) for model in roster):
        raise ValueError("Capture manifest has no valid model roster.")
    return {
        "expected_runs": list(range(1, runs + 1)),
        "expected_models": sorted(roster),
        "case_ids": sorted({case_id for cases in models.values() for case_id in cases}),
        "models": {
            model: {
                case_id: sorted(case_runs)
                for case_id, case_runs in sorted(cases.items())
            }
            for model, cases in sorted(models.items())
        },
    }


def _review_sample_inventory(review: dict[str, Any]) -> dict[str, dict[str, list[int]]]:
    """Extract the scored samples' independent model/case/run inventory."""
    inventory: dict[str, dict[str, list[int]]] = {}
    for model, model_review in review.get("models", {}).items():
        if not isinstance(model, str) or not isinstance(model_review, dict):
            raise TypeError("Review has an invalid model entry.")
        for sample in model_review.get("samples", []):
            if not isinstance(sample, dict):
                raise TypeError(f"Review sample for {model!r} is invalid.")
            case_id = sample.get("case_id")
            run = sample.get("run")
            if not isinstance(case_id, str) or not isinstance(run, int):
                raise TypeError(f"Review sample for {model!r} lacks case_id/run.")
            inventory.setdefault(model, {}).setdefault(case_id, []).append(run)
    return {
        model: {
            case_id: sorted(runs) for case_id, runs in sorted(case_runs.items())
        }
        for model, case_runs in sorted(inventory.items())
    }


def _dataset_tree_at_revision(revision: str, dataset_path: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"{revision}:{dataset_path}"],
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _expected_case_ids_at_revision(revision: str, dataset_path: str) -> list[str]:
    completed = subprocess.run(
        ["git", "show", f"{revision}:{dataset_path}/golden.yml"],
        capture_output=True,
        check=True,
        text=True,
    )
    payload = yaml.safe_load(completed.stdout)
    if not isinstance(payload, list) or not all(
        isinstance(case, dict) and isinstance(case.get("case_id"), str) for case in payload
    ):
        raise ValueError(f"{dataset_path}/golden.yml has no valid case-id inventory.")
    return sorted(case["case_id"] for case in payload)


def _validate_provenance(review: dict[str, Any], capture_path: Path) -> dict[str, Any]:
    provenance = review.get("provenance")
    if not isinstance(provenance, dict):
        raise TypeError("Review has no recorded provenance.")
    recorded_hash = provenance.get("capture_sha256")
    if not isinstance(recorded_hash, str) or _capture_sha256(capture_path) != recorded_hash:
        raise ValueError("Capture SHA-256 does not match the reviewed scoring input.")
    if provenance.get("capture_filename") != capture_path.name:
        raise ValueError("Capture filename does not match the reviewed scoring input.")
    scoring_commit = provenance.get("scoring_commit")
    if not isinstance(scoring_commit, str) or not scoring_commit:
        raise ValueError("Review has no recorded scoring commit.")
    dataset_identity = provenance.get("dataset_identity")
    dataset = review.get("dataset")
    expected_path = f"datasets/{dataset}"
    if (
        not isinstance(dataset_identity, dict)
        or dataset_identity.get("name") != dataset
        or dataset_identity.get("path") != expected_path
        or not isinstance(dataset_identity.get("tree"), str)
    ):
        raise ValueError("Review dataset identity does not match the card dataset.")
    if _dataset_tree_at_revision(scoring_commit, expected_path) != dataset_identity["tree"]:
        raise ValueError("Recorded dataset tree does not match the scoring revision.")
    inventory = provenance.get("case_run_inventory")
    if not isinstance(inventory, dict) or inventory != _capture_inventory(capture_path):
        raise ValueError("Capture case/run inventory does not match the reviewed scoring input.")
    expected_runs = inventory.get("expected_runs")
    expected_models = inventory.get("expected_models")
    expected_cases = inventory.get("case_ids")
    model_inventory = inventory.get("models")
    if expected_runs != [1, 2, 3]:
        raise ValueError(f"Expected complete runs 1, 2, 3; found {expected_runs!r}.")
    if (
        not isinstance(expected_models, list)
        or not isinstance(expected_cases, list)
        or not expected_cases
        or not isinstance(model_inventory, dict)
    ):
        raise ValueError("Review has an incomplete case/run inventory.")
    if sorted(review.get("models", {})) != expected_models:
        raise ValueError("Review models do not match the capture roster.")
    declared_cases = provenance.get("expected_case_ids")
    if declared_cases != _expected_case_ids_at_revision(scoring_commit, expected_path):
        raise ValueError("Review expected-case inventory does not match the scored pack.")
    if expected_cases != declared_cases:
        raise ValueError("Capture is missing an expected case or contains an undeclared case.")
    if _review_sample_inventory(review) != model_inventory:
        raise ValueError("Scored samples do not reconcile to the capture inventory.")
    for model in expected_models:
        case_runs = model_inventory.get(model)
        if not isinstance(case_runs, dict) or sorted(case_runs) != expected_cases:
            raise ValueError(f"Incomplete case inventory for model {model!r}.")
        for case_id in expected_cases:
            if case_runs.get(case_id) != expected_runs:
                raise ValueError(
                    f"Incomplete runs for {model!r}/{case_id!r}: {case_runs.get(case_id)!r}."
                )
        model_review = review["models"].get(model)
        if not isinstance(model_review, dict) or model_review.get("valid") is not True:
            raise ValueError(f"Refusing to render invalid model {model!r}.")
        for sample in model_review.get("samples", []):
            if isinstance(sample, dict) and sample.get("valid") is False:
                raise ValueError(f"Refusing to render invalid record for model {model!r}.")
    return provenance


def render_card(
    review: dict[str, Any],
    *,
    capture_path: Path,
    review_path: Path,
    rendered_at_commit: str,
) -> str:
    """Render one result card from a self-tested offline-score review."""
    dataset = review.get("dataset")
    if dataset not in _PACKS:
        raise ValueError(f"No card configuration for dataset {dataset!r}")
    if review.get("evaluator_self_test", {}).get("passed") is not True:
        raise ValueError("Refusing to render a card without a passing evaluator self-test.")
    metadata = _PACKS[dataset]
    provenance = _validate_provenance(review, capture_path)
    dataset_identity = provenance["dataset_identity"]
    lines = [
        f"# {metadata['title']} benchmark result",
        "",
        f"- dataset: {metadata['title']}",
        "- runs: 3",
        "- evaluator self-test: passed",
        "- method: executed produced governed calls and raw-SQL controls, both compared with independently computed direct-SQL truth",
        f"- scoring commit: `{provenance['scoring_commit']}`",
        f"- rendered at commit: `{rendered_at_commit}`",
        f"- capture SHA-256: `{provenance['capture_sha256']}`",
        f"- dataset snapshot: `{dataset_identity['path']}` tree `{dataset_identity['tree']}`",
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
) -> list[Path]:
    """Render all five 069-reviewed cards only after every review validates."""
    revision = _short_revision()
    rendered_cards: list[tuple[Path, str]] = []
    for metadata in _PACKS.values():
        review_path = scores_dir / metadata["review"]
        capture_path = captures_dir / metadata["capture"]
        if not capture_path.is_file():
            raise FileNotFoundError(capture_path)
        review = json.loads(review_path.read_text(encoding="utf-8"))
        rendered = render_card(
            review,
            capture_path=capture_path,
            review_path=review_path,
            rendered_at_commit=revision,
        )
        output = results_dir / metadata["card"]
        rendered_cards.append((output, rendered))
    written: list[Path] = []
    for output, rendered in rendered_cards:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        written.append(output)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render runs=3 result cards from offline reviews.")
    parser.add_argument("--scores-dir", type=Path, default=Path(".grounded/scores"))
    parser.add_argument("--captures-dir", type=Path, default=Path(".grounded/captures"))
    parser.add_argument("--results-dir", type=Path, default=Path("evals/results"))
    arguments = parser.parse_args(argv)
    for path in render_all(
        scores_dir=arguments.scores_dir,
        captures_dir=arguments.captures_dir,
        results_dir=arguments.results_dir,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
