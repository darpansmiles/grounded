from __future__ import annotations

from pathlib import Path

import pytest

from agent.agent import answer
from scripts.seed_duckdb import seed_database


_CITATION = (
    "revenue ← Cube:Sales.revenue ← SQLMesh:gold.fct_sales "
    "← Tables:[gold.fct_sales, silver.stg_sales_order_line, bronze.salesorderdetail] "
    "← Source:[postgres.adventureworks]"
)


@pytest.fixture()
def seeded_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")


def test_agent_answers_revenue_through_governed_tool(seeded_database):
    result = answer("What was revenue last month by product category?")

    assert result["answer_rows"] == [
        {"category": "Electronics", "revenue": 500.0},
        {"category": "Home", "revenue": 405.0},
        {"category": "Books", "revenue": 280.0},
    ]
    assert result["verify_status"] == "pass"
    assert result["lineage_citation"] == _CITATION


def test_agent_customer_read_masks_then_allows_pii_role(seeded_database):
    viewer_result = answer("Show the customer directory and emails")
    pii_result = answer("Show the customer directory and emails", role="analyst_pii")

    assert {row["email"] for row in viewer_result["answer_rows"]} == {"***@example.com"}
    assert pii_result["answer_rows"][0]["email"] == "alice@example.com"


def test_agent_refuses_unknown_question_without_database_access():
    result = answer("What is gross margin by channel?")

    assert result == {"message": "I can only answer governed metrics: [aov, orders, revenue]"}


def test_agent_does_not_import_resolver_or_duckdb():
    source = (Path(__file__).resolve().parents[1] / "agent" / "agent.py").read_text(encoding="utf-8")

    assert "resolver" not in source
    assert "duckdb" not in source
