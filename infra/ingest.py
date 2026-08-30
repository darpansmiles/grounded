"""Ingest the active source pack into its DuckDB bronze schema."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import dlt
from dlt.sources.sql_database import sql_database

from ontology.marquez_client import GROUNDED_OL_PRODUCER, RUN_EVENT_SCHEMA_URL
from packlib import Pack, active_pack

LINEAGE_PATH = Path("data/openlineage/ingest.jsonl")


def _quoted(identifier: str) -> str:
    """Quote an SQL identifier from a pack manifest."""
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _enable_sqlite(connection: Any) -> None:
    """Load DuckDB's SQLite extension, installing it on first use if necessary."""
    import duckdb

    try:
        connection.execute("LOAD sqlite")
    except duckdb.Error:
        try:
            connection.execute("INSTALL sqlite")
            connection.execute("LOAD sqlite")
        except duckdb.Error as exc:
            raise RuntimeError(
                "DuckDB's sqlite extension is required to ingest SQLite source packs"
            ) from exc


def _attach_sqlite_source(connection: Any, source_path: Path) -> None:
    """Attach a pack SQLite source under the fixed, local-only `src` alias."""
    escaped_path = str(source_path).replace("'", "''")
    connection.execute(f"ATTACH '{escaped_path}' AS src (TYPE sqlite)")

def _source_dsn(pack: Pack) -> str:
    """Read a pack-named source credential from the environment or dlt secrets."""
    if pack.source.type != "postgres" or pack.source.dsn_env is None:
        raise ValueError(f"Pack {pack.name!r} does not provide a PostgreSQL source")
    dsn = os.environ.get(pack.source.dsn_env) or dlt.secrets.get(pack.source.dsn_env)
    if not isinstance(dsn, str) or not dsn:
        raise RuntimeError(
            f"Set {pack.source.dsn_env} in the environment or .dlt/secrets.toml before ingesting {pack.name}."
        )
    return dsn


def _source_table_names(pack: Pack) -> tuple[str, ...]:
    return pack.source.tables


def _resources(pack: Pack, source_dsn: str) -> list[Any]:
    """Create dlt resources from the active PostgreSQL pack's declared tables."""
    resources: list[Any] = []
    tables_by_schema: dict[str, list[str]] = {}
    for source_table in pack.source.tables:
        schema, separator, table = source_table.partition(".")
        if not separator or not schema or not table:
            raise ValueError(f"Pack source table must be schema-qualified: {source_table}")
        tables_by_schema.setdefault(schema, []).append(table)
    for schema, tables in tables_by_schema.items():
        source = sql_database(
            credentials=source_dsn,
            schema=schema,
            table_names=tables,
        )
        resources.extend(source.resources.values())
    return resources


def _source_tables_by_resource(pack: Pack, source_dsn: str) -> dict[str, str]:
    """Map the extraction configuration's resource names to source identities."""
    database = urlparse(source_dsn).path.removeprefix("/")
    return {
        source_table.rsplit(".", maxsplit=1)[1]: f"{database}.{source_table}"
        for source_table in pack.source.tables
    }


def _source_namespace(source_dsn: str) -> str:
    """Derive the OpenLineage source namespace from the configured DSN scheme."""
    scheme = urlparse(source_dsn).scheme.partition("+")[0]
    return scheme.removesuffix("ql")


def _pack_namespace(namespace: str) -> str:
    """Scope one OpenLineage dataset namespace to the active pack."""
    return f"{active_pack().namespace}.{namespace}"


def _loaded_tables(load_info: Any) -> tuple[dict[str, Any], list[str]]:
    """Select the actual completed destination tables from dlt's load metadata."""
    metadata = load_info.asdict()
    tables = {
        job["table_name"]
        for package in metadata["load_packages"]
        for job in package["jobs"]
        if job["state"] == "completed_jobs" and not job["table_name"].startswith("_dlt_")
    }
    tables.update(
        table
        for output in metadata["outputs"]
        for table in output.get("tables", [])
        if not table.startswith("_dlt_")
    )
    if not tables:
        raise RuntimeError("dlt load metadata did not report any completed destination tables")
    return metadata, sorted(tables)


