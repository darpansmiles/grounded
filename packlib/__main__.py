"""Small Makefile-facing interface for resolved dataset-pack paths."""

from __future__ import annotations

import argparse
from pathlib import Path

from packlib import PROJECT_ROOT, active_pack, source_is_available


def _project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve a field from GROUNDED_PACK.")
    parser.add_argument(
        "field",
        choices=(
            "source_load",
            "source_load_or_empty",
            "source_type",
            "source_available",
            "transform",
            "has_transform",
            "semantics_backend",
            "semantics_cube",
            "semantics_cube_or_empty",
            "golden",
            "destination",
        ),
    )
    arguments = parser.parse_args()
    pack = active_pack()
    values: dict[str, Path | str | None] = {
        "source_load": pack.source.load,
        "source_load_or_empty": pack.source.load or "",
        "source_type": pack.source.type,
        "source_available": str(source_is_available(pack)).lower(),
        "transform": pack.transform_dir,
        "has_transform": str(pack.transform_dir is not None).lower(),
        "semantics_backend": pack.semantics.backend if pack.semantics else None,
        "semantics_cube": pack.semantics.cube if pack.semantics else None,
        "semantics_cube_or_empty": (
            pack.semantics.cube if pack.semantics and pack.semantics.cube else ""
        ),
        "golden": pack.golden,
        "destination": pack.destination.path,
    }
    value = values[arguments.field]
    if isinstance(value, str):
        print(value)
        return
    if value is None:
        raise SystemExit(f"Active pack {pack.name!r} does not provide {arguments.field}")
    print(_project_relative(value))


if __name__ == "__main__":
    main()
