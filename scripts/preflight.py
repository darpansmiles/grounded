"""Fail fast with actionable prerequisites for Grounded spine and benchmark runs."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx
import yaml

from evals.roster import model_roster
from packlib import Pack, load_pack
from scripts.check_source_secret import source_dsn_is_configured


@dataclass(frozen=True)
class PreflightIssue:
    """One concise prerequisite failure and its exact remediation command."""

    problem: str
    remedy: str

    def render(self) -> str:
        return f"{self.problem}. Fix: {self.remedy}"


CommandRunner = Callable[..., Any]
HttpGet = Callable[..., Any]


def _command_succeeds(command: list[str], runner: CommandRunner) -> bool:
    try:
        result = runner(command, capture_output=True, check=False, text=True)
    except OSError:
        return False
    return result.returncode == 0


def _cube_model_names(pack: Pack) -> set[str]:
    """Read the Cube names declared by this pack without querying its data."""
    if pack.semantics is None or pack.semantics.cube is None:
        return set()
    names: set[str] = set()
    for model_path in (pack.semantics.cube / "model").glob("*.y*ml"):
        document = yaml.safe_load(model_path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            continue
        for cube in document.get("cubes", []):
            if isinstance(cube, dict) and isinstance(cube.get("name"), str):
                names.add(cube["name"])
    return names


def _cube_is_pointed_at_pack(
    pack: Pack,
    http_get: HttpGet,
    *,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Check Cube readiness and that metadata includes the active pack's model."""
    if attempts < 1:
        raise ValueError("attempts must be at least one")
    base_url = os.environ.get("GROUNDED_CUBE_URL", "http://localhost:4000/cubejs-api/v1")
    expected = _cube_model_names(pack)
    for attempt in range(attempts):
        try:
            ready = http_get("http://localhost:4000/readyz", timeout=3.0)
            ready.raise_for_status()
            metadata = http_get(f"{base_url.rstrip('/')}/meta", timeout=3.0)
            metadata.raise_for_status()
            payload = metadata.json()
        except (httpx.HTTPError, ValueError):
            if attempt + 1 < attempts:
                sleep(1.0)
            continue
        served = {
            cube.get("name")
            for cube in payload.get("cubes", [])
            if isinstance(cube, dict) and isinstance(cube.get("name"), str)
        } if isinstance(payload, dict) else set()
        if expected and expected <= served:
            return True
        if attempt + 1 < attempts:
            sleep(1.0)
    return False


def _model_tag_aliases(model: str) -> set[str]:
    """Treat a bare Ollama model name and its implicit :latest tag as equal."""
    if model.endswith(":latest"):
        return {model, model.removesuffix(":latest")}
    if ":" not in model:
        return {model, f"{model}:latest"}
    return {model}


def _missing_models(runner: CommandRunner, models: list[str]) -> list[str]:
    try:
        result = runner(["ollama", "list"], capture_output=True, check=False, text=True)
    except OSError:
        return models
    if result.returncode:
        return models
    installed = {line.split()[0] for line in result.stdout.splitlines()[1:] if line.split()}
    return [
        model
        for model in models
        if not _model_tag_aliases(model).intersection(installed)
    ]


def check_preflight(
    dataset: str,
    run: str,
    *,
    command_runner: CommandRunner = subprocess.run,
    http_get: HttpGet = httpx.get,
    models: list[str] | None = None,
) -> list[PreflightIssue]:
    """Return all unmet prerequisites for one selected run path, without raising."""
    pack = load_pack(dataset)
    issues: list[PreflightIssue] = []
    if not _command_succeeds(["docker", "info"], command_runner):
        issues.append(
            PreflightIssue(
                "Docker Desktop is not running",
                "start Docker Desktop, then retry",
            )
        )

    if run == "spine":
        if pack.source.type == "postgres" and not source_dsn_is_configured(dataset):
            issues.append(
                PreflightIssue(
                    f"{pack.source.dsn_env} is not configured",
                    f"{pack.source.dsn_env}=... make set-secret",
                )
            )
        return issues

    if not pack.destination.path.is_file():
        issues.append(
            PreflightIssue(
                f"Dataset database is missing: {pack.destination.path}",
                f"make spine DATASET={dataset}",
            )
        )
    if pack.semantics and pack.semantics.backend == "cube" and not _cube_is_pointed_at_pack(pack, http_get):
        issues.append(
            PreflightIssue(
                f"Cube is not serving dataset {dataset}",
                f"make cube-up DATASET={dataset}",
            )
        )
    missing_models = _missing_models(command_runner, models or model_roster())
    if missing_models:
        issues.append(
            PreflightIssue(
                f"Ollama is unavailable or missing models: {', '.join(missing_models)}",
                " ".join(f"ollama pull {model}" for model in missing_models),
            )
        )
    return issues


def run_preflight(dataset: str, run: str) -> int:
    """Print only friendly one-line failures and return a shell exit status."""
    issues = check_preflight(dataset, run)
    if not issues:
        print(f"Preflight passed for {run} DATASET={dataset}.")
        return 0
    for issue in issues:
        print(issue.render(), file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Grounded run prerequisites.")
    parser.add_argument("--dataset", default="adventureworks")
    parser.add_argument("--run", choices=("spine", "benchmark"), required=True)
    arguments = parser.parse_args(argv)
    return run_preflight(arguments.dataset, arguments.run)


if __name__ == "__main__":
    raise SystemExit(main())
