"""Cube REST backend driven by the active dataset pack's Cube model."""

from __future__ import annotations

import json
import os
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx
import yaml

from packlib import active_pack
from resolver.backends.fixture import (
    UndeclaredFieldError,
    UnknownMetricError,
    _last_month_window,
    _load_definition,
)

DEFAULT_CUBE_URL = os.environ.get(
    "GROUNDED_CUBE_URL", "http://localhost:4000/cubejs-api/v1"
)


class CubeResponseError(RuntimeError):
    """Raised when Cube cannot provide a valid `/load` response."""


def _cube_remedy(exc: httpx.HTTPError) -> str:
    """Give the active pack's recovery command without leaking transport internals."""
    pack_name = active_pack().name
    message = (
        f"Cube is not serving dataset {pack_name!r}. "
        f"Run `make cube-up DATASET={pack_name}` and retry."
    )
    if os.environ.get("GROUNDED_DEBUG"):
        return f"{message} Debug: {exc}"
    return message


def _cube_definitions() -> list[dict[str, Any]]:
    """Read all declarative Cube definitions owned by the active semantic pack."""
    pack = active_pack()
    if pack.semantics is None or pack.semantics.cube is None:
        raise UnknownMetricError(
            f"Active pack {pack.name!r} does not provide Cube semantics"
        )
    definitions: list[dict[str, Any]] = []
    for model_path in sorted((pack.semantics.cube / "model").glob("*.y*ml")):
        with model_path.open(encoding="utf-8") as model_file:
            document = yaml.safe_load(model_file)
        if isinstance(document, dict):
            definitions.extend(
                cube_definition
                for cube_definition in document.get("cubes", [])
                if isinstance(cube_definition, dict)
            )
    if not definitions:
        raise UnknownMetricError(f"Active pack {pack.name!r} has no Cube definitions")
    return definitions


def _member_maps(metric: str, dimensions: list[str]) -> tuple[str, dict[str, str]]:
    """Resolve public semantic names to members declared by the active Cube model."""
    definitions = _cube_definitions()
    measure_cube = next(
        (
            cube_definition
            for cube_definition in definitions
            if any(
                measure.get("name") == metric
                for measure in cube_definition.get("measures", [])
            )
        ),
        None,
    )
    if measure_cube is None:
        raise UnknownMetricError(f"Cube does not expose governed metric: {metric}")
    cube_name = measure_cube.get("name")
    if not isinstance(cube_name, str) or not cube_name:
        raise UnknownMetricError(f"Cube measure {metric!r} has no owning cube name")

    declared_dimensions = {
        dimension.get("name")
        for dimension in measure_cube.get("dimensions", [])
        if isinstance(dimension, dict)
    }
    members: dict[str, str] = {}
    for dimension in dimensions:
        if dimension in declared_dimensions:
            members[dimension] = f"{cube_name}.{dimension}"
            continue
        fallback_cube = next(
            (
                candidate
                for candidate in definitions
                if any(
                    declared.get("name") == dimension
                    for declared in candidate.get("dimensions", [])
                    if isinstance(declared, dict)
                )
            ),
            None,
        )
        fallback_name = fallback_cube.get("name") if fallback_cube else None
        if not isinstance(fallback_name, str) or not fallback_name:
            raise UnknownMetricError(
                f"Cube does not expose governed dimension: {dimension}"
            )
        members[dimension] = f"{fallback_name}.{dimension}"
    return f"{cube_name}.{metric}", members


def has_dimension_member(member: str) -> bool:
    """Return whether a fully-qualified member is a declared Cube dimension."""
    return any(
        member == f"{cube_definition.get('name')}.{dimension.get('name')}"
        for cube_definition in _cube_definitions()
        for dimension in cube_definition.get("dimensions", [])
        if isinstance(dimension, dict)
    )


def _declared_dimension_members(metric: str, definition: dict[str, Any]) -> dict[str, str]:
    """Resolve every Contract-B dimension against the active pack's Cube model."""
    dimensions = definition.get("dimensions", [])
    if not isinstance(dimensions, list):
        raise UnknownMetricError(f"Metric {metric!r} has invalid dimension declarations")
    names = [dimension.get("name") for dimension in dimensions if isinstance(dimension, dict)]
    if len(names) != len(dimensions) or any(not isinstance(name, str) or not name for name in names):
        raise UnknownMetricError(f"Metric {metric!r} has invalid dimension declarations")
    _, members = _member_maps(metric, names)
    return members


def _validate_request(
    metric: str,
    definition: dict[str, Any],
    dimensions: list[str],
    filters: dict[str, Any],
) -> None:
    """Validate only the metric dimensions and filter vocabulary declared by this pack."""
    declared_dimensions = _declared_dimension_members(metric, definition)
    for dimension in dimensions:
        if dimension not in declared_dimensions:
            raise UndeclaredFieldError(f"Undeclared dimension: {dimension}")
    for filter_name, filter_value in filters.items():
        if filter_name != "order_month" or filter_name not in declared_dimensions:
            raise UndeclaredFieldError(f"Undeclared filter: {filter_name}")
        if filter_value != "last_month":
            raise UndeclaredFieldError("Only the declared order_month=last_month filter is supported")


