from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from audit.log import read_audit
from governed.service import governed_query
from resolver.backends import cube, fixture
from resolver.metric_resolver import resolve_and_run
from scripts.seed_duckdb import seed_database

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _RecordedResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _recorded_post(payload: dict, calls: list[dict]):
    def post(url: str, *, json: dict, timeout: float) -> _RecordedResponse:
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _RecordedResponse(payload)

    return post


def _payload(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_cube_backend_parses_recorded_gold_revenue_by_category(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(cube.httpx, "post", _recorded_post(_payload("cube_revenue_by_category.json"), calls))

    result = resolve_and_run(
        "revenue", dimensions=["category"], backend="cube", cube_url="http://cube.test/cubejs-api/v1"
    )

    assert result["rows"] == [
        {"category": "Bikes", "revenue": Decimal("94651172.72")},
        {"category": "Components", "revenue": Decimal("11802593.29")},
        {"category": "Clothing", "revenue": Decimal("2120542.53")},
        {"category": "Accessories", "revenue": Decimal("1272072.89")},
    ]
    assert sum(row["revenue"] for row in result["rows"]) == Decimal("109846381.43")
    assert result["row_count"] == 4
    assert calls == [
        {
            "url": "http://cube.test/cubejs-api/v1/load",
            "timeout": 30.0,
            "json": {
                "query": {
                    "measures": ["Sales.revenue"],
                    "dimensions": ["Sales.category"],
                    "order": {"Sales.revenue": "desc", "Sales.category": "asc"},
                }
            },
        }
    ]


def test_cube_http_error_has_a_pack_specific_remedy(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "adventureworks")
    request = httpx.Request("POST", "http://cube.test/cubejs-api/v1/load")
    response = httpx.Response(400, request=request)

    class FailingResponse:
        def raise_for_status(self):
            raise httpx.HTTPStatusError("400 invalid query", request=request, response=response)

    monkeypatch.setattr(cube.httpx, "post", lambda *_args, **_kwargs: FailingResponse())

    with pytest.raises(cube.CubeResponseError, match="make cube-up DATASET=adventureworks") as error:
        cube.resolve_and_run("revenue", ["category"], cube_url="http://cube.test/cubejs-api/v1")

    assert "400 invalid query" not in str(error.value)


def test_cube_backend_validates_tpch_dimensions_from_the_active_pack(monkeypatch, tmp_path):
    model_directory = tmp_path / "model"
    model_directory.mkdir()
    (model_directory / "line_items.yml").write_text(
        """cubes:
  - name: LineItems
    measures:
      - name: revenue
    dimensions:
      - name: nation
      - name: region
      - name: market_segment
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cube,
        "active_pack",
        lambda: SimpleNamespace(semantics=SimpleNamespace(cube=tmp_path)),
    )
    monkeypatch.setattr(
        cube,
        "_load_definition",
        lambda _: {
            "metric": "revenue",
            "definition": {"measure": "sum(line_items.revenue)"},
            "dimensions": [
                {"name": "nation"},
                {"name": "region"},
                {"name": "market_segment"},
            ],
        },
    )
    calls: list[dict] = []
    monkeypatch.setattr(
        cube.httpx,
        "post",
        _recorded_post(
            {
                "data": [
                    {
                        "LineItems.revenue": "123.45",
                        "LineItems.nation": "GERMANY",
                        "LineItems.region": "EUROPE",
                        "LineItems.market_segment": "BUILDING",
                    }
                ]
            },
            calls,
        ),
    )

    result = resolve_and_run(
        "revenue",
        dimensions=["nation", "region", "market_segment"],
        backend="cube",
        cube_url="http://cube.test/cubejs-api/v1",
    )

    assert result["rows"] == [
        {
            "nation": "GERMANY",
            "region": "EUROPE",
            "market_segment": "BUILDING",
            "revenue": Decimal("123.45"),
        }
    ]
    assert calls[0]["json"]["query"]["dimensions"] == [
        "LineItems.nation",
        "LineItems.region",
        "LineItems.market_segment",
    ]


def test_cube_backend_normalizes_additive_empty_bucket_to_zero(monkeypatch):
    monkeypatch.setattr(
        cube,
        "_member_maps",
        lambda *_: ("LineItems.revenue", {"order_month": "LineItems.order_month"}),
    )

    rows = cube._parse_rows(
        {"data": [{"LineItems.revenue": None, "LineItems.order_month.month": "1996-01-01"}]},
        "revenue",
        ["order_month"],
        {"definition": {"measure": "sum(line_items.revenue)"}},
    )

    assert rows == [{"order_month": "1996-01-01", "revenue": Decimal("0.00")}]


def test_cube_backend_keeps_ratio_empty_bucket_null(monkeypatch):
    monkeypatch.setattr(
        cube,
        "_member_maps",
        lambda *_: ("LineItems.aov", {"order_month": "LineItems.order_month"}),
    )

    rows = cube._parse_rows(
        {"data": [{"LineItems.aov": None, "LineItems.order_month.month": "1996-01-01"}]},
        "aov",
        ["order_month"],
        {"definition": {"derived": "ratio", "numerator": "revenue", "denominator": "orders"}},
    )

    assert rows == [{"order_month": "1996-01-01", "aov": None}]


def test_cube_backend_translates_eu_row_policy_before_execution(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls: list[dict] = []
    monkeypatch.setattr(
        cube.httpx, "post", _recorded_post(_payload("cube_revenue_eu_by_category.json"), calls)
    )

    result = governed_query(
        "revenue",
        dimensions=["category"],
        role="eu_analyst",
        backend="cube",
        cube_url="http://cube.test/cubejs-api/v1",
    )

    assert result["rows"] == [
        {"category": "Bikes", "revenue": Decimal("10496417.87")},
        {"category": "Components", "revenue": Decimal("1208534.86")},
        {"category": "Clothing", "revenue": Decimal("253241.36")},
        {"category": "Accessories", "revenue": Decimal("208769.16")},
    ]
    assert result["verify_status"] == "pass"
    assert result["policy_decisions"][0]["id"] == "row-eu-only"
    assert calls[0]["json"]["query"]["filters"] == [
        {"member": "Sales.country", "operator": "equals", "values": ["DE", "FR", "NL"]}
    ]
    assert read_audit("audit.log.jsonl")[0]["policy_decisions"] == result["policy_decisions"]


def test_default_fixture_backend_is_identical_to_direct_fixture(tmp_path):
    db_path = tmp_path / "grounded.duckdb"
    seed_database(str(db_path))
    arguments = {
        "metric": "revenue",
        "dimensions": ["category"],
        "filters": {"order_month": "last_month"},
        "db_path": str(db_path),
    }

    assert resolve_and_run(**arguments) == fixture.resolve_and_run(**arguments)