def _schema_fields(table_schema: dict[str, Any]) -> list[dict[str, str]]:
    """Render dlt's normalized columns as an OpenLineage SchemaDatasetFacet."""
    return [
        {"name": column["name"], "type": column.get("data_type", "unknown")}
        for _, column in sorted(table_schema["columns"].items())
    ]


def _destination_row_count(destination_path: Path, dataset: str, table: str) -> int:
    """Read a destination count only when dlt's normalize trace lacks a table."""
    import duckdb

    quoted_dataset = dataset.replace('"', '""')
    quoted_table = table.replace('"', '""')
    with duckdb.connect(str(destination_path), read_only=True) as destination:
        return destination.execute(
            f'SELECT COUNT(*) FROM "{quoted_dataset}"."{quoted_table}"'
        ).fetchone()[0]


def _dataset(
    namespace: str,
    name: str,
    fields: list[dict[str, str]],
    row_count: int,
) -> dict[str, Any]:
    """Build one dlt-reported dataset identity with schema and row-count facets."""
    return {
        "namespace": namespace,
        "name": name,
        "facets": {
            "schema": {
                "_producer": f"{GROUNDED_OL_PRODUCER}/blob/main/infra/ingest.py",
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json",
                "fields": fields,
            },
            "dataQualityMetrics": {
                "_producer": f"{GROUNDED_OL_PRODUCER}/blob/main/infra/ingest.py",
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsInputDatasetFacet.json",
                "rowCount": row_count,
            },
        },
    }


def lineage_events(
    load_info: Any,
    schema: Any,
    row_counts: dict[str, int],
    source_tables: dict[str, str],
    source_namespace: str,
    destination_path: Path | None = None,
    job_namespace: str = "dlt",
    *,
    started_at: str,
    completed_at: str,
) -> list[dict[str, Any]]:
    """Build Contract-A events from dlt's actual load, schema, and trace state."""
    metadata, table_names = _loaded_tables(load_info)
    destination_namespace = _pack_namespace(metadata["dataset_name"])
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    for table_name in table_names:
        if table_name not in source_tables:
            raise RuntimeError(f"dlt loaded resource without source configuration: {table_name}")
        if table_name not in schema.tables:
            raise RuntimeError(f"dlt loaded resource without normalized schema: {table_name}")
        fields = _schema_fields(schema.tables[table_name])
        row_count = row_counts.get(table_name)
        if row_count is None:
            if destination_path is None:
                raise RuntimeError("dlt row count was missing and no destination path was provided")
            row_count = _destination_row_count(destination_path, destination_namespace, table_name)
        inputs.append(
            _dataset(
                _pack_namespace(source_namespace),
                source_tables[table_name],
                fields,
                row_count,
            )
        )
        outputs.append(_dataset(destination_namespace, table_name, fields, row_count))

    load_ids = metadata["loads_ids"]
    run = {
        "runId": load_ids[-1],
        "facets": {
            "dlt_load": {
                "_producer": f"{GROUNDED_OL_PRODUCER}/blob/main/infra/ingest.py",
                "loadIds": load_ids,
                "rowCounts": {table: row_counts[table] for table in table_names if table in row_counts},
            }
        },
    }
    common = {
        "producer": f"{GROUNDED_OL_PRODUCER}/blob/main/infra/ingest.py",
        "schemaURL": RUN_EVENT_SCHEMA_URL,
        "run": run,
        "job": {"namespace": job_namespace, "name": metadata["pipeline"]["pipeline_name"]},
        "inputs": inputs,
        "outputs": outputs,
    }
    return [
        {"eventType": "START", "eventTime": started_at, **common},
        {"eventType": "COMPLETE", "eventTime": completed_at, **common},
    ]


