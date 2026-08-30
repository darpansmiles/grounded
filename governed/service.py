"""Orchestrate resolution, policy, verification, and audit for governed tools."""

from __future__ import annotations

import os
from copy import deepcopy
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import duckdb
import yaml

from audit.log import append_audit
from policy.engine import apply_masking, row_predicates_for_role
from resolver.backends import cube
from resolver.metric_resolver import resolve_and_run
from semantics.loader import load_expanded_definition
from verify.verifier import verify_result

_SEMANTICS_DIRECTORY = Path(__file__).resolve().parents[1] / "semantics"
_CUBE_FILTER_OPERATORS = {"in": "equals", "equals": "equals"}


def _missing_database_error(exc: duckdb.Error, db_path: str) -> RuntimeError:
    """Turn a missing local store into the same repair path used by Make."""
    dataset = os.environ.get("GROUNDED_PACK", "fixture")
    message = (
        f"Dataset database is unavailable at {db_path}. "
        f"Run `make spine DATASET={dataset}` and retry."
    )
    if os.environ.get("GROUNDED_DEBUG"):
        message = f"{message} Debug: {exc}"
    return RuntimeError(message)


def _load_customers_definition() -> dict[str, Any]:
    with (_SEMANTICS_DIRECTORY / "customers.yml").open(
        encoding="utf-8"
    ) as definition_file:
        return yaml.safe_load(definition_file)


def _load_metric_definition(metric: str) -> dict[str, Any]:
    return load_expanded_definition(metric)


def _verify_status(verification: list[dict]) -> str:
    return (
        "pass" if all(result["status"] == "pass" for result in verification) else "fail"
    )


def _union_records(*groups: list[dict]) -> list[dict]:
    """Combine declared policy records while preserving their first-seen order."""
    combined: list[dict] = []
    for group in groups:
        for record in group:
            if record not in combined:
                combined.append(record)
    return combined


def _with_inherited_policies(
    definition: dict, inherited_policies: list[dict] | None
) -> dict:
    """Provide parent policy declarations to a composed child without changing enforcement."""
    if not inherited_policies:
        return definition
    effective = deepcopy(definition)
    effective["policies"] = _union_records(
        effective.get("policies", []), inherited_policies
    )
    return effective


def _cube_filters_for_row_decisions(row_decisions: list[dict]) -> list[dict[str, Any]]:
    """Translate the declared Contract-B row policies into trusted Cube filters."""
    cube_filters: list[dict[str, Any]] = []
    for decision in row_decisions:
        member = decision.get("cube_member")
        declared_operator = decision.get("operator")
        values = decision.get("values")
        if (
            not isinstance(member, str)
            or not member
            or declared_operator not in _CUBE_FILTER_OPERATORS
            or not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) for value in values)
        ):
            raise ValueError(
                "A Cube row-filter policy must declare cube_member, operator, and string values."
            )
        if not cube.has_dimension_member(member):
            raise ValueError(
                f"Declared Cube row-filter member does not exist: {member}"
            )
        cube_filters.append(
            {
                "member": member,
                "operator": _CUBE_FILTER_OPERATORS[declared_operator],
                "values": values,
            }
        )
    return cube_filters


def _ratio_rows(
    numerator_rows: list[dict],
    denominator_rows: list[dict],
    dimensions: list[str],
    numerator_metric: str,
    denominator_metric: str,
    metric: str,
) -> tuple[list[dict], bool]:
    """Align parent dimension rows and calculate a two-decimal ratio without division by zero."""
    key_for = lambda row: tuple(row.get(dimension) for dimension in dimensions)
    numerator_by_key = {key_for(row): row for row in numerator_rows}
    denominator_by_key = {key_for(row): row for row in denominator_rows}
    rows: list[dict] = []
    zero_denominator = False
    for key in [
        *numerator_by_key,
        *(key for key in denominator_by_key if key not in numerator_by_key),
    ]:
        numerator = numerator_by_key.get(key, {}).get(numerator_metric, Decimal(0))
        denominator = denominator_by_key.get(key, {}).get(
            denominator_metric, Decimal(0)
        )
        row = {
            dimension: value for dimension, value in zip(dimensions, key, strict=True)
        }
        if denominator in (None, 0):
            row[metric] = None
            zero_denominator = True
        else:
            row[metric] = (Decimal(numerator) / Decimal(denominator)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        rows.append(row)
    return (
        sorted(
            rows,
            key=lambda row: (
                row[metric] is None,
                -(row[metric] if row[metric] is not None else Decimal(0)),
                tuple(str(row.get(dimension, "")) for dimension in dimensions),
            ),
        ),
        zero_denominator,
    )


def _audit_record(
    *,
    role: str,
    tool: str,
    target: str,
    dimensions: list[str],
    filters: dict,
    policy_decisions: list[dict],
    verify_status: str,
    row_count: int,
) -> dict:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "role": role,
        "tool": tool,
        "target": target,
        "dimensions": dimensions,
        "filters": filters,
        "policy_decisions": policy_decisions,
        "verify_status": verify_status,
        "row_count": row_count,
    }


