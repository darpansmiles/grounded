from __future__ import annotations

import subprocess

import duckdb

from agent.ungoverned import gold_schema_prompt
from governed.service import _cube_filters_for_row_decisions
from packlib import PROJECT_ROOT, load_pack
from scripts.lakehouse import AttachedPack, attach_read_only, catalog_rows


def test_full_packs_own_distinct_duckdb_files():
    adventureworks = load_pack("adventureworks")
    fixture = load_pack("fixture")

    assert (
        adventureworks.destination.path
        == PROJECT_ROOT / "data" / "adventureworks.duckdb"
    )
    assert fixture.destination.path == PROJECT_ROOT / "data" / "fixture.duckdb"
    assert adventureworks.destination.path != fixture.destination.path


def test_lakehouse_attaches_namespaced_pack_databases_read_only(tmp_path):
    adventureworks_path = tmp_path / "adventureworks.duckdb"
    fixture_path = tmp_path / "fixture.duckdb"
    for path, value in ((adventureworks_path, "aw"), (fixture_path, "fixture")):
        connection = duckdb.connect(str(path))
        try:
            connection.execute("CREATE SCHEMA gold")
            connection.execute("CREATE TABLE gold.dim_customer (pack VARCHAR)")
            connection.execute("INSERT INTO gold.dim_customer VALUES (?)", [value])
        finally:
            connection.close()

    connection = duckdb.connect(":memory:")
    try:
        attach_read_only(
            connection,
            [
                AttachedPack("adventureworks", adventureworks_path),
                AttachedPack("fixture", fixture_path),
            ],
        )
        assert catalog_rows(connection) == [
            ("adventureworks", "gold", "dim_customer"),
            ("fixture", "gold", "dim_customer"),
        ]
        assert (
            connection.execute(
                "SELECT pack FROM adventureworks.gold.dim_customer"
            ).fetchone()[0]
            == "aw"
        )
        assert (
            connection.execute("SELECT pack FROM fixture.gold.dim_customer").fetchone()[
                0
            ]
            == "fixture"
        )
    finally:
        connection.close()


def test_transform_command_audits_the_active_pack_without_aw_model_list():
    planned = subprocess.run(
        ["make", "-n", "DATASET=adventureworks", "transform"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout

    assert "sqlmesh audit" in planned
    assert "--model" not in planned
    assert "gold.fct_sales --model" not in planned


def test_cube_row_filter_uses_declared_member_and_values(monkeypatch):
    monkeypatch.setattr(
        "governed.service.cube.has_dimension_member",
        lambda member: member == "LineItems.region",
    )

    assert _cube_filters_for_row_decisions(
        [
            {
                "cube_member": "LineItems.region",
                "operator": "equals",
                "values": ["EUROPE"],
            }
        ]
    ) == [{"member": "LineItems.region", "operator": "equals", "values": ["EUROPE"]}]


def test_control_arm_prompt_is_read_from_the_actual_gold_schema(tmp_path):
    database = tmp_path / "second-pack.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute("CREATE SCHEMA gold")
        connection.execute(
            "CREATE TABLE gold.fct_lineitem (order_key BIGINT, revenue DOUBLE)"
        )
        connection.execute("CREATE TABLE gold.dim_region (region VARCHAR)")
    finally:
        connection.close()

    prompt = gold_schema_prompt(str(database), "second-pack")

    assert "second-pack gold schema" in prompt
    assert "gold.fct_lineitem(order_key, revenue)" in prompt
    assert "gold.dim_region(region)" in prompt
    assert "AdventureWorks" not in prompt