def _member_value(raw_row: dict[str, Any], member: str, dimension: str) -> Any:
    if member in raw_row:
        return raw_row[member]
    if dimension == "order_month":
        return raw_row.get(f"{member}.month")
    return None


def _is_additive_metric(definition: dict[str, Any]) -> bool:
    """Classify the Contract-B aggregate forms that have a zero empty-group value."""
    metric_definition = definition.get("definition", {})
    if not isinstance(metric_definition, dict):
        raise UnknownMetricError("Metric definition must be a mapping")
    if metric_definition.get("derived") == "ratio":
        return False
    measure = metric_definition.get("measure")
    if not isinstance(measure, str):
        raise UnknownMetricError("Metric must declare an additive measure or a derived ratio")
    return measure.startswith(("sum(", "count("))


def build_load_query(
    metric: str,
    dimensions: list[str],
    filters: dict[str, Any],
    reference_date: str,
    cube_filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Translate a declared governed request into Cube's REST query shape."""
    requested_member_dimensions = [
        *dimensions,
        *(
            []
            if "order_month" in dimensions or "order_month" not in filters
            else ["order_month"]
        ),
    ]
    measure_member, dimension_members = _member_maps(
        metric, requested_member_dimensions
    )
    query: dict[str, Any] = {"measures": [measure_member]}
    requested_dimensions = [
        dimension_members[dimension]
        for dimension in dimensions
        if dimension != "order_month"
    ]
    if requested_dimensions:
        query["dimensions"] = requested_dimensions

    time_dimensions: list[dict[str, Any]] = []
    if "order_month" in dimensions or filters.get("order_month") == "last_month":
        time_dimension: dict[str, Any] = {
            "dimension": dimension_members["order_month"],
            "granularity": "month",
        }
        if filters.get("order_month") == "last_month":
            start, end = _last_month_window(reference_date)
            time_dimension["dateRange"] = [start.isoformat(), end.isoformat()]
        time_dimensions.append(time_dimension)
    if time_dimensions:
        query["timeDimensions"] = time_dimensions

    if cube_filters:
        query["filters"] = cube_filters

    ordering = {measure_member: "desc"}
    ordering.update({member: "asc" for member in requested_dimensions})
    if "order_month" in dimensions:
        ordering[f"{dimension_members['order_month']}.month"] = "asc"
    query["order"] = ordering
    return query


def _parse_rows(
    payload: dict[str, Any], metric: str, dimensions: list[str], definition: dict[str, Any]
) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise CubeResponseError(
            "Cube /load response must contain a data array of objects"
        )
    measure_member, dimension_members = _member_maps(metric, dimensions)
    rows: list[dict[str, Any]] = []
    for raw_row in data:
        if measure_member not in raw_row:
            raise CubeResponseError(
                f"Cube /load response is missing measure: {measure_member}"
            )
        raw_value = raw_row[measure_member]
        if raw_value is None:
            value = Decimal(0) if _is_additive_metric(definition) else None
        else:
            try:
                value = Decimal(str(raw_value)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            except (
                Exception
            ) as exc:  # pragma: no cover - exact Decimal error varies by Python release
                raise CubeResponseError(
                    f"Cube returned a non-numeric value for {measure_member}"
                ) from exc
        row = {
            dimension: _member_value(raw_row, dimension_members[dimension], dimension)
            for dimension in dimensions
        }
        row[metric] = value
        rows.append(row)
    return rows


def resolve_and_run(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict | None = None,
    reference_date: str = "2026-08-12",
    *,
    row_predicates: list[str] | None = None,
    cube_filters: list[dict[str, Any]] | None = None,
    cube_url: str | None = None,
) -> dict:
    """Query the active pack's Cube model and normalize its result shape."""
    requested_dimensions = dimensions or []
    requested_filters = filters or {}
    definition = _load_definition(metric)
    if definition.get("definition", {}).get("derived"):
        raise UnknownMetricError(
            f"Derived metric must be resolved through governed service: {metric}"
        )
    _validate_request(metric, definition, requested_dimensions, requested_filters)
    if row_predicates:
        raise ValueError("Cube row predicates must be translated by governed.service")

    query = build_load_query(
        metric, requested_dimensions, requested_filters, reference_date, cube_filters
    )
    endpoint = f"{(cube_url or DEFAULT_CUBE_URL).rstrip('/')}/load"
    try:
        response = httpx.post(endpoint, json={"query": query}, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise CubeResponseError(_cube_remedy(exc)) from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise CubeResponseError("Cube /load response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise CubeResponseError("Cube /load response must be a JSON object")
    rows = _parse_rows(payload, metric, requested_dimensions, definition)
    return {
        "metric": metric,
        "dimensions": requested_dimensions,
        "filters": requested_filters,
        "columns": [*requested_dimensions, metric],
        "rows": rows,
        "row_count": len(rows),
        "sql": f"Cube /load query: {json.dumps(query, separators=(',', ':'), sort_keys=True)}",
        "resolved_definition": definition,
    }
