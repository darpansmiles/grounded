"""Inspect the unified, read-only catalog of each available pack database."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

from packlib import PACKS_DIRECTORY, load_pack


@dataclass(frozen=True)
class AttachedPack:
    """The physical database and catalog alias for one pack."""

    alias: str
    database: Path


def available_pack_databases() -> list[AttachedPack]:
    """Resolve existing pack databases using their declared lineage aliases."""
    packs: list[AttachedPack] = []
    for pack_root in sorted(PACKS_DIRECTORY.iterdir()):
        if not pack_root.is_dir() or not (pack_root / "pack.yml").is_file() or pack_root.name.startswith("_"):
            continue
        pack = load_pack(pack_root.name)
        if pack.destination.path.is_file():
            packs.append(AttachedPack(pack.namespace, pack.destination.path))
    return packs


def attach_read_only(
    connection: duckdb.DuckDBPyConnection, packs: list[AttachedPack]
) -> None:
    """Attach each pack as its stable lineage namespace without granting write access."""
    for pack in packs:
        escaped_path = str(pack.database).replace("'", "''")
        escaped_alias = pack.alias.replace('"', '""')
        connection.execute(
            f"ATTACH '{escaped_path}' AS \"{escaped_alias}\" (READ_ONLY)"
        )


def catalog_rows(connection: duckdb.DuckDBPyConnection) -> list[tuple[str, str, str]]:
    """Return every attached user relation as catalog, schema, table triples."""
    return connection.execute(
        """
        SELECT table_catalog, table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_catalog, table_schema, table_name
        """
    ).fetchall()


def main() -> None:
    """Attach every available pack into one ephemeral unified read-only session."""
    packs = available_pack_databases()
    if not packs:
        raise SystemExit("No pack databases exist. Run a pack spine first.")
    connection = duckdb.connect(":memory:")
    try:
        attach_read_only(connection, packs)
        print("Attached read-only pack catalogs:")
        for alias, schema, table in catalog_rows(connection):
            print(f"{alias}.{schema}.{table}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
