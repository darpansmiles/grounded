"""Offline, independently grounded scoring for captured benchmark executions.

This module deliberately has no dependency on ``governed.service`` or the
resolver.  It reads capture JSONL and computes expected rows through a second,
plain DuckDB implementation over the committed pack data.  That keeps model
collection expensive but scoring repeatable and makes a resolver regression
observable rather than self-confirming.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import duckdb

from agent.ungoverned import extract_sql, is_single_select


class TruthUnavailable(RuntimeError):
    """Raised when a capture cannot be checked against an independent truth."""


@dataclass(frozen=True)
class _Recipe:
    from_sql: str
    dimensions: dict[str, str]
    measures: dict[str, str]
    role_predicates: dict[str, str]
    base_predicate: str


_RECIPES: dict[str, _Recipe] = {
    "fixture": _Recipe(
        from_sql="mart_revenue AS m",
        dimensions={
            "category": "m.category",
            "country": "m.country",
            "order_month": "date_trunc('month', m.order_month)",
        },
        measures={
            "revenue": "SUM(m.line_revenue)",
            "orders": "COUNT(DISTINCT m.order_id)",
            "aov": "SUM(m.line_revenue) / NULLIF(COUNT(DISTINCT m.order_id), 0)",
        },
        role_predicates={"eu_analyst": "m.country IN ('DE', 'FR', 'NL')"},
        base_predicate="m.status = 'completed'",
    ),
    "adventureworks": _Recipe(
        from_sql=(
            "gold.fct_sales AS f "
            "JOIN gold.dim_product AS p ON f.product_key = p.product_key "
            "JOIN gold.dim_territory AS t ON f.territory_key = t.territory_key "
            "JOIN gold.dim_date AS d ON f.date_key = d.date_key"
        ),
        dimensions={
            "category": "p.category",
            "country": "t.country_region",
            "order_month": "date_trunc('month', d.full_date)",
        },
        measures={
            "revenue": "SUM(f.line_total)",
            "orders": "COUNT(DISTINCT f.order_id)",
            "units_sold": "SUM(f.quantity)",
            "customers": "COUNT(DISTINCT f.customer_key)",
            "aov": "SUM(f.line_total) / NULLIF(COUNT(DISTINCT f.order_id), 0)",
            "average_unit_price": "SUM(f.line_total) / NULLIF(SUM(f.quantity), 0)",
            "revenue_per_customer": "SUM(f.line_total) / NULLIF(COUNT(DISTINCT f.customer_key), 0)",
            "orders_per_customer": "COUNT(DISTINCT f.order_id) / NULLIF(COUNT(DISTINCT f.customer_key), 0)",
        },
        role_predicates={"eu_analyst": "t.country_region IN ('DE', 'FR', 'NL')"},
        base_predicate="f.is_completed = TRUE",
    ),
    "tpch": _Recipe(
        from_sql=(
            "gold.fct_lineitem AS f "
            "JOIN gold.dim_part AS p ON f.part_key = p.part_key "
            "JOIN gold.dim_customer AS c ON f.customer_key = c.customer_key "
            "JOIN gold.dim_nation AS n ON f.nation_key = n.nation_key "
            "JOIN gold.dim_region AS r ON f.region_key = r.region_key "
            "JOIN gold.dim_orderdate AS d ON f.order_date_key = d.order_date_key"
        ),
        dimensions={
            "nation": "n.nation",
            "region": "r.region",
            "market_segment": "c.market_segment",
            "part_brand": "p.part_brand",
            "part_type": "p.part_type",
            "order_month": "date_trunc('month', d.order_date)",
        },
        measures={
            "revenue": "SUM(f.extended_price * (1 - f.discount))",
            "orders": "COUNT(DISTINCT f.order_key)",
            "units_sold": "SUM(f.quantity)",
            "customers": "COUNT(DISTINCT f.customer_key)",
            "aov": "SUM(f.extended_price * (1 - f.discount)) / NULLIF(COUNT(DISTINCT f.order_key), 0)",
            "average_unit_price": "SUM(f.extended_price * (1 - f.discount)) / NULLIF(SUM(f.quantity), 0)",
            "margin": "SUM(f.extended_price * (1 - f.discount) - f.supply_cost * f.quantity)",
        },
        role_predicates={"eu_analyst": "r.region = 'EUROPE'"},
        base_predicate="f.is_completed = TRUE",
    ),
    "spider_world1": _Recipe(
        from_sql='bronze.country AS c',
        dimensions={"continent": 'c."Continent"', "region": 'c."Region"'},
        measures={
            "total_population": 'SUM(c."Population")',
            "country_count": 'COUNT(c."Code")',
            "total_gnp": 'SUM(c."GNP")',
        },
        role_predicates={"eu_analyst": "c.Continent = 'Europe'"},
        base_predicate="TRUE",
    ),
    "bird_ca_schools": _Recipe(
        from_sql='bronze.schools AS s',
        dimensions={"county": 's."County"'},
        measures={"school_count": 'COUNT(s."CDSCode")'},
        role_predicates={},
        base_predicate="TRUE",
    ),
}


def _canonical(value: Any) -> Any:
    """Normalise DuckDB/Python values without conflating null, zero, or emptiness."""
    if isinstance(value, Decimal):
        return value.normalize()
    if isinstance(value, float):
        return Decimal(str(value)).normalize()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def _row_key(row: dict[str, Any], *, alias_map: dict[str, str] | None = None) -> tuple[tuple[str, Any], ...]:
    aliases = alias_map or {}
    return tuple(sorted((aliases.get(key, key), _canonical(value)) for key, value in row.items()))


def rows_match(
    actual: list[dict[str, Any]] | None,
    expected: list[dict[str, Any]] | None,
    *,
    alias_map: dict[str, str] | None = None,
    metric: str | None = None,
) -> bool:
    """Compare answer rows as multisets, retaining duplicate-result failures.

    Metric tolerances are declared per metric below.  All current public
    result surfaces quantize to cents/two decimals, so the independent SQL
    does the same and each declared tolerance is exact zero rather than a
    post-hoc global cushion.
    """
    if actual is None or expected is None:
        return False
    if metric is not None:
        return _rows_match_with_metric_tolerance(actual, expected, metric, alias_map)
    return Counter(_row_key(row, alias_map=alias_map) for row in actual) == Counter(
        _row_key(row, alias_map=alias_map) for row in expected
    )


_METRIC_TOLERANCES: dict[str, Decimal] = {
    "revenue": Decimal(0),
    "orders": Decimal(0),
    "aov": Decimal(0),
    "units_sold": Decimal(0),
    "customers": Decimal(0),
    "average_unit_price": Decimal(0),
    "revenue_per_customer": Decimal(0),
    "orders_per_customer": Decimal(0),
    "margin": Decimal(0),
    "total_population": Decimal(0),
    "country_count": Decimal(0),
    "total_gnp": Decimal(0),
    "school_count": Decimal(0),
    "total_enrollment": Decimal(0),
    "avg_sat_math": Decimal(0),
}


def _rows_match_with_metric_tolerance(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    metric: str,
    alias_map: dict[str, str] | None,
) -> bool:
    if metric not in _METRIC_TOLERANCES or len(actual) != len(expected):
        return False
    aliases = alias_map or {}
    unmatched = [{aliases.get(key, key): _canonical(value) for key, value in row.items()} for row in expected]
    for raw_actual in actual:
        actual_row = {aliases.get(key, key): _canonical(value) for key, value in raw_actual.items()}
        match_index = next(
            (
                index
                for index, expected_row in enumerate(unmatched)
                if _row_matches(actual_row, expected_row, metric, _METRIC_TOLERANCES[metric])
            ),
            None,
        )
        if match_index is None:
            return False
        unmatched.pop(match_index)
    return not unmatched


def _row_matches(
    actual: dict[str, Any], expected: dict[str, Any], metric: str, tolerance: Decimal
) -> bool:
    if set(actual) != set(expected):
        return False
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if key != metric:
            if actual_value != expected_value:
                return False
            continue
        if actual_value is None or expected_value is None:
            if actual_value != expected_value:
                return False
            continue
        try:
            if abs(Decimal(str(actual_value)) - Decimal(str(expected_value))) > tolerance:
                return False
        except (InvalidOperation, TypeError, ValueError):
            return False
    return True


_METRIC_ALIASES: dict[str, set[str]] = {
    "revenue": {"total_revenue", "sales", "total_sales"},
    "orders": {"order_count", "total_orders", "number_of_orders"},
    "aov": {"average_order_value", "average_value_per_order"},
    "units_sold": {"total_units", "units"},
    "customers": {"customer_count", "total_customers"},
    "average_unit_price": {"avg_unit_price"},
    "revenue_per_customer": {"avg_revenue_per_customer"},
    "orders_per_customer": {"avg_orders_per_customer"},
    "total_population": {"population"},
    "country_count": {"countries"},
    "total_gnp": {"gnp"},
    "school_count": {"schools"},
    "total_enrollment": {"enrollment"},
    "avg_sat_math": {"average_sat_math"},
}


def _aliases_for_metric(metric: str) -> dict[str, str]:
    """Allow documented semantic aliases, and reject every other extra field."""
    return {alias: metric for alias in _METRIC_ALIASES.get(metric, set())}


def _last_month_predicate(expression: str) -> str:
    # The fixture and pack capture contract fixes the reference date at 2026-08-12.
    return f"{expression} >= DATE '2026-07-01' AND {expression} < DATE '2026-08-01'"


def independent_rows(
    dataset: str,
    plan: dict[str, Any],
    role: str,
    *,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Calculate expected metric rows with independent, direct DuckDB SQL.

    The expressions are an explicit second implementation of each public metric
    contract.  They neither call nor import the resolver, governed service, or
    Cube API.  Every numeric result is rounded to the public two-decimal Cube
    representation only after the direct calculation, matching the documented
    response boundary rather than the resolver's internal execution.
    """
    if dataset not in _RECIPES:
        raise TruthUnavailable(f"No independent SQL recipe is declared for {dataset!r}.")
    if plan.get("tool") != "query_metric":
        raise TruthUnavailable("Only declared metric calls have independent row truth.")
    args = plan.get("args", {})
    metric = args.get("metric")
    dimensions = args.get("dimensions", [])
    filters = args.get("filters", {})
    if dataset == "bird_ca_schools":
        return _bird_independent_rows(
            metric, dimensions, filters, db_path=db_path
        )
    recipe = _RECIPES[dataset]
    if not isinstance(metric, str) or metric not in recipe.measures:
        raise TruthUnavailable(f"No independent SQL measure is declared for {metric!r}.")
    if not isinstance(dimensions, list) or any(dimension not in recipe.dimensions for dimension in dimensions):
        raise TruthUnavailable("Metric call includes an undeclared independent dimension.")
    if not isinstance(filters, dict) or set(filters) - {"order_month"}:
        raise TruthUnavailable("Metric call includes an undeclared independent filter.")
    if filters.get("order_month") not in {None, "last_month"}:
        raise TruthUnavailable("Only the declared order_month=last_month filter is supported.")

    select_dimensions = [f"{recipe.dimensions[dimension]} AS \"{dimension}\"" for dimension in dimensions]
    predicates = [recipe.base_predicate]
    if role in recipe.role_predicates:
        predicates.append(recipe.role_predicates[role])
    if filters.get("order_month") == "last_month":
        predicates.append(_last_month_predicate(recipe.dimensions["order_month"]))
    query = "\n".join(
        [
            "SELECT",
            "  " + ",\n  ".join(
                [*select_dimensions, f"ROUND({recipe.measures[metric]}, 2) AS \"{metric}\""]
            ),
            f"FROM {recipe.from_sql}",
            "WHERE " + " AND ".join(predicates),
            *( ["GROUP BY " + ", ".join(recipe.dimensions[dimension] for dimension in dimensions)] if dimensions else [] ),
        ]
    )
    path = Path(db_path) if db_path is not None else Path("data") / f"{dataset}.duckdb"
    if not path.exists():
        raise TruthUnavailable(f"Independent truth database is unavailable: {path}")
    connection = duckdb.connect(str(path), read_only=True)
    try:
        cursor = connection.execute(query)
        columns = [column[0] for column in cursor.description]
        return [{column: _canonical(value) for column, value in zip(columns, row)} for row in cursor.fetchall()]
    finally:
        connection.close()


