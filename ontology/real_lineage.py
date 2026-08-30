"""Emit AdventureWorks lineage to Marquez from real dlt and SQLMesh metadata."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlmesh import Context
from sqlmesh.core.lineage import column_dependencies

from ontology.marquez_client import (
    GROUNDED_OL_PRODUCER,
    RUN_EVENT_SCHEMA_URL,
    emit_events,
)
from packlib import active_pack

DEFAULT_INGEST_LINEAGE_PATH = "data/openlineage/ingest.jsonl"


def active_transform_path() -> Path:
    """Return the SQLMesh project declared by the active pack."""
    transform_dir = active_pack().transform_dir
    if transform_dir is None:
        raise ValueError("The active pack does not provide a SQLMesh transform project")
    return transform_dir


def _dataset_from_identifier(identifier: str) -> dict[str, str] | None:
    """Normalize a SQLMesh identifier to its trailing namespace and dataset name."""
    parts = [part.strip('"') for part in identifier.split(".")]
    if len(parts) < 2:
        return None
    namespace, name = parts[-2:]
    return {"namespace": f"{active_pack().namespace}.{namespace}", "name": name}


def _normalized_ingest_event(raw_event: dict[str, Any]) -> dict[str, Any]:
    """Add the stable Grounded producer identity without changing load datasets."""
    return {
        "eventType": raw_event["eventType"],
        "eventTime": raw_event["eventTime"],
        "producer": f"{GROUNDED_OL_PRODUCER}/blob/main/infra/ingest.py",
        "schemaURL": RUN_EVENT_SCHEMA_URL,
        "run": raw_event["run"],
        "job": raw_event["job"],
        "inputs": raw_event.get("inputs", []),
        "outputs": raw_event.get("outputs", []),
    }


def ingest_events(path: str | Path = DEFAULT_INGEST_LINEAGE_PATH) -> list[dict[str, Any]]:
    """Read and normalize every producer-emitted ingestion JSONL event."""
    event_path = Path(path)
    if not event_path.is_file():
        raise FileNotFoundError(f"dlt lineage JSONL was not found: {event_path}")
    events: list[dict[str, Any]] = []
    with event_path.open(encoding="utf-8") as event_file:
        for line_number, line in enumerate(event_file, start=1):
            if not line.strip():
                continue
            try:
                raw_event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid ingest lineage JSON at {event_path}:{line_number}") from exc
            if not isinstance(raw_event, dict):
                raise TypeError(f"Ingest lineage event must be an object at {event_path}:{line_number}")
            events.append(_normalized_ingest_event(raw_event))
    if not events:
        raise ValueError(f"dlt lineage JSONL contained no events: {event_path}")
    return events


def _model_lineage(
    context: Context, model_identifier: str
) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    """Derive dataset and column dependencies from SQLMesh's column API."""
    model = context.models[model_identifier]
    dependencies: dict[tuple[str, str], dict[str, str]] = {}
    fields: dict[str, dict[str, Any]] = {}
    for column in model.columns_to_types:
        input_fields: list[dict[str, str]] = []
        for dependency_identifier, dependency_columns in column_dependencies(
            context, model_identifier, column
        ).items():
            dependency = _dataset_from_identifier(dependency_identifier)
            if dependency is None:
                continue
            dependencies[(dependency["namespace"], dependency["name"])] = dependency
            input_fields.extend(
                {
                    "namespace": dependency["namespace"],
                    "name": dependency["name"],
                    "field": dependency_column,
                }
                for dependency_column in sorted(dependency_columns)
            )
        if input_fields:
            fields[column] = {
                "inputFields": input_fields,
                "transformationDescription": "SQLMesh column dependency",
                "transformationType": "IDENTITY",
            }

    # `depends_on` is SQLMesh's parsed model DAG. It covers transformations such
    # as dim_date where a generated series masks the source table at column level.
    for dependency_identifier in model.depends_on:
        dependency = _dataset_from_identifier(dependency_identifier)
        if dependency is not None:
            dependencies[(dependency["namespace"], dependency["name"])] = dependency
    return list(dependencies.values()), fields


def _schema_facet(model: Any) -> dict[str, Any]:
    return {
        "_producer": f"{GROUNDED_OL_PRODUCER}/blob/main/ontology/real_lineage.py",
        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/SchemaDatasetFacet.json",
        "fields": [
            {"name": name, "type": str(data_type)}
            for name, data_type in sorted(model.columns_to_types.items())
        ],
    }


def sqlmesh_events_from_context(context: Context) -> list[dict[str, Any]]:
    """Build one event per SQLMesh model with dynamically-derived column facets."""
    event_time = datetime.now(UTC).isoformat()
    events: list[dict[str, Any]] = []
    for model_identifier in sorted(context.models):
        model = context.models[model_identifier]
        output = _dataset_from_identifier(model.name)
        if output is None:
            continue
        inputs, column_fields = _model_lineage(context, model_identifier)
        if not inputs:
            continue
        inputs.sort(key=lambda dataset: (dataset["namespace"], dataset["name"]))
        run_id = str(uuid5(NAMESPACE_URL, f"grounded/sqlmesh/{model.name}"))
        events.append(
            {
                "eventType": "COMPLETE",
                "eventTime": event_time,
                "producer": f"{GROUNDED_OL_PRODUCER}/blob/main/ontology/real_lineage.py",
                "schemaURL": RUN_EVENT_SCHEMA_URL,
                "run": {"runId": run_id},
                "job": {
                    "namespace": f"{active_pack().namespace}.sqlmesh",
                    "name": model.name,
                    "jobType": "sqlmesh",
                },
                "inputs": inputs,
                "outputs": [
                    {
                        **output,
                        "facets": {
                            "schema": _schema_facet(model),
                            "columnLineage": {
                                "_producer": f"{GROUNDED_OL_PRODUCER}/blob/main/ontology/real_lineage.py",
                                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ColumnLineageDatasetFacet.json",
                                "fields": column_fields,
                            },
                        },
                    }
                ],
            }
        )
    if not events:
        raise ValueError("SQLMesh project produced no lineage events")
    return events


def sqlmesh_events(transform_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Derive normalized OpenLineage events from the loaded SQLMesh project."""
    context = Context(paths=str(transform_path or active_transform_path()))
    return sqlmesh_events_from_context(context)


def emit_real_lineage(
    *,
    ingest_path: str | Path = DEFAULT_INGEST_LINEAGE_PATH,
    transform_path: str | Path | None = None,
) -> dict[str, Any]:
    """Emit ingestion and optional SQLMesh metadata to the Marquez lineage service."""
    producer_events = ingest_events(ingest_path)
    active_transform = transform_path or active_pack().transform_dir
    derived_events = sqlmesh_events(active_transform) if active_transform is not None else []
    events = [*producer_events, *derived_events]
    delivered = emit_events(events)

    return {
        "events_emitted": len(events),
        "ingest_events_emitted": len(producer_events),
        "sqlmesh_events_emitted": len(derived_events),
        "marquez_delivered": delivered,
    }