def sqlite_lineage_events(
    pack: Pack,
    table_fields: dict[str, list[dict[str, str]]],
    row_counts: dict[str, int],
    *,
    started_at: str,
    completed_at: str,
) -> list[dict[str, Any]]:
    """Build Contract-A source-to-bronze events for one SQLite pack load."""
    source_namespace = f"{pack.namespace}.sqlite"
    destination_namespace = f"{pack.namespace}.{pack.destination.dataset}"
    inputs = [
        _dataset(source_namespace, table, table_fields[table], row_counts[table])
        for table in pack.source.tables
    ]
    outputs = [
        _dataset(destination_namespace, table, table_fields[table], row_counts[table])
        for table in pack.source.tables
    ]
    common = {
        "producer": f"{GROUNDED_OL_PRODUCER}/blob/main/infra/ingest.py",
        "schemaURL": RUN_EVENT_SCHEMA_URL,
        "run": {"runId": str(uuid4())},
        "job": {
            "namespace": f"{pack.namespace}.sqlite",
            "name": f"{pack.name}_to_{pack.destination.dataset}",
        },
        "inputs": inputs,
        "outputs": outputs,
    }
    return [
        {"eventType": "START", "eventTime": started_at, **common},
        {"eventType": "COMPLETE", "eventTime": completed_at, **common},
    ]


def _write_events(events: list[dict[str, Any]]) -> None:
    LINEAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LINEAGE_PATH.open("w", encoding="utf-8") as lineage_file:
        for event in events:
            lineage_file.write(json.dumps(event, sort_keys=True))
            lineage_file.write("\n")


def _sqlite_source_path(pack: Pack) -> Path:
    """Require the declared user-fetched SQLite file only when ingestion begins."""
    source_path = pack.source.path
    if source_path is None:
        raise ValueError(f"Pack {pack.name!r} does not provide a SQLite source.path")
    if not source_path.is_file():
        raise RuntimeError(
            f"SQLite source is missing: place the SQLite at {source_path} — "
            "see source/README.md for the download URL"
        )
    return source_path


def _ingest_sqlite(pack: Pack) -> None:
    """Copy declared SQLite base tables into the pack-local bronze schema."""
    import duckdb

    source_path = _sqlite_source_path(pack)
    started_at = datetime.now(UTC).isoformat()
    pack.destination.path.parent.mkdir(parents=True, exist_ok=True)
    table_fields: dict[str, list[dict[str, str]]] = {}
    row_counts: dict[str, int] = {}
    with duckdb.connect(str(pack.destination.path)) as destination:
        _enable_sqlite(destination)
        _attach_sqlite_source(destination, source_path)
        destination.execute(f"CREATE SCHEMA IF NOT EXISTS {_quoted(pack.destination.dataset)}")
        for table in pack.source.tables:
            quoted_table = _quoted(table)
            fields = destination.execute(f"DESCRIBE src.{quoted_table}").fetchall()
            if not fields:
                raise RuntimeError(f"SQLite source table was not found: {table}")
            table_fields[table] = [
                {"name": field[0], "type": str(field[1])} for field in fields
            ]
            destination.execute(
                f"CREATE OR REPLACE TABLE {_quoted(pack.destination.dataset)}.{quoted_table} "
                f"AS SELECT * FROM src.{quoted_table}"
            )
            row_counts[table] = destination.execute(
                f"SELECT COUNT(*) FROM {_quoted(pack.destination.dataset)}.{quoted_table}"
            ).fetchone()[0]
    events = sqlite_lineage_events(
        pack,
        table_fields,
        row_counts,
        started_at=started_at,
        completed_at=datetime.now(UTC).isoformat(),
    )
    _write_events(events)
    print(f"SQLite source loaded into {pack.destination.path}")
    print(f"OpenLineage events: START, COMPLETE -> {LINEAGE_PATH}")