def _bird_independent_rows(
    metric: Any,
    dimensions: Any,
    filters: Any,
    *,
    db_path: str | Path | None,
) -> list[dict[str, Any]]:
    """Evaluate BIRD's three independent bronze-table measures directly."""
    sources = {
        "school_count": ('bronze.schools AS s', 's."County"', 'COUNT(s."CDSCode")'),
        "total_enrollment": (
            'bronze.frpm AS f',
            'f."County Name"',
            'SUM(f."Enrollment (K-12)")',
        ),
        "avg_sat_math": ('bronze.satscores AS s', 's."cname"', 'AVG(s."AvgScrMath")'),
    }
    if metric not in sources:
        raise TruthUnavailable(f"No independent SQL measure is declared for {metric!r}.")
    if not isinstance(dimensions, list) or any(dimension != "county" for dimension in dimensions):
        raise TruthUnavailable("BIRD metric call includes an undeclared independent dimension.")
    if not isinstance(filters, dict) or filters:
        raise TruthUnavailable("BIRD metric call includes an undeclared independent filter.")
    from_sql, county, measure = sources[metric]
    select_dimensions = [f'{county} AS "county"'] if dimensions else []
    query = "\n".join(
        [
            "SELECT",
            "  " + ",\n  ".join(
                [*select_dimensions, f'ROUND({measure}, 2) AS "{metric}"']
            ),
            f"FROM {from_sql}",
            *( [f"GROUP BY {county}"] if dimensions else [] ),
        ]
    )
    path = Path(db_path) if db_path is not None else Path("data/bird_ca_schools.duckdb")
    if not path.exists():
        raise TruthUnavailable(f"Independent truth database is unavailable: {path}")
    connection = duckdb.connect(str(path), read_only=True)
    try:
        cursor = connection.execute(query)
        columns = [column[0] for column in cursor.description]
        return [
            {column: _canonical(value) for column, value in zip(columns, row)}
            for row in cursor.fetchall()
        ]
    finally:
        connection.close()


