from __future__ import annotations

import subprocess

from datasets.fixture.source.seed import seed_database
from governed.service import governed_query
from packlib import PROJECT_ROOT, active_pack, load_pack


def test_adventureworks_pack_resolves_all_declared_capabilities(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "adventureworks")

    pack = active_pack()

    assert pack == load_pack("adventureworks")
    assert pack.namespace == "adventureworks"
    assert pack.source.type == "postgres"
    assert pack.source.dsn_env == "GROUNDED_ADVENTUREWORKS_SOURCE_DSN"
    assert pack.source.tables == (
        "sales.salesorderheader",
        "sales.salesorderdetail",
        "sales.customer",
        "sales.salesterritory",
        "production.product",
        "production.productsubcategory",
        "production.productcategory",
        "person.person",
        "person.emailaddress",
    )
    assert pack.destination.path == PROJECT_ROOT / "data" / "adventureworks.duckdb"
    assert pack.destination.dataset == "bronze"
    assert pack.transform_dir == pack.root / "transform"
    assert pack.semantics is not None
    assert pack.semantics.backend == "cube"
    assert pack.semantics.cube == pack.root / "semantics" / "cube"
    assert [path.name for path in pack.semantics.metrics] == [
        "revenue.yml",
        "orders.yml",
        "aov.yml",
    ]
    assert pack.golden == pack.root / "golden.yml"


def test_active_pack_defaults_to_adventureworks(monkeypatch):
    monkeypatch.delenv("GROUNDED_PACK", raising=False)

    assert active_pack().name == "adventureworks"


def test_tpch_pack_uses_its_own_postgres_source_dsn(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "tpch")

    pack = active_pack()

    assert pack.source.type == "postgres"
    assert pack.source.dsn_env == "GROUNDED_TPCH_SOURCE_DSN"


def test_fixture_pack_round_trip_is_deterministic(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GROUNDED_PACK", "fixture")

    pack = active_pack()
    seed_database("grounded.duckdb")
    result = governed_query(
        "revenue",
        ["category"],
        {"order_month": "last_month"},
        db_path="grounded.duckdb",
    )

    assert pack.source.type == "duckdb_seed"
    assert pack.transform_dir is None
    assert pack.semantics is not None
    assert pack.semantics.backend == "fixture"
    assert pack.semantics.cube is None
    assert pack.golden == pack.root / "golden.yml"
    assert result["rows"] == [
        {"category": "Electronics", "revenue": 500.0},
        {"category": "Home", "revenue": 405.0},
        {"category": "Books", "revenue": 280.0},
    ]


def test_fixture_spine_skips_docker_sqlmesh_and_cube():
    planned = subprocess.run(
        ["make", "-n", "DATASET=fixture", "spine"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert "datasets/fixture/source/seed.py" in planned.stdout
    assert "docker" not in planned.stdout
    assert "sqlmesh" not in planned.stdout
    assert "cube" not in planned.stdout
