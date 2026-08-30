"""Generate TPC-H with DuckDB and COPY its eight source tables into PostgreSQL."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import dlt
import duckdb
import psycopg2

from packlib import active_pack

TABLES = ("region", "nation", "supplier", "customer", "part", "partsupp", "orders", "lineitem")
POSTGRES_SCHEMA = "tpch"
POSTGRES_DATABASE = "tpch"
POSTGRES_USERNAME = "grounded"
POSTGRES_PASSWORD = "grounded_local_password"
SCALE_FACTOR = 0.5
PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = PROJECT_ROOT / "infra" / "docker-compose.yml"


def _source_dsn() -> str:
    pack = active_pack()
    if pack.source.dsn_env is None:
        raise RuntimeError("The TPC-H pack must declare its PostgreSQL DSN environment key")
    dsn = os.environ.get(pack.source.dsn_env) or dlt.secrets.get(pack.source.dsn_env)
    if not isinstance(dsn, str) or not dsn:
        raise RuntimeError(f"Set {pack.source.dsn_env} before loading TPC-H.")
    return dsn


def _compose(*arguments: str) -> None:
    environment = {
        **os.environ,
        "GROUNDED_SOURCE_DATABASE": POSTGRES_DATABASE,
        "GROUNDED_SOURCE_USERNAME": POSTGRES_USERNAME,
        "GROUNDED_SOURCE_PASSWORD": POSTGRES_PASSWORD,
    }
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *arguments],
        check=True,
        env=environment,
    )


def _postgres_type(duckdb_type: str) -> str:
    """Map the small, generated TPC-H DuckDB type surface to PostgreSQL DDL."""
    normalized = duckdb_type.upper()
    if normalized.startswith("DECIMAL"):
        return normalized
    if normalized in {"BIGINT", "INTEGER", "DATE", "VARCHAR"}:
        return normalized
    raise ValueError(f"Unsupported generated TPC-H type: {duckdb_type}")


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _create_schema(cursor: Any, source: duckdb.DuckDBPyConnection) -> None:
    cursor.execute(f"DROP SCHEMA IF EXISTS {_quote(POSTGRES_SCHEMA)} CASCADE")
    cursor.execute(f"CREATE SCHEMA {_quote(POSTGRES_SCHEMA)}")
    for table in TABLES:
        columns = source.execute(f"DESCRIBE {_quote(table)}").fetchall()
        ddl_columns = ", ".join(
            f"{_quote(name)} {_postgres_type(type_name)}"
            for name, type_name, *_ in columns
        )
        cursor.execute(
            f"CREATE TABLE {_quote(POSTGRES_SCHEMA)}.{_quote(table)} ({ddl_columns})"
        )


def load() -> None:
    """Generate SF=0.5, then copy every TPC-H relation into the PostgreSQL source."""
    _compose("up", "-d", "postgres")
    with duckdb.connect(":memory:") as source, psycopg2.connect(_source_dsn()) as destination:
        source.execute("INSTALL tpch")
        source.execute("LOAD tpch")
        source.execute(f"CALL dbgen(sf={SCALE_FACTOR})")
        with destination.cursor() as cursor:
            _create_schema(cursor, source)
            with tempfile.TemporaryDirectory(prefix="grounded-tpch-") as temporary_directory:
                temporary_root = Path(temporary_directory)
                for table in TABLES:
                    csv_path = temporary_root / f"{table}.csv"
                    escaped_path = str(csv_path).replace("'", "''")
                    source.execute(
                        f"COPY {_quote(table)} TO '{escaped_path}' (HEADER, DELIMITER ',')"
                    )
                    with csv_path.open(encoding="utf-8") as csv_file:
                        cursor.copy_expert(
                            f"COPY {_quote(POSTGRES_SCHEMA)}.{_quote(table)} FROM STDIN WITH CSV HEADER",
                            csv_file,
                        )
        destination.commit()
    verify()


def verify() -> None:
    """Print the real PostgreSQL source counts for all declared TPC-H relations."""
    with psycopg2.connect(_source_dsn()) as destination, destination.cursor() as cursor:
        print(f"{'table_name':20} {'row_count':>12}")
        print("-" * 33)
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM {_quote(POSTGRES_SCHEMA)}.{_quote(table)}")
            count = cursor.fetchone()[0]
            if count == 0:
                raise RuntimeError(f"TPC-H source table is unexpectedly empty: {table}")
            print(f"{POSTGRES_SCHEMA}.{table:14} {count:12d}")


def up() -> None:
    """Start the shared local PostgreSQL source service."""
    _compose("up", "-d", "postgres")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and load the TPC-H PostgreSQL source.")
    parser.add_argument("command", choices=("up", "load", "verify"), nargs="?", default="load")
    command = parser.parse_args().command
    {"up": up, "load": load, "verify": verify}[command]()


if __name__ == "__main__":
    main()
