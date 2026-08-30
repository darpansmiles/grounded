from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import graph_lineage, lineage_source
from harness.tools import describe_metric, impact_of, query_metric
from scripts.seed_duckdb import seed_database

_CITATION = (
    "revenue ← Cube:Revenue.revenue ← SQLMesh:mart_revenue "
    "← Tables:[gold.mart_revenue, silver.stg_order_items, raw.orders, raw.order_items] "
    "← Source:[postgres.shop]"
)
_FIXTURE = Path(__file__).parent / "fixtures" / "marquez_lineage_fixture_revenue.json"


def _dataset_ids(nodes: list[dict]) -> set[str]:
    return {f"{node['namespace']}.{node['name']}" for node in nodes}


@pytest.fixture()
def recorded_fixture_lineage(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "fixture")
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return json.loads(_FIXTURE.read_text(encoding="utf-8"))

    class Client:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 5.0

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def get(self, _url: str, *, params: dict[str, str | int]) -> Response:
            assert params["nodeId"].startswith("dataset:")
            return Response()

    monkeypatch.setattr(lineage_source.httpx, "Client", Client)
    monkeypatch.setattr(graph_lineage, "LINEAGE_SOURCE", "marquez")


def test_graph_lineage_matches_declared_contract_b(recorded_fixture_lineage):
    definition = describe_metric("revenue")

    assert definition["lineage_graph_verified"] is True
    assert {
        "fixture.gold.mart_revenue",
        "fixture.silver.stg_order_items",
        "fixture.raw.orders",
        "fixture.raw.order_items",
        "fixture.postgres.shop",
    } <= _dataset_ids(definition["lineage_graph"]["nodes"])
    assert definition["lineage_graph"]["edges"]
    assert definition["lineage_citation"] == _CITATION


def test_query_metric_attaches_graph_verification(recorded_fixture_lineage, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")

    result = query_metric("revenue", ["category"], {"order_month": "last_month"}, "viewer")

    assert result["lineage_graph_verified"] is True
    assert result["lineage_citation"] == _CITATION
    assert result["rows"][0] == {"category": "Electronics", "revenue": 500.0}


def test_impact_of_reports_dataset_and_metric_impact(recorded_fixture_lineage):
    order_items_impact = impact_of("fixture.raw.order_items")
    mart_impact = impact_of("fixture.gold.mart_revenue")

    assert order_items_impact["available"] is True
    assert {"fixture.silver.stg_order_items", "fixture.gold.mart_revenue"} <= set(
        order_items_impact["downstream_datasets"]
    )
    assert order_items_impact["downstream_metrics"] == ["orders", "revenue"]
    assert mart_impact["downstream_datasets"] == []
    assert mart_impact["downstream_metrics"] == ["orders", "revenue"]


def test_graph_absence_degrades_without_changing_citation(monkeypatch):
    monkeypatch.setattr(graph_lineage, "LINEAGE_SOURCE", "none")

    metric = describe_metric("revenue")
    graph_impact = impact_of("raw.order_items")

    assert metric["lineage_graph_verified"] is False
    assert metric["lineage_graph"] == {"nodes": [], "edges": []}
    assert metric["lineage_citation"] == (
        "revenue ← Cube:Sales.revenue ← SQLMesh:gold.fct_sales "
        "← Tables:[gold.fct_sales, silver.stg_sales_order_line, bronze.salesorderdetail] "
        "← Source:[postgres.adventureworks]"
    )
    assert graph_impact == {
        "available": False,
        "downstream_datasets": [],
        "downstream_metrics": [],
    }
