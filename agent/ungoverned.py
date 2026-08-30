"""Deliberately naive raw-SQL control arm for governed-vs-ungoverned evaluation."""

from __future__ import annotations

import re
from typing import Any

import duckdb

from models.provider import LLMProvider

UNGOVERNED_SYSTEM_PROMPT = """Answer the user's question by returning one SQL SELECT statement.
You have a raw DuckDB schema:
- customers(customer_id, name, email, country, created_at)
- products(product_id, name, category, price)
- orders(order_id, customer_id, order_ts, status)
- order_items(order_id, product_id, quantity, unit_price)

Return SQL only. You may use joins and aggregations, but do not use markdown or explanations."""

AW_GOLD_SYSTEM_PROMPT = """Answer the user's question by returning one SQL SELECT statement.
You have an AdventureWorks gold star schema in DuckDB:
- gold.fct_sales(product_key, customer_key, territory_key, date_key, order_id, line_number,
  order_date, quantity, unit_price, line_total, standard_cost, status_code, order_status,
  is_completed)
- gold.dim_product(product_key, product_id, product_name, category, subcategory,
  standard_cost, list_price)
- gold.dim_customer(customer_key, customer_id, customer_type, full_name, email)
- gold.dim_territory(territory_key, territory_id, territory_name, country_region)
- gold.dim_date(date_key, full_date, year, month, quarter)

Join facts to dimensions by their *_key fields. Revenue is SUM(line_total) for
is_completed = TRUE; completed orders are distinct order_id values under that same filter.
Return SQL only. You may use joins and aggregations, but do not use markdown or explanations."""

_STEELMAN_EXAMPLES = """Generic SQL examples (illustrative only; not evaluation questions):
Question: Count rows in a relation.
SQL: SELECT COUNT(*) AS row_count FROM schema_name.table_name
Question: Sum a numeric column by a categorical column.
SQL: SELECT category, SUM(amount) AS total FROM schema_name.table_name GROUP BY category
Question: Filter a date range before aggregating.
SQL: SELECT SUM(amount) AS total FROM schema_name.table_name WHERE event_date >= DATE '2026-01-01'
"""


def pack_schema_prompt(db_path: str, pack_name: str, has_transform: bool = True) -> str:
    """Describe the active pack's queryable gold or bronze schema for the control arm."""
    schema = "gold" if has_transform else "bronze"
    connection = duckdb.connect(db_path, read_only=True)
    try:
        rows = connection.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = ?
            ORDER BY table_name, ordinal_position
            """
            ,
            [schema],
        ).fetchall()
    finally:
        connection.close()
    columns_by_table: dict[str, list[tuple[str, str]]] = {}
    for table, column, data_type in rows:
        columns_by_table.setdefault(table, []).append((column, data_type))
    if not columns_by_table:
        raise ValueError(f"Pack {pack_name!r} has no {schema} schema at {db_path}")
    relations = "\n".join(
        f"- {schema}.{table}({', '.join(column for column, _ in columns)}) "
        f"[types: {', '.join(f'{column} {data_type}' for column, data_type in columns)}]"
        for table, columns in columns_by_table.items()
    )
    return "\n".join(
        [
            "Answer the user's question by returning one SQL SELECT statement.",
            f"You have the {pack_name} {schema} schema in DuckDB:",
            relations,
            "",
            "Join facts to dimensions by their declared key fields.",
            _STEELMAN_EXAMPLES,
            "Return SQL only. You may use joins and aggregations, but do not use markdown or explanations.",
        ]
    )


def gold_schema_prompt(db_path: str, pack_name: str) -> str:
    """Backward-compatible gold-only prompt helper for transformed packs."""
    return pack_schema_prompt(db_path, pack_name)


def _prompt_for_dataset(dataset: str) -> str:
    if dataset == "fixture":
        return UNGOVERNED_SYSTEM_PROMPT
    if dataset == "aw":
        return AW_GOLD_SYSTEM_PROMPT
    raise ValueError("dataset must be either 'fixture' or 'aw'.")


def _single_select(sql: str) -> bool:
    """Allow one SELECT/WITH query only; refuse empty, multi-statement, and write SQL."""
    stripped = sql.strip()
    if not stripped:
        return False
    if ";" in stripped:
        if not stripped.endswith(";") or stripped.count(";") != 1:
            return False
        stripped = stripped[:-1].strip()
    statement = stripped.lstrip()
    return bool(re.match(r"(?is)^(select|with)\b", statement))


def _failure_reason(error: str | None) -> str | None:
    if error is None:
        return None
    lowered = error.casefold()
    if "column" in lowered:
        return "wrong_column"
    if "table" in lowered or "catalog" in lowered:
        return "wrong_table"
    if "join" in lowered:
        return "wrong_join"
    if "select statement" in lowered:
        return "unsafe_or_nonselect_sql"
    return "execution_error"


def answer_ungoverned(
    question: str,
    provider: LLMProvider,
    db_path: str = "grounded.duckdb",
    *,
    dataset: str = "fixture",
    system_prompt: str | None = None,
    max_attempts: int = 2,
) -> dict[str, Any]:
    """Ask for raw SQL, retrying one bounded time only after an execution error."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    prompt = system_prompt or _prompt_for_dataset(dataset)
    raw_sql = ""
    for attempts in range(1, max_attempts + 1):
        raw_sql = provider.complete(prompt, question)
        sql = raw_sql.strip()
        if not _single_select(sql):
            error = "only one SELECT statement is allowed"
        else:
            try:
                connection = duckdb.connect(db_path, read_only=True)
                try:
                    cursor = connection.execute(sql)
                    columns = [column[0] for column in cursor.description]
                    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                finally:
                    connection.close()
            except duckdb.Error as exc:
                error = str(exc)
            else:
                return {"raw_sql": raw_sql, "sql": sql, "rows": rows, "schema_break": False, "rejection_reason": None, "error": None, "attempts": attempts, "execution_success": True, "failure_reason": None}
        if attempts < max_attempts:
            prompt = f"{prompt}\nPrevious SQL failed with: {error}\nReturn a corrected single SELECT only."
    return {"raw_sql": raw_sql, "sql": sql, "rows": None, "schema_break": True, "rejection_reason": error, "error": error, "attempts": attempts, "execution_success": False, "failure_reason": _failure_reason(error)}
