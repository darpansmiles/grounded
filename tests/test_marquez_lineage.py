from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import httpx

from harness import graph_lineage, lineage_source

# Parser-relevant projection of the real `GET /api/v1/lineage` response
# recorded from Marquez for `dataset:bronze:salesorderdetail`.
_FIXTURE = Path(__file__).parent / "fixtures" / "marquez_lineage_bronze_salesorderdetail.json"
_FIXTURE_POC = Path(__file__).parent / "fixtures" / "marquez_lineage_fixture_revenue.json"
_AW_DEFINITION = {
    "metric": "aw_revenue_test_only",
    "lineage": {
        "tables": [
            "gold.fct_sales",
            "silver.stg_sales_order_line",
            "bronze.salesorderdetail",
        ],
    },
}


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return json.loads(_FIXTURE.read_text(encoding="utf-8"))


class _Client:
    requests: ClassVar[list[tuple[str, dict[str, str | int]]]] = []

    def __init__(self, *, timeout: float) -> None:
        assert timeout == 5.0

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def get(self, url: str, *, params: dict[str, str | int]) -> _Response:
        self.requests.append((url, params))
        return _Response()


def _dataset_ids(nodes: list[dict]) -> set[str]:
    return {f"{node['namespace']}.{node['name']}" for node in nodes}


def test_marquez_source_parses_recorded_rest_graph_and_proves_aw_parity(monkeypatch):
    _Client.requests = []
    monkeypatch.setattr(lineage_source.httpx, "Client", _Client)
    source = lineage_source.MarquezLineageSource("http://marquez.example:5050")

    upstream = source.upstream("adventureworks.gold.fct_sales")
    downstream = source.downstream("adventureworks.bronze.salesorderdetail")
    verified = source.verify(_AW_DEFINITION)

    assert _dataset_ids(upstream["nodes"]) == {
        "adventureworks.postgres.adventureworks.sales.salesorderdetail",
        "adventureworks.bronze.salesorderdetail",
        "adventureworks.silver.stg_sales_order_line",
        "adventureworks.gold.fct_sales",
    }
    assert _dataset_ids(downstream["nodes"]) == {
        "adventureworks.bronze.salesorderdetail",
        "adventureworks.silver.stg_sales_order_line",
        "adventureworks.gold.fct_sales",
    }
    assert verified["verified"] is True
    assert _Client.requests == [
        ("http://marquez.example:5050/api/v1/lineage", {"nodeId": "dataset:adventureworks.gold:fct_sales", "depth": 10}),
        ("http://marquez.example:5050/api/v1/lineage", {"nodeId": "dataset:adventureworks.bronze:salesorderdetail", "depth": 10}),
        ("http://marquez.example:5050/api/v1/lineage", {"nodeId": "dataset:adventureworks.gold:fct_sales", "depth": 10}),
    ]


def test_marquez_source_gracefully_degrades_when_unavailable(monkeypatch):
    class _UnavailableClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 5.0

        def __enter__(self):
            raise httpx.ConnectError("connection refused")

        def __exit__(self, *_args) -> None:
            return None

    monkeypatch.setattr(lineage_source.httpx, "Client", _UnavailableClient)
    result = lineage_source.MarquezLineageSource().verify(_AW_DEFINITION)

    assert result == {"available": False, "verified": False, "nodes": [], "edges": []}


def test_recorded_fixture_response_keeps_the_deterministic_poc_verified(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "fixture")
    class _FixtureResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return json.loads(_FIXTURE_POC.read_text(encoding="utf-8"))

    class _FixtureClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 5.0

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def get(self, _url: str, *, params: dict[str, str | int]) -> _FixtureResponse:
            assert params == {"nodeId": "dataset:fixture.gold:mart_revenue", "depth": 10}
            return _FixtureResponse()

    monkeypatch.setattr(lineage_source.httpx, "Client", _FixtureClient)
    monkeypatch.setattr(graph_lineage, "LINEAGE_SOURCE", "marquez")

    result = graph_lineage.graph_lineage_for_metric(
        {
            "lineage": {
                "tables": [
                    "gold.mart_revenue",
                    "silver.stg_order_items",
                    "raw.orders",
                    "raw.order_items",
                ],
                "sources": ["postgres.shop"],
            }
        }
    )

    assert result["verified"] is True
    assert "fixture.postgres.shop" in _dataset_ids(result["nodes"])
