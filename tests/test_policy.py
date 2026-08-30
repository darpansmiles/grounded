from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from governed.service import governed_customers, governed_query
from policy.engine import apply_masking, check_policy
from scripts.seed_duckdb import seed_database


@pytest.fixture()
def seeded_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "grounded.duckdb"
    seed_database(str(db_path))
    return db_path


def _customers_definition() -> dict:
    definition_path = Path(__file__).resolve().parents[1] / "semantics" / "customers.yml"
    with definition_path.open(encoding="utf-8") as definition_file:
        return yaml.safe_load(definition_file)


def test_governed_customers_masks_email_for_viewer(seeded_database):
    result = governed_customers("viewer", str(seeded_database))

    assert result["rows"] == [
        {"name": "Alice", "country": "DE", "email": "***@example.com"},
        {"name": "Bob", "country": "US", "email": "***@example.com"},
        {"name": "Cara", "country": "FR", "email": "***@example.com"},
        {"name": "Dan", "country": "NL", "email": "***@example.com"},
        {"name": "Eve", "country": "GB", "email": "***@example.com"},
    ]
    assert result["policy_decisions"] == [
        {
            "target": "customers.email",
            "rule": "mask",
            "decision": "mask",
            "reason": "pii-mask-email: customers.email masked unless role in [analyst_pii, admin]",
        }
    ]
    assert result["verify_status"] == "pass"


def test_governed_customers_allows_pii_role(seeded_database):
    result = governed_customers("analyst_pii", str(seeded_database))

    assert [row["email"] for row in result["rows"]] == [
        "alice@example.com",
        "bob@example.com",
        "cara@example.com",
        "dan@example.com",
        "eve@example.com",
    ]
    assert len(result["policy_decisions"]) == 1
    assert result["policy_decisions"][0]["decision"] == "allow"


def test_check_policy_masks_viewer_and_allows_admin():
    definition = _customers_definition()

    assert check_policy("customers.email", "viewer", definition)["decision"] == "mask"
    assert check_policy("customers.email", "admin", definition)["decision"] == "allow"


def test_check_policy_supports_generic_deny():
    definition = {"policies": [{"id": "deny-name", "applies_to": "customers.name", "rule": "deny"}]}

    assert check_policy("customers.name", "viewer", definition)["decision"] == "deny"


def test_pii_column_without_a_role_grant_is_masked_by_default():
    rows, decisions = apply_masking(
        [{"email": "alice@example.com"}],
        {"columns": [{"name": "email", "source": "customers.email", "pii": True}]},
        "viewer",
    )

    assert rows == [{"email": "***@example.com"}]
    assert decisions[0]["decision"] == "mask"


def test_governed_revenue_preserves_numbers_without_pii_policy_decisions(seeded_database):
    result = governed_query(
        "revenue",
        ["category"],
        {"order_month": "last_month"},
        role="viewer",
        db_path=str(seeded_database),
    )

    assert result["rows"] == [
        {"category": "Electronics", "revenue": Decimal("500.00")},
        {"category": "Home", "revenue": Decimal("405.00")},
        {"category": "Books", "revenue": Decimal("280.00")},
    ]
    assert result["policy_decisions"] == []
    assert result["verify_status"] == "pass"
