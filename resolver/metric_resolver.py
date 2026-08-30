"""Dispatch governed metrics to the deterministic fixture or Cube backend."""

from __future__ import annotations

from typing import Any

from resolver.backends import SUPPORTED_BACKENDS
from resolver.backends import cube, fixture
from resolver.backends.fixture import (
    UndeclaredFieldError,
    UnknownMetricError,
    _compile_measure,
    _dimension_columns,
    _load_definition,
    _validate_request,
)


def resolve_and_run(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict | None = None,
    reference_date: str = "2026-08-12",
    db_path: str = "grounded.duckdb",
    row_predicates: list[str] | None = None,
    *,
    backend: str = "fixture",
    cube_filters: list[dict[str, Any]] | None = None,
    cube_url: str | None = None,
) -> dict:
    """Resolve one base metric through the selected computation backend."""
    if backend not in SUPPORTED_BACKENDS:
        raise ValueError(f"Unknown resolver backend: {backend}")
    if backend == "fixture":
        return fixture.resolve_and_run(
            metric, dimensions, filters, reference_date, db_path, row_predicates
        )
    return cube.resolve_and_run(
        metric,
        dimensions,
        filters,
        reference_date,
        row_predicates=row_predicates,
        cube_filters=cube_filters,
        cube_url=cube_url,
    )


__all__ = [
    "UndeclaredFieldError",
    "UnknownMetricError",
    "_compile_measure",
    "_dimension_columns",
    "_load_definition",
    "_validate_request",
    "resolve_and_run",
]
