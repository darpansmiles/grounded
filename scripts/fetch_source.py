"""Fetch one approved third-party SQLite source and verify its documented checksum."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packlib import load_pack


@dataclass(frozen=True)
class SourceFetch:
    """One pinned, documented third-party source acquisition contract."""

    dataset: str
    url: str
    sha256: str
    archive_member: str | None = None


FETCHES = {
    "spider_world1": SourceFetch(
        dataset="spider_world1",
        url=(
            "https://huggingface.co/datasets/Chinastark/spider_datasets/resolve/"
            "e78889179827ba6af803937c320e1f0632886c24/database/world_1/world_1.sqlite"
        ),
        sha256="17b986695f16786d58d66f85e49dba87bdfe72953207ab9b1b49da9d2301ef65",
    ),
    "bird_ca_schools": SourceFetch(
        dataset="bird_ca_schools",
        url="https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip",
        sha256="c0903eec662e63068fd1d14403d3d6c1d473287fc10c4356333ea58f878db983",
        archive_member="minidev/MINIDEV/dev_databases/california_schools/california_schools.sqlite",
    ),
}

CommandRunner = Callable[..., Any]


class SourceFetchError(RuntimeError):
    """The requested source could not be downloaded or verified safely."""


def sha256(path: Path) -> str:
    """Return a file's SHA-256 without relying on a platform-specific shell tool."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str], runner: CommandRunner, **kwargs: Any) -> None:
    try:
        result = runner(command, check=False, **kwargs)
    except OSError as exc:
        raise SourceFetchError(f"Could not run {' '.join(command[:1])}: {exc}") from exc
    if result.returncode:
        raise SourceFetchError(f"Command failed ({result.returncode}): {' '.join(command[:2])}")


def fetch_source(dataset: str, *, runner: CommandRunner = subprocess.run) -> Path:
    """Fetch and atomically install one source only after its checksum matches."""
    try:
        fetch = FETCHES[dataset]
    except KeyError as exc:
        raise SourceFetchError(
            f"{dataset} has no approved external source fetch. See its source/README.md."
        ) from exc

    pack = load_pack(dataset)
    target = pack.source.path
    if target is None:
        raise SourceFetchError(f"{dataset} does not declare a SQLite source path.")
    if target.is_file() and sha256(target) == fetch.sha256:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"grounded-{dataset}-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        downloaded = temporary_root / "source.download"
        _run(["curl", "--fail", "--location", fetch.url, "--output", str(downloaded)], runner)
        candidate = downloaded
        if fetch.archive_member:
            candidate = temporary_root / target.name
            with candidate.open("wb") as extracted:
                _run(["unzip", "-p", str(downloaded), fetch.archive_member], runner, stdout=extracted)
        actual_sha256 = sha256(candidate)
        if actual_sha256 != fetch.sha256:
            raise SourceFetchError(
                f"Checksum mismatch for {dataset}: expected {fetch.sha256}, got {actual_sha256}. "
                "The source was not installed."
            )
        candidate.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch one approved Grounded third-party source.")
    parser.add_argument("dataset", choices=tuple(FETCHES))
    arguments = parser.parse_args(argv)
    try:
        path = fetch_source(arguments.dataset)
    except SourceFetchError as exc:
        print(f"Source fetch failed: {exc}", file=sys.stderr)
        return 2
    print(f"Fetched and checksum-verified {arguments.dataset} source at {path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
