from __future__ import annotations

from decimal import Decimal

import pytest

from governed import service
from governed.service import governed_query
from harness.tools import describe_metric, list_metrics
from resolver.metric_resolver import UnknownMetricError, _compile_measure, resolve_and_run
from scripts.seed_duckdb import seed_database
from semantics.loader import load_expanded_definition


@pytest.fixture()
def seeded_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    database = tmp_path / "grounded.duckdb"
    seed_database(str(database))
    return database


def test_orders_compiles_count_distinct_by_category_and_total(seeded_database):
    by_category = resolve_and_run(
        "orders", ["category"], {"order_month": "last_month"}, db_path=str(seeded_database)
    )
    total = resolve_and_run("orders", filters={"order_month": "last_month"}, db_path=str(seeded_database))

    assert by_category["rows"] == [
        {"category": "Books", "orders": Decimal("4.00")},
        {"category": "Electronics", "orders": Decimal("3.00")},
        {"category": "Home", "orders": Decimal("3.00")},
    ]
    assert total["rows"] == [{"orders": Decimal("5.00")}]


def test_aov_composes_governed_parent_metrics_by_category_and_total(seeded_database):
    by_category = governed_query(
        "aov", ["category"], {"order_month": "last_month"}, db_path=str(seeded_database)
    )
    total = governed_query("aov", filters={"order_month": "last_month"}, db_path=str(seeded_database))

    assert by_category["rows"] == [
        {"category": "Electronics", "aov": Decimal("166.67")},
        {"category": "Home", "aov": Decimal("135.00")},
        {"category": "Books", "aov": Decimal("70.00")},
    ]
    assert total["rows"] == [{"aov": Decimal("237.00")}]


def test_revenue_compiler_output_is_unchanged(seeded_database):
    result = resolve_and_run(
        "revenue", ["category"], {"order_month": "last_month"}, db_path=str(seeded_database)
    )

    assert result["rows"] == [
        {"category": "Electronics", "revenue": Decimal("500.00")},
        {"category": "Home", "revenue": Decimal("405.00")},
        {"category": "Books", "revenue": Decimal("280.00")},
    ]
    assert sum(row["revenue"] for row in result["rows"]) == Decimal("1185.00")
    assert result["row_count"] == 10


def test_aov_description_exposes_parent_lineage_and_policies():
    definition = describe_metric("aov")

    assert definition["dimensions"][0]["name"] == "category"
    assert set(definition["lineage_citation"].split("Tables:[", 1)[1].split("]", 1)[0].split(", ")) == {
        "gold.fct_sales",
        "silver.stg_sales_order_line",
        "bronze.salesorderdetail",
    }
    assert {policy["id"] for policy in definition["policies"]} == {"pii-mask-email", "row-eu-only"}


def test_aov_applies_the_inherited_eu_row_filter_to_both_parents(seeded_database):
    result = governed_query(
        "aov",
        ["category"],
        {"order_month": "last_month"},
        role="eu_analyst",
        db_path=str(seeded_database),
    )

    assert result["rows"] == [
        {"category": "Electronics", "aov": Decimal("150.00")},
        {"category": "Home", "aov": Decimal("150.00")},
        {"category": "Books", "aov": Decimal("60.00")},
    ]
    assert governed_query(
        "aov", filters={"order_month": "last_month"}, role="eu_analyst", db_path=str(seeded_database)
    )["rows"] == [{"aov": Decimal("210.00")}]


def test_zero_denominator_returns_null_with_a_verification_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def parent_result(metric, *_args, **_kwargs):
        return {
            "rows": [{"category": "Empty", metric: Decimal("10.00" if metric == "revenue" else "0.00")}],
            "row_count": 1,
            "policy_decisions": [],
        }

    monkeypatch.setattr(service, "governed_query", parent_result)
    result = service._governed_ratio(
        load_expanded_definition("aov"),
        ["category"],
        {"order_month": "last_month"},
        "viewer",
        "2026-08-12",
        str(tmp_path / "grounded.duckdb"),
    )

    assert result["rows"] == [{"category": "Empty", "aov": None}]
    assert result["verification"][-1] == {
        "type": "division_by_zero",
        "field": "aov",
        "status": "pass",
        "detail": "Denominator was zero; returned null instead of dividing by zero.",
    }


def test_list_metrics_includes_the_metric_tree():
    assert {definition["metric"] for definition in list_metrics()} == {"revenue", "orders", "aov"}


def test_undeclared_measure_forms_are_rejected():
    with pytest.raises(UnknownMetricError, match="Unsupported governed measure"):
        _compile_measure({"metric": "bad", "definition": {"measure": "avg(order_items.unit_price)"}})