def _governed_ratio(
    definition: dict,
    dimensions: list[str] | None,
    filters: dict | None,
    role: str,
    reference_date: str,
    db_path: str,
    backend: str = "fixture",
    cube_url: str | None = None,
) -> dict:
    """Compose a derived ratio from fully governed parent metrics."""
    ratio = definition["definition"]
    numerator_metric = ratio["numerator"]
    denominator_metric = ratio["denominator"]
    inherited_policies = definition.get("policies", [])
    numerator = governed_query(
        numerator_metric,
        dimensions,
        filters,
        role,
        reference_date,
        db_path,
        backend=backend,
        cube_url=cube_url,
        _inherited_policies=inherited_policies,
    )
    denominator = governed_query(
        denominator_metric,
        dimensions,
        filters,
        role,
        reference_date,
        db_path,
        backend=backend,
        cube_url=cube_url,
        _inherited_policies=inherited_policies,
    )
    requested_dimensions = dimensions or []
    rows, zero_denominator = _ratio_rows(
        numerator["rows"],
        denominator["rows"],
        requested_dimensions,
        numerator_metric,
        denominator_metric,
        definition["metric"],
    )
    verification = verify_result(
        [row for row in rows if row[definition["metric"]] is not None],
        definition.get("verification", []),
    )
    if zero_denominator:
        verification.append(
            {
                "type": "division_by_zero",
                "field": definition["metric"],
                "status": "pass",
                "detail": "Denominator was zero; returned null instead of dividing by zero.",
            }
        )
    verify_status = _verify_status(verification)
    policy_decisions = _union_records(
        numerator["policy_decisions"], denominator["policy_decisions"]
    )
    result = {
        "metric": definition["metric"],
        "dimensions": requested_dimensions,
        "filters": filters or {},
        "columns": [*requested_dimensions, definition["metric"]],
        "rows": rows,
        "row_count": numerator["row_count"],
        "sql": f"DERIVED {definition['metric']} = {numerator_metric} / {denominator_metric}",
        "resolved_definition": definition,
        "role": role,
        "policy_decisions": policy_decisions,
        "verification": verification,
        "verify_status": verify_status,
    }
    append_audit(
        _audit_record(
            role=role,
            tool="query_metric",
            target=definition["metric"],
            dimensions=requested_dimensions,
            filters=filters or {},
            policy_decisions=policy_decisions,
            verify_status=verify_status,
            row_count=result["row_count"],
        )
    )
    return result


def governed_query(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict | None = None,
    role: str = "viewer",
    reference_date: str = "2026-08-12",
    db_path: str = "grounded.duckdb",
    backend: str = "fixture",
    cube_url: str | None = None,
    _inherited_policies: list[dict] | None = None,
) -> dict:
    """Execute one governed metric query, then verify and audit the result."""
    definition = _with_inherited_policies(
        _load_metric_definition(metric), _inherited_policies
    )
    if definition.get("definition", {}).get("derived") == "ratio":
        return _governed_ratio(
            definition,
            dimensions,
            filters,
            role,
            reference_date,
            db_path,
            backend,
            cube_url,
        )
    row_decisions = row_predicates_for_role(definition, role)
    try:
        result = resolve_and_run(
            metric,
            dimensions,
            filters,
            reference_date,
            db_path,
            row_predicates=[decision["predicate"] for decision in row_decisions]
            if backend == "fixture"
            else None,
            backend=backend,
            cube_filters=_cube_filters_for_row_decisions(row_decisions)
            if backend == "cube"
            else None,
            cube_url=cube_url,
        )
    except duckdb.Error as exc:
        raise _missing_database_error(exc, db_path) from exc
    result["resolved_definition"] = definition
    masked_rows, masking_decisions = apply_masking(result["rows"], definition, role)
    policy_decisions = [*row_decisions, *masking_decisions]
    verification = verify_result(masked_rows, definition.get("verification", []))
    verify_status = _verify_status(verification)
    result.update(
        {
            "rows": masked_rows,
            "role": role,
            "policy_decisions": policy_decisions,
            "verification": verification,
            "verify_status": verify_status,
        }
    )
    append_audit(
        _audit_record(
            role=role,
            tool="query_metric",
            target=metric,
            dimensions=result["dimensions"],
            filters=result["filters"],
            policy_decisions=policy_decisions,
            verify_status=verify_status,
            row_count=result["row_count"],
        )
    )
    return result


def governed_customers(role: str = "viewer", db_path: str = "grounded.duckdb") -> dict:
    """Read the governed customer directory, mask PII, verify, and audit it."""
    definition = _load_customers_definition()
    try:
        connection = duckdb.connect(db_path, read_only=True)
    except duckdb.Error as exc:
        raise _missing_database_error(exc, db_path) from exc
    try:
        cursor = connection.execute(
            "SELECT name, country, email FROM customer_directory ORDER BY name ASC"
        )
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()

    masked_rows, policy_decisions = apply_masking(rows, definition, role)
    verification = verify_result(masked_rows, definition.get("verification", []))
    verify_status = _verify_status(verification)
    result = {
        "read": definition["read"],
        "columns": columns,
        "rows": masked_rows,
        "row_count": len(masked_rows),
        "role": role,
        "policy_decisions": policy_decisions,
        "verification": verification,
        "verify_status": verify_status,
    }
    append_audit(
        _audit_record(
            role=role,
            tool="customer_directory",
            target=definition["read"],
            dimensions=[],
            filters={},
            policy_decisions=policy_decisions,
            verify_status=verify_status,
            row_count=result["row_count"],
        )
    )
    return result
