"""Dataset-pack manifest loading and active-pack selection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKS_DIRECTORY = PROJECT_ROOT / "datasets"
DEFAULT_PACK = "adventureworks"


@dataclass(frozen=True)
class Source:
    """A pack-owned source configuration with credentials named, not embedded."""

    type: str
    load: Path | None
    tables: tuple[str, ...]
    dsn_env: str | None
    path: Path | None


@dataclass(frozen=True)
class Destination:
    """The destination dlt writes for this pack."""

    type: str
    path: Path
    dataset: str


@dataclass(frozen=True)
class Semantics:
    """Optional governed-semantic capability provided by a pack."""

    backend: str
    cube: Path | None
    metrics: tuple[Path, ...]


@dataclass(frozen=True)
class Pack:
    """A validated dataset pack with all manifest paths resolved."""

    name: str
    root: Path
    namespace: str
    source: Source
    destination: Destination
    transform_dir: Path | None
    semantics: Semantics | None
    golden: Path


def source_is_available(pack: Pack) -> bool:
    """Return whether a pack's optional local source asset is present."""
    path = getattr(pack.source, "path", None)
    return path is None or path.is_file()


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"pack.yml {field} must be a mapping")
    return value


def _relative_path(pack_root: Path, value: Any, field: str, *, required: bool = True) -> Path | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"pack.yml {field} must be a non-empty relative path")
    path = (pack_root / value).resolve()
    if pack_root not in path.parents and path != pack_root:
        raise ValueError(f"pack.yml {field} must stay within its pack directory")
    if not path.exists():
        raise ValueError(f"pack.yml {field} does not exist: {value}")
    return path


def _destination_path(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("pack.yml destination.path must be a non-empty path")
    path = (PROJECT_ROOT / value).resolve()
    if PROJECT_ROOT not in path.parents and path != PROJECT_ROOT:
        raise ValueError("pack.yml destination.path must stay within the project")
    return path


def _source_path(pack_root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("pack.yml source.path must be a non-empty relative path")
    path = (pack_root / value).resolve()
    if pack_root not in path.parents:
        raise ValueError("pack.yml source.path must stay within the pack directory")
    return path


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) for item in value):
        raise ValueError(f"pack.yml {field} must be a non-empty list of strings")
    return tuple(value)


def load_pack(name: str) -> Pack:
    """Load one pack by directory name and validate its shared manifest contract."""
    if not name or Path(name).name != name:
        raise ValueError("Pack name must be one directory name")
    root = (PACKS_DIRECTORY / name).resolve()
    manifest_path = root / "pack.yml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Unknown dataset pack: {name}")
    with manifest_path.open(encoding="utf-8") as manifest_file:
        manifest = _mapping(yaml.safe_load(manifest_file), "root")

    manifest_name = manifest.get("name")
    namespace = manifest.get("lineage_namespace")
    if manifest_name != name or not isinstance(namespace, str) or not namespace:
        raise ValueError("pack.yml name and lineage_namespace must be non-empty strings")

    source_data = _mapping(manifest.get("source"), "source")
    source_type = source_data.get("type")
    if source_type not in {"postgres", "sqlite", "duckdb_seed", "generator"}:
        raise ValueError("pack.yml source.type must be postgres, sqlite, duckdb_seed, or generator")
    connection = source_data.get("connection")
    dsn_env: str | None = None
    if source_type == "postgres":
        connection_data = _mapping(connection, "source.connection")
        dsn_env = connection_data.get("dsn_env")
        if not isinstance(dsn_env, str) or not dsn_env:
            raise ValueError("pack.yml source.connection.dsn_env must be a non-empty string")
    source_path = _source_path(root, source_data.get("path")) if source_type == "sqlite" else None
    if source_type == "sqlite" and any("." in table for table in _string_list(source_data.get("tables"), "source.tables")):
        raise ValueError("pack.yml sqlite source.tables must use bare table names")
    source = Source(
        type=source_type,
        load=_relative_path(root, source_data.get("load"), "source.load", required=False),
        tables=_string_list(source_data.get("tables"), "source.tables"),
        dsn_env=dsn_env,
        path=source_path,
    )

    destination_data = _mapping(manifest.get("destination"), "destination")
    if destination_data.get("type") != "duckdb":
        raise ValueError("pack.yml destination.type must be duckdb")
    destination_dataset = destination_data.get("dataset")
    if not isinstance(destination_dataset, str) or not destination_dataset:
        raise ValueError("pack.yml destination.dataset must be a non-empty string")
    destination = Destination(
        type="duckdb",
        path=_destination_path(destination_data.get("path")),
        dataset=destination_dataset,
    )

    transform_dir = _relative_path(root, manifest.get("transform"), "transform", required=False)
    semantics_data = manifest.get("semantics")
    semantics: Semantics | None = None
    if semantics_data is not None:
        semantic_mapping = _mapping(semantics_data, "semantics")
        backend = semantic_mapping.get("backend")
        if backend not in {"cube", "fixture"}:
            raise ValueError("pack.yml semantics.backend must be cube or fixture")
        cube = _relative_path(root, semantic_mapping.get("cube"), "semantics.cube", required=False)
        if backend == "cube" and cube is None:
            raise ValueError("Cube packs must declare semantics.cube")
        semantics = Semantics(
            backend=backend,
            cube=cube,
            metrics=tuple(
                _relative_path(root, metric, "semantics.metrics[]")
                for metric in _string_list(semantic_mapping.get("metrics"), "semantics.metrics")
            ),
        )
    return Pack(
        name=name,
        root=root,
        namespace=namespace,
        source=source,
        destination=destination,
        transform_dir=transform_dir,
        semantics=semantics,
        golden=_relative_path(root, manifest.get("golden"), "golden"),
    )


def active_pack() -> Pack:
    """Resolve the process-wide active pack from the one supported selection seam."""
    return load_pack(os.environ.get("GROUNDED_PACK", DEFAULT_PACK))
