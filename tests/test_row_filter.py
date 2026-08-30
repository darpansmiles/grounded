from __future__ import annotations

from decimal import Decimal

import pytest
import yaml

from audit.log import read_audit
from governed.service import governed_query
from packlib import active_pack
from policy.engine import row_predicates_for_role
from resolver.metric_resolver import UndeclaredFieldError
from scripts.seed_duckdb import seed_database


@pytest.fixture()
def seeded_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "grounded.duckdb"
    seed_database(str(db_path))
    return db_path


def _revenue_definition() -> dict:
    definition_path = next(
        path for path in active_pack().semantics.metrics if path.stem == "revenue"
    )
    with definition_path.open(encoding="utf-8") as definition_file:
        return yaml.safe_load(definition_file)


def test_eu_analyst_revenue_is_filtered_before_aggregation_and_audited(seeded_database):
    result = governed_query(
        "revenue",
        ["category"],
        {"order_month": "last_month"},
        role="eu_analyst",
        db_path=str(seeded_database),
    )

    assert result["rows"] == [
        {"category": "Electronics", "revenue": Decimal("300.00")},
        {"category": "Books", "revenue": Decimal("180.00")},
        {"category": "Home", "revenue": Decimal("150.00")},
    ]
    assert result["row_count"] == 6
    assert sum(row["revenue"] for row in result["rows"]) == Decimal("630.00")
    assert result["policy_decisions"] == [
        {
            "id": "row-eu-only",
            "target": "customers.country",
            "rule": "row_filter",
            "decision": "row_filter",
            "predicate": "country IN ('DE','FR','NL')",
            "cube_member": "Sales.country",
            "operator": "in",
            "values": ["DE", "FR", "NL"],
            "reason": "row-eu-only: rows filtered to country IN ('DE','FR','NL') for role eu_analyst",
        }
    ]
    assert result["verify_status"] == "pass"
    assert "AND (country IN ('DE','FR','NL'))" in result["sql"]
    assert result["sql"].index("AND (country IN ('DE','FR','NL'))") < result["sql"].index("GROUP BY")
    assert read_audit("audit.log.jsonl")[0]["policy_decisions"] == result["policy_decisions"]


@pytest.mark.parametrize("role", ["viewer", "analyst_pii"])
def test_non_eu_roles_preserve_existing_revenue(role, seeded_database):
    result = governed_query(
        "revenue",
        ["category"],
        {"order_month": "last_month"},
        role=role,
        db_path=str(seeded_database),
    )

    assert result["rows"] == [
        {"category": "Electronics", "revenue": Decimal("500.00")},
        {"category": "Home", "revenue": Decimal("405.00")},
        {"category": "Books", "revenue": Decimal("280.00")},
    ]
    assert result["row_count"] == 10
    assert result["policy_decisions"] == []


def test_row_predicates_are_declarative_and_role_limited():
    definition = _revenue_definition()

    assert row_predicates_for_role(definition, "eu_analyst") == [
        {
            "id": "row-eu-only",
            "target": "customers.country",
            "rule": "row_filter",
            "decision": "row_filter",
            "predicate": "country IN ('DE','FR','NL')",
            "cube_member": "Sales.country",
            "operator": "in",
            "values": ["DE", "FR", "NL"],
            "reason": "row-eu-only: rows filtered to country IN ('DE','FR','NL') for role eu_analyst",
        }
    ]
    assert row_predicates_for_role(definition, "viewer") == []


def test_caller_cannot_inject_row_predicate(seeded_database):
    with pytest.raises(UndeclaredFieldError, match="Undeclared filter: country"):
        governed_query(
            "revenue",
            ["category"],
            {"country": "country IN ('DE','FR','NL')"},
            role="viewer",
            db_path=str(seeded_database),
        )
