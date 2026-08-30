from __future__ import annotations

from decimal import Decimal

import pytest

from resolver.metric_resolver import UndeclaredFieldError, UnknownMetricError, resolve_and_run
from scripts.seed_duckdb import seed_database


@pytest.fixture()
def seeded_database(tmp_path):
    db_path = tmp_path / "grounded.duckdb"
    seed_database(str(db_path))
    return db_path


def _last_month_revenue_by_category(db_path):
    return resolve_and_run(
        "revenue",
        dimensions=["category"],
        filters={"order_month": "last_month"},
        reference_date="2026-08-12",
        db_path=str(db_path),
    )


def test_revenue_by_category_last_month(seeded_database):
    result = _last_month_revenue_by_category(seeded_database)

    assert result["rows"] == [
        {"category": "Electronics", "revenue": Decimal("500.00")},
        {"category": "Home", "revenue": Decimal("405.00")},
        {"category": "Books", "revenue": Decimal("280.00")},
    ]
    assert result["row_count"] == 10
    assert sum(row["revenue"] for row in result["rows"]) == Decimal("1185.00")
    assert result["columns"] == ["category", "revenue"]
    assert result["resolved_definition"]["metric"] == "revenue"


def test_excludes_cancelled_and_out_of_window(seeded_database):
    result = _last_month_revenue_by_category(seeded_database)

    assert sum(row["revenue"] for row in result["rows"]) == Decimal("1185.00")
    assert result["row_count"] == 10


def test_unknown_metric_raises(seeded_database):
    with pytest.raises(UnknownMetricError, match="Unknown governed metric: gmv"):
        resolve_and_run("gmv", db_path=str(seeded_database))


def test_rejects_undeclared_dimension(seeded_database):
    with pytest.raises(UndeclaredFieldError, match="Undeclared dimension: email"):
        resolve_and_run("revenue", dimensions=["email"], db_path=str(seeded_database))


def test_no_raw_sql_passthrough(seeded_database):
    with pytest.raises(UndeclaredFieldError, match="Undeclared filter: sql"):
        resolve_and_run(
            "revenue",
            dimensions=["category"],
            filters={"sql": "DROP TABLE orders"},
            db_path=str(seeded_database),
        )