def _question_group(record: dict[str, Any]) -> str:
    expected_type = record.get("expect", {}).get("type")
    category = str(record.get("category", ""))
    if expected_type == "refuse" or category.startswith("refuse"):
        return "ambiguous_forbidden_unsupported"
    if expected_type == "metric":
        return "in_catalog"
    return "ambiguous_forbidden_unsupported"


def _is_refusal_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().casefold().startswith(("i can't", "i cannot", "unable", "insufficient"))


def _expected_metric(record: dict[str, Any]) -> bool:
    return record.get("expect", {}).get("type") == "metric"


def _expected_refusal(record: dict[str, Any]) -> bool:
    return record.get("expect", {}).get("type") == "refuse"


def _has_required_evidence(record: dict[str, Any], metric: str) -> bool:
    evidence = record.get("evidence")
    if not isinstance(evidence, dict):
        return False
    response = record.get("governed_response")
    response_rows_match = not isinstance(response, dict) or response.get("answer_rows") == record.get("governed_rows")
    lineage = evidence.get("lineage_citation")
    return bool(
        evidence.get("metric_definition")
        and isinstance(lineage, str)
        and metric in lineage
        and evidence.get("verification") is not None
        and evidence.get("verify_status") == "pass"
        and response_rows_match
    )


def _policy_matches(record: dict[str, Any], rows: list[dict[str, Any]] | None) -> bool | None:
    """Check only policy obligations applicable to the requested role/case."""
    expected_type = record.get("expect", {}).get("type")
    if expected_type == "policy":
        expected_decision = record.get("expect", {}).get("decision")
        return any(
            isinstance(decision, dict) and decision.get("decision") == expected_decision
            for decision in record.get("policy_decisions") or []
        )
    if not _expected_metric(record):
        return None
    role = record.get("role")
    if role != "eu_analyst":
        return None
    policy_decisions = record.get("policy_decisions") or []
    has_row_filter = any(
        isinstance(decision, dict) and decision.get("rule") == "row_filter"
        for decision in policy_decisions
    )
    if not has_row_filter:
        return False
    if rows is None:
        return False
    dataset = record.get("dataset")
    constrained_dimension = "country" if dataset in {"fixture", "adventureworks"} else "region"
    allowed = {"DE", "FR", "NL"} if constrained_dimension == "country" else {"EUROPE"}
    return all(
        constrained_dimension not in row or row[constrained_dimension] in allowed
        for row in rows
    )


