from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from infra import ingest
from ontology import real_lineage


class _LoadInfo:
    def __init__(self, tables: list[str], destination: str) -> None:
        self._tables = tables
        self._destination = destination

    def asdict(self) -> dict:
        return {
            "loads_ids": ["load-42"],
            "dataset_name": self._destination,
            "pipeline": {"pipeline_name": "test_pipeline"},
            "load_packages": [
                {
                    "jobs": [
                        {"table_name": table, "state": "completed_jobs"}
                        for table in self._tables
                    ]
                }
            ],
            "outputs": [{"tables": self._tables}],
        }


def _schema(tables: dict[str, dict[str, str]]) -> SimpleNamespace:
    return SimpleNamespace(
        tables={
            name: {
                "columns": {
                    column: {"name": column, "data_type": data_type}
                    for column, data_type in columns.items()
                }
            }
            for name, columns in tables.items()
        }
    )


@pytest.mark.parametrize(
    ("tables", "source_tables"),
    [
        (
            {
                "salesorderheader": {"order_id": "bigint"},
                "salesorderdetail": {"line_total": "decimal"},
            },
            {
                "salesorderheader": "adventureworks.sales.salesorderheader",
                "salesorderdetail": "adventureworks.sales.salesorderdetail",
            },
        ),
        (
            {
                "orders": {"order_id": "bigint"},
                "order_items": {"amount": "decimal"},
            },
            {
                "orders": "fixture.public.orders",
                "order_items": "fixture.public.order_items",
            },
        ),
    ],
)
def test_dlt_lineage_events_follow_the_loaded_schema(
    tables: dict[str, dict[str, str]], source_tables: dict[str, str]
):
    events = ingest.lineage_events(
        _LoadInfo(list(tables), "bronze"),
        _schema(tables),
        {table: index + 1 for index, table in enumerate(tables)},
        source_tables,
        "postgres",
        started_at="2026-08-16T00:00:00Z",
        completed_at="2026-08-16T00:01:00Z",
    )

    assert [event["eventType"] for event in events] == ["START", "COMPLETE"]
    assert events[-1]["run"]["runId"] == "load-42"
    assert {dataset["name"] for dataset in events[-1]["outputs"]} == set(tables)
    assert {dataset["name"] for dataset in events[-1]["inputs"]} == set(
        source_tables.values()
    )
    assert all(
        dataset["facets"]["dataQualityMetrics"]["rowCount"] > 0
        for dataset in events[-1]["outputs"]
    )
    assert all(
        dataset["facets"]["schema"]["fields"]
        for dataset in events[-1]["outputs"]
    )


def test_sqlmesh_lineage_events_follow_any_context_models(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "fixture")
    output_model = SimpleNamespace(
        name='"fixture"."gold"."revenue"',
        columns_to_types={"revenue": "decimal"},
        depends_on={'"fixture"."silver"."order_items"'},
    )
    input_model = SimpleNamespace(
        name='"fixture"."silver"."order_items"',
        columns_to_types={"amount": "decimal"},
        depends_on=set(),
    )
    context = SimpleNamespace(
        models={output_model.name: output_model, input_model.name: input_model}
    )
    monkeypatch.setattr(
        real_lineage,
        "column_dependencies",
        lambda _context, model, _column: (
            {'"fixture"."silver"."order_items"': {"amount"}}
            if model == output_model.name
            else {}
        ),
    )

    events = real_lineage.sqlmesh_events_from_context(context)

    assert len(events) == 1
    assert events[0]["outputs"][0]["name"] == "revenue"
    assert events[0]["inputs"] == [
        {"namespace": "fixture.silver", "name": "order_items"}
    ]
    assert events[0]["outputs"][0]["facets"]["columnLineage"]["fields"] == {
        "revenue": {
            "inputFields": [
                {
                    "namespace": "fixture.silver",
                    "name": "order_items",
                    "field": "amount",
                }
            ],
            "transformationDescription": "SQLMesh column dependency",
            "transformationType": "IDENTITY",
        }
    }


def test_lineage_construction_depends_on_runtime_metadata_not_inline_tables():
    dlt_source = inspect.getsource(ingest.ingest) + inspect.getsource(ingest.lineage_events)
    sqlmesh_source = inspect.getsource(real_lineage.sqlmesh_events_from_context)

    assert all(
        token in dlt_source
        for token in ("load_info", "default_schema", "row_counts", "source_tables")
    )
    assert all(token in sqlmesh_source for token in ("context.models", "column_fields", "_model_lineage"))
    assert "salesorderdetail" not in dlt_source
    assert "salesorderdetail" not in sqlmesh_source


def test_same_named_models_in_two_packs_have_distinct_dataset_ids(monkeypatch):
    schema = _schema({"dim_customer": {"customer_key": "bigint"}})
    source_tables = {"dim_customer": "source.public.dim_customer"}

    monkeypatch.setenv("GROUNDED_PACK", "adventureworks")
    adventureworks = ingest.lineage_events(
        _LoadInfo(["dim_customer"], "gold"),
        schema,
        {"dim_customer": 1},
        source_tables,
        "postgres",
        started_at="2026-08-16T00:00:00Z",
        completed_at="2026-08-16T00:01:00Z",
    )[-1]
    monkeypatch.setenv("GROUNDED_PACK", "fixture")
    fixture = ingest.lineage_events(
        _LoadInfo(["dim_customer"], "gold"),
        schema,
        {"dim_customer": 1},
        source_tables,
        "postgres",
        started_at="2026-08-16T00:00:00Z",
        completed_at="2026-08-16T00:01:00Z",
    )[-1]

    assert adventureworks["outputs"][0]["namespace"] == "adventureworks.gold"
    assert fixture["outputs"][0]["namespace"] == "fixture.gold"
    assert adventureworks["outputs"][0] != fixture["outputs"][0]