def ingest() -> None:
    """Run the active pack's replacement load and emit its Contract-A handoff."""
    pack = active_pack()
    if pack.source.type == "sqlite":
        _ingest_sqlite(pack)
        return
    source_dsn = _source_dsn(pack)
    started_at = datetime.now(UTC).isoformat()
    pack.destination.path.parent.mkdir(parents=True, exist_ok=True)

    pipeline = dlt.pipeline(
        pipeline_name=f"{pack.name}_to_{pack.destination.dataset}",
        destination=dlt.destinations.duckdb(credentials=str(pack.destination.path)),
        dataset_name=pack.destination.dataset,
    )
    load_info = pipeline.run(_resources(pack, source_dsn), write_disposition="replace")
    trace = pipeline.last_trace
    if trace is None:
        raise RuntimeError("dlt did not retain a trace for the completed load")
    events = lineage_events(
        load_info,
        pipeline.default_schema,
        trace.last_normalize_info.row_counts,
        _source_tables_by_resource(pack, source_dsn),
        _source_namespace(source_dsn),
        pack.destination.path,
        f"{pack.namespace}.dlt",
        started_at=started_at,
        completed_at=datetime.now(UTC).isoformat(),
    )
    _write_events(events)
    print(load_info)
    print(f"OpenLineage events: START, COMPLETE -> {LINEAGE_PATH}")


def verify() -> None:
    """Compare every bronze table count against its declared source."""
    import duckdb
    import psycopg2

    pack = active_pack()
    if not pack.destination.path.is_file():
        raise SystemExit(f"Bronze lakehouse does not exist: {pack.destination.path}")

    if pack.source.type == "sqlite":
        source_path = _sqlite_source_path(pack)
        with duckdb.connect(str(pack.destination.path), read_only=True) as bronze:
            _enable_sqlite(bronze)
            _attach_sqlite_source(bronze, source_path)
            print(f"{'table_name':31} {'source_rows':>12} {'bronze_rows':>12}")
            print("-" * 59)
            for table in _source_table_names(pack):
                quoted_table = _quoted(table)
                source_rows = bronze.execute(
                    f"SELECT COUNT(*) FROM src.{quoted_table}"
                ).fetchone()[0]
                bronze_rows = bronze.execute(
                    f"SELECT COUNT(*) FROM {_quoted(pack.destination.dataset)}.{quoted_table}"
                ).fetchone()[0]
                print(f"{table:31} {source_rows:12d} {bronze_rows:12d}")
                if source_rows != bronze_rows:
                    raise SystemExit(
                        f"Ingestion fidelity failure for {table}: "
                        f"source={source_rows}, bronze={bronze_rows}"
                    )
                if source_rows == 0:
                    raise SystemExit(f"Source table is unexpectedly empty: {table}")
        return

    source_dsn = _source_dsn(pack)

    with psycopg2.connect(source_dsn) as source, duckdb.connect(
        str(pack.destination.path), read_only=True
    ) as bronze:
        print(f"{'table_name':31} {'source_rows':>12} {'bronze_rows':>12}")
        print("-" * 59)
        for source_table in _source_table_names(pack):
            schema, table = source_table.split(".")
            with source.cursor() as cursor:
                cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
                source_rows = cursor.fetchone()[0]
            bronze_rows = bronze.execute(
                f'SELECT COUNT(*) FROM "{pack.destination.dataset}"."{table}"'
            ).fetchone()[0]
            print(f"{source_table:31} {source_rows:12d} {bronze_rows:12d}")
            if source_rows != bronze_rows:
                raise SystemExit(
                    f"Ingestion fidelity failure for {source_table}: "
                    f"source={source_rows}, bronze={bronze_rows}"
                )
            if source_rows == 0:
                raise SystemExit(f"Source table is unexpectedly empty: {source_table}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest or verify the active pack's bronze data.")
    parser.add_argument("command", choices=("ingest", "verify"), nargs="?", default="ingest")
    args = parser.parse_args()
    if args.command == "ingest":
        ingest()
    else:
        verify()
