"""The deterministic DuckDB fixture resolver used by the PoC test suite."""

from __future__ import annotations

from datetime import date
import re
from typing import Any

import duckdb

from semantics.loader import load_expanded_definition


class UnknownMetricError(ValueError):
    """Raised when no governed metric definition exists for a requested metric."""


class UndeclaredFieldError(ValueError):
    """Raised when a request names a dimension or filter outside Contract B."""


_DIMENSION_COLUMNS = {
    "products.category": "category",
    "orders.order_ts": "order_month",
    "customers.country": "country",
}


def _load_definition(metric: str) -> dict[str, Any]:
    try:
        return load_expanded_definition(metric)
    except FileNotFoundError as exc:
        raise UnknownMetricError(f"Unknown governed metric: {metric}") from exc


def _last_month_window(reference_date: str) -> tuple[date, date]:
    reference = date.fromisoformat(reference_date)
    current_month_start = reference.replace(day=1)
    if current_month_start.month == 1:
        previous_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
    else:
        previous_month_start = current_month_start.replace(month=current_month_start.month - 1)
    return previous_month_start, current_month_start


def _dimension_columns(definition: dict[str, Any]) -> dict[str, str]:
    return {
        dimension["name"]: _DIMENSION_COLUMNS[dimension["source"]]
        for dimension in definition["dimensions"]
    }


def _validate_request(
    dimensions: list[str], filters: dict[str, Any], declared_dimensions: dict[str, str]
) -> None:
    for dimension in dimensions:
        if dimension not in declared_dimensions:
            raise UndeclaredFieldError(f"Undeclared dimension: {dimension}")
    for filter_name, filter_value in filters.items():
        if filter_name != "order_month":
            raise UndeclaredFieldError(f"Undeclared filter: {filter_name}")
        if filter_name not in declared_dimensions:
            raise UndeclaredFieldError(f"Undeclared filter: {filter_name}")
        if filter_value != "last_month":
            raise UndeclaredFieldError("Only the declared order_month=last_month filter is supported")


def _compile_measure(definition: dict[str, Any]) -> str:
    """Compile only the declared sum and count-distinct measure forms to mart SQL."""
    measure = definition["definition"]["measure"]
    sum_match = re.fullmatch(r"sum\(([^()]+)\)", measure)
    if sum_match:
        expressions = {"order_items.quantity * order_items.unit_price": "quantity * unit_price"}
        expression = expressions.get(sum_match.group(1).strip())
        if expression is not None:
            return f"SUM({expression})"
    count_match = re.fullmatch(r"count_distinct\(([^()]+)\)", measure)
    if count_match:
        columns = {"orders.order_id": "order_id"}
        column = columns.get(count_match.group(1).strip())
        if column is not None:
            return f"COUNT(DISTINCT {column})"
    raise UnknownMetricError(f"Unsupported governed measure for metric: {definition['metric']}")


def resolve_and_run(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict | None = None,
    reference_date: str = "2026-08-12",
    db_path: str = "grounded.duckdb",
    row_predicates: list[str] | None = None,
) -> dict:
    """Resolve one declared base metric, execute its compiled SQL, and return results."""
    requested_dimensions = dimensions or []
    requested_filters = filters or {}
    definition = _load_definition(metric)
    if definition.get("definition", {}).get("derived"):
        raise UnknownMetricError(f"Derived metric must be resolved through governed service: {metric}")
    declared_dimensions = _dimension_columns(definition)
    _validate_request(requested_dimensions, requested_filters, declared_dimensions)

    select_dimensions = [declared_dimensions[dimension] for dimension in requested_dimensions]
    select_clause = ", ".join(select_dimensions)
    if select_clause:
        select_clause += ", "
    group_by_clause = f"GROUP BY {', '.join(select_dimensions)}" if select_dimensions else ""
    order_by_clause = f"ORDER BY {metric} DESC"
    if select_dimensions:
        order_by_clause += f", {', '.join(select_dimensions)} ASC"

    where_clauses = ["status = 'completed'"]
    if requested_filters.get("order_month") == "last_month":
        window_start, window_end = _last_month_window(reference_date)
        where_clauses.extend(
            [
                f"order_month >= DATE '{window_start.isoformat()}'",
                f"order_month < DATE '{window_end.isoformat()}'",
            ]
        )
    for predicate in row_predicates or []:
        where_clauses.append(f"({predicate})")

    sql = "\n".join(
        part
        for part in [
            f"SELECT {select_clause}CAST({_compile_measure(definition)} AS DECIMAL(18, 2)) AS {metric},",
            "       SUM(COUNT(*)) OVER () AS _row_count",
            "FROM mart_revenue",
            f"WHERE {' AND '.join(where_clauses)}",
            group_by_clause,
            order_by_clause,
        ]
        if part
    )

    connection = duckdb.connect(db_path, read_only=True)
    try:
        cursor = connection.execute(sql)
        columns = [column[0] for column in cursor.description]
        result_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()

    row_count = result_rows[0].pop("_row_count") if result_rows else 0
    for row in result_rows[1:]:
        row.pop("_row_count")
    return {
        "metric": metric,
        "dimensions": requested_dimensions,
        "filters": requested_filters,
        "columns": [*select_dimensions, metric],
        "rows": result_rows,
        "row_count": row_count,
        "sql": sql,
        "resolved_definition": definition,
    }