def _answer_label(expected_refusal: bool, answered: bool, correctness: str) -> str:
    if expected_refusal:
        return "wrong_answer" if answered else "correct_refusal"
    if not answered:
        return "over_refusal"
    if correctness == "correct":
        return "correct_answer"
    if correctness == "wrong":
        return "wrong_answer"
    return "unscored"


def score_record(
    record: dict[str, Any], *, dataset: str, db_path: str | Path | None = None
) -> dict[str, Any]:
    """Score captured governed and raw attempts without model or resolver calls."""
    record = {**record, "dataset": dataset}
    expected_refusal = _expected_refusal(record)
    expected_metric = _expected_metric(record)
    expected_rows: list[dict[str, Any]] | None = None
    truth_error: str | None = None
    if expected_metric:
        try:
            expected_rows = independent_rows(
                dataset, record["expected_plan"], record["role"], db_path=db_path
            )
        except TruthUnavailable as exc:
            truth_error = str(exc)
    metric = record.get("expected_plan", {}).get("args", {}).get("metric", "")
    aliases = _aliases_for_metric(metric) if isinstance(metric, str) else {}

    governed_plan = record.get("produced_plan") or {}
    governed_answered = governed_plan.get("tool") != "refuse" and bool(record.get("governed_executed"))
    governed_rows = record.get("governed_rows")
    governed_correctness = "n/a"
    if expected_metric and governed_answered and expected_rows is not None:
        governed_correctness = "correct" if rows_match(governed_rows, expected_rows, alias_map=aliases, metric=metric) else "wrong"
    elif expected_refusal and governed_plan.get("tool") != "refuse":
        governed_correctness = "wrong"
    governed_policy = _policy_matches(record, governed_rows)
    governed_evidence = (
        "complete" if expected_metric and _has_required_evidence(record, metric) else "incomplete"
        if expected_metric else "n/a"
    )

    raw = record.get("ungoverned") or {}
    raw_candidate = raw.get("raw_sql") or record.get("ungoverned_sql") or ""
    raw_sql = extract_sql(raw_candidate) if isinstance(raw_candidate, str) else ""
    raw_refusal = _is_refusal_text(raw_candidate)
    raw_rows = raw.get("rows") if raw else record.get("ungoverned_rows")
    raw_answered = not raw_refusal and bool(raw_sql)
    raw_correctness = "n/a"
    if expected_metric and raw_rows is not None and expected_rows is not None:
        raw_correctness = "correct" if rows_match(raw_rows, expected_rows, alias_map=aliases, metric=metric) else "wrong"
    elif expected_refusal and raw_answered:
        raw_correctness = "wrong"
    raw_policy = _policy_matches(record, raw_rows)
    raw_evidence = "incomplete" if expected_metric and raw_answered else "n/a"

    return {
        "case_id": record.get("case_id"),
        "model": record.get("model"),
        "run": record.get("run"),
        "group": _question_group(record),
        "truth_source": "direct_duckdb_sql" if expected_rows is not None else None,
        "truth_error": truth_error,
        "expected_rows": expected_rows,
        "governed": {
            "answer_correctness": governed_correctness,
            "interface_compliance": "compliant" if record.get("schema_valid") else "noncompliant",
            "policy_compliance": "n/a" if governed_policy is None else "compliant" if governed_policy else "noncompliant",
            "evidence_completeness": governed_evidence,
            "summary_label": _answer_label(expected_refusal, governed_answered, governed_correctness),
            "schema_break": "n/a",
        },
        "ungoverned": {
            "answer_correctness": raw_correctness,
            "interface_compliance": "compliant" if raw_refusal or is_single_select(raw_sql) else "noncompliant",
            "policy_compliance": "n/a" if raw_policy is None else "compliant" if raw_policy else "noncompliant",
            "evidence_completeness": raw_evidence,
            "summary_label": _answer_label(expected_refusal, raw_answered, raw_correctness),
            "schema_break": "n/a" if raw_refusal else bool(raw.get("schema_break", raw_rows is None)),
        },
    }


