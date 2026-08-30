from __future__ import annotations

from decimal import Decimal

import pytest

from harness.tools import check_policy, describe_metric, list_metrics, query_metric
from resolver.metric_resolver import UnknownMetricError
from scripts.seed_duckdb import seed_database


_CITATION = (
    "revenue ← Cube:Sales.revenue ← SQLMesh:gold.fct_sales "
    "← Tables:[gold.fct_sales, silver.stg_sales_order_line, bronze.salesorderdetail] "
    "← Source:[postgres.adventureworks]"
)


@pytest.fixture()
def seeded_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")


def test_list_metrics_excludes_governed_entity_reads():
    assert list_metrics() == [
        {
            "metric": "aov",
            "label": "Average Order Value",
            "description": "Revenue per completed order (Revenue / Orders).",
            "owner": "darpan",
        },
        {
            "metric": "orders",
            "label": "Orders",
            "description": "Count of distinct completed orders.",
            "owner": "darpan",
        },
        {
            "metric": "revenue",
            "label": "Revenue",
            "description": "Gross merchandise revenue from completed order items.",
            "owner": "darpan",
        }
    ]


def test_describe_metric_returns_contract_and_exact_citation():
    result = describe_metric("revenue")

    assert result["definition"]["measure"] == "sum(order_items.quantity * order_items.unit_price)"
    assert result["dimensions"][0]["name"] == "category"
    assert result["policies"][0]["id"] == "pii-mask-email"
    assert result["verification"][0]["type"] == "non_negative"
    assert result["lineage_citation"] == _CITATION


def test_query_metric_is_governed_verified_and_cited(seeded_database):
    result = query_metric("revenue", ["category"], {"order_month": "last_month"}, "viewer")

    assert result["rows"] == [
        {"category": "Electronics", "revenue": 500.0},
        {"category": "Home", "revenue": 405.0},
        {"category": "Books", "revenue": 280.0},
    ]
    assert result["verify_status"] == "pass"
    assert result["policy_decisions"] == []
    assert result["lineage_citation"] == _CITATION
    assert result["metric_definition"] == {
        "measure": "sum(order_items.quantity * order_items.unit_price)",
        "grain": "order_item",
        "filter": "orders.status = 'completed'",
    }


def test_check_policy_uses_governed_definition():
    assert check_policy("customers.email", "viewer")["decision"] == "mask"
    assert check_policy("customers.email", "admin")["decision"] == "allow"


def test_describe_unknown_metric_raises():
    with pytest.raises(UnknownMetricError, match="Unknown governed metric: gmv"):
        describe_metric("gmv")
