from __future__ import annotations

from datetime import datetime

import pytest

from audit.log import read_audit
from governed.service import governed_customers, governed_query
from scripts.seed_duckdb import seed_database


_AUDIT_KEYS = {
    "timestamp",
    "role",
    "tool",
    "target",
    "dimensions",
    "filters",
    "policy_decisions",
    "verify_status",
    "row_count",
}


@pytest.fixture()
def seeded_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "grounded.duckdb"
    seed_database(str(db_path))
    return db_path


def test_each_governed_call_appends_a_complete_audit_record(seeded_database):
    governed_query(
        "revenue",
        ["category"],
        {"order_month": "last_month"},
        role="viewer",
        db_path=str(seeded_database),
    )
    records = read_audit("audit.log.jsonl")

    assert len(records) == 1
    assert set(records[0]) == _AUDIT_KEYS
    assert records[0]["tool"] == "query_metric"
    assert records[0]["verify_status"] == "pass"
    datetime.fromisoformat(records[0]["timestamp"])


def test_audit_is_append_only(seeded_database):
    governed_customers("viewer", str(seeded_database))
    first_line = open("audit.log.jsonl", encoding="utf-8").readline()

    governed_customers("analyst_pii", str(seeded_database))
    records = read_audit("audit.log.jsonl")

    assert len(records) == 2
    assert open("audit.log.jsonl", encoding="utf-8").readline() == first_line
    assert records[0]["tool"] == records[1]["tool"] == "customer_directory"