def _rate(matches: list[bool]) -> dict[str, int | float | None]:
    denominator = len(matches)
    numerator = sum(matches)
    return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator if denominator else None}


def _arm_summary(samples: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    values = [sample[arm] for sample in samples]
    answered = [value for value in values if value["answer_correctness"] in {"correct", "wrong"}]
    return {
        "answer_correctness_when_answered": _rate(
            [value["answer_correctness"] == "correct" for value in answered]
        ),
        "wrong_answer_rate": _rate([value["summary_label"] == "wrong_answer" for value in values]),
        "over_refusal_rate": _rate([value["summary_label"] == "over_refusal" for value in values]),
        "correct_refusal_rate": _rate([value["summary_label"] == "correct_refusal" for value in values]),
        "interface_compliance_rate": _rate(
            [value["interface_compliance"] == "compliant" for value in values if value["interface_compliance"] != "n/a"]
        ),
        "policy_compliance_rate": _rate(
            [value["policy_compliance"] == "compliant" for value in values if value["policy_compliance"] != "n/a"]
        ),
        "evidence_completeness_rate": _rate(
            [value["evidence_completeness"] == "complete" for value in values if value["evidence_completeness"] != "n/a"]
        ),
        "schema_break_rate": {"numerator": None, "denominator": None, "rate": None}
        if arm == "governed"
        else _rate([value["schema_break"] is True for value in values if value["schema_break"] != "n/a"]),
    }


def _capture_records(paths: list[str | Path]) -> tuple[str, list[dict[str, Any]]]:
    manifests: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item.get("record_type") == "manifest":
                manifests.append(item)
            elif item.get("record_type") == "case":
                records.append(item)
    datasets = {manifest.get("dataset") for manifest in manifests}
    if len(datasets) != 1 or None in datasets:
        raise ValueError("Offline scoring requires capture files for exactly one declared dataset.")
    return datasets.pop(), records


def evaluator_self_test() -> dict[str, bool]:
    """Prove that five known evaluator failures are observable before scoring."""
    base = {
        "dataset": "fixture",
        "case_id": "self-test",
        "model": "self-test",
        "run": 1,
        "category": "by_dimension",
        "role": "viewer",
        "expect": {"type": "metric"},
        "expected_plan": {"tool": "query_metric", "args": {"metric": "revenue", "dimensions": [], "filters": {"order_month": "last_month"}}},
        "produced_plan": {"tool": "query_metric", "args": {"metric": "revenue", "dimensions": [], "filters": {"order_month": "last_month"}}},
        "schema_valid": True,
        "governed_executed": True,
        "governed_rows": [{"revenue": 1185.0}],
        "policy_decisions": [],
        "evidence": {"metric_definition": {"measure": "sum"}, "lineage_citation": "revenue ← fixture lineage", "verification": [], "verify_status": "pass"},
        "ungoverned": {"raw_sql": "SELECT 1185 AS revenue", "rows": [{"revenue": 1185.0}], "schema_break": False},
    }
    wrong_metric = {
        **base,
        "produced_plan": {"tool": "query_metric", "args": {"metric": "orders", "dimensions": [], "filters": {"order_month": "last_month"}}},
        "governed_rows": [{"orders": 5.0}],
    }
    wrong_period = {
        **base,
        "produced_plan": {"tool": "query_metric", "args": {"metric": "revenue", "dimensions": [], "filters": {}}},
        "governed_rows": [{"revenue": 1635.0}],
    }
    duplicate = {**base, "governed_rows": [{"revenue": 1185.0}, {"revenue": 1185.0}]}
    missing_evidence = {**base, "evidence": None}
    forbidden_scope = {
        **base,
        "role": "eu_analyst",
        "governed_rows": [{"category": "Electronics", "revenue": 500.0}, {"category": "Books", "revenue": 280.0}],
        "expected_plan": {"tool": "query_metric", "args": {"metric": "revenue", "dimensions": ["category"], "filters": {"order_month": "last_month"}}},
        "produced_plan": {"tool": "query_metric", "args": {"metric": "revenue", "dimensions": ["category"], "filters": {"order_month": "last_month"}}},
    }
    return {
        "wrong_metric": score_record(wrong_metric, dataset="fixture")["governed"]["answer_correctness"] == "wrong",
        "wrong_period": score_record(wrong_period, dataset="fixture")["governed"]["answer_correctness"] == "wrong",
        "duplicate_result": score_record(duplicate, dataset="fixture")["governed"]["answer_correctness"] == "wrong",
        "missing_evidence": score_record(missing_evidence, dataset="fixture")["governed"]["evidence_completeness"] == "incomplete",
        "forbidden_scope": score_record(forbidden_scope, dataset="fixture")["governed"]["policy_compliance"] == "noncompliant",
    }


def score_capture_files(
    paths: list[str | Path], *, db_path: str | Path | None = None
) -> dict[str, Any]:
    """Score captured JSONL offline, rejecting output until the evaluator gate passes."""
    gate = evaluator_self_test()
    if not all(gate.values()):
        raise RuntimeError(f"Evaluator self-test failed: {gate}")
    dataset, records = _capture_records(paths)
    samples = [score_record(record, dataset=dataset, db_path=db_path) for record in records]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        grouped[str(sample.get("model"))].append(sample)
    return {
        "dataset": dataset,
        "source": "captured_jsonl",
        "evaluator_self_test": {"passed": True, "checks": gate},
        "models": {
            model: {
                "valid": all(
                    sample["truth_error"] is None
                    for sample in model_samples
                    if sample["group"] == "in_catalog"
                ),
                "groups": {
                    group: {
                        "governed": _arm_summary([sample for sample in model_samples if sample["group"] == group], "governed"),
                        "ungoverned": _arm_summary([sample for sample in model_samples if sample["group"] == group], "ungoverned"),
                    }
                    for group in sorted({sample["group"] for sample in model_samples})
                },
                "samples": model_samples,
            }
            for model, model_samples in grouped.items()
        },
    }


def write_offline_score(report: dict[str, Any], path: str | Path) -> Path:
    """Persist an offline score report without creating a publishable result card."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, default=_json_default, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value).__name__}")
