from __future__ import annotations

from decimal import Decimal

import pytest

from governed.service import governed_query
from scripts.seed_duckdb import seed_database
from verify.verifier import verify_result


def test_revenue_rules_pass():
    outcomes = verify_result(
        [{"category": "Electronics", "revenue": Decimal("500.00")}],
        [
            {"type": "non_negative", "field": "revenue"},
            {"type": "not_null", "field": "category"},
        ],
    )

    assert [outcome["status"] for outcome in outcomes] == ["pass", "pass"]


def test_verification_reports_offending_values_without_raising():
    outcomes = verify_result(
        [{"category": None, "revenue": Decimal("-1.00")}],
        [
            {"type": "non_negative", "field": "revenue"},
            {"type": "not_null", "field": "category"},
        ],
    )

    assert outcomes[0]["status"] == "fail"
    assert "-1.00" in outcomes[0]["detail"]
    assert outcomes[1]["status"] == "fail"
    assert "None" in outcomes[1]["detail"]


@pytest.mark.parametrize("pack", ("fixture", "adventureworks"))
def test_revenue_total_marks_unselected_category_check_not_applicable(
    tmp_path, monkeypatch, pack
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GROUNDED_PACK", pack)
    database = tmp_path / "grounded.duckdb"
    seed_database(str(database))

    result = governed_query("revenue", db_path=str(database))

    assert result["verify_status"] == "pass"
    assert result["verification"] == [
        {"type": "non_negative", "field": "revenue", "status": "pass", "detail": "passed"},
        {
            "type": "not_null",
            "field": "category",
            "status": "n/a",
            "detail": "field not in result",
        },
    ]


def test_present_category_check_still_fails_for_a_null_category():
    outcomes = verify_result(
        [{"category": None, "revenue": Decimal("1.00")}],
        [{"type": "not_null", "field": "category"}],
        columns=["category", "revenue"],
    )

    assert outcomes == [
        {
            "type": "not_null",
            "field": "category",
            "status": "fail",
            "detail": "First offending value: None",
        }
    ]


def test_negative_total_still_fails_its_applicable_measure_check():
    outcomes = verify_result(
        [{"revenue": Decimal("-1.00")}],
        [
            {"type": "non_negative", "field": "revenue"},
            {"type": "not_null", "field": "category"},
        ],
        columns=["revenue"],
    )

    assert outcomes[0]["status"] == "fail"
    assert "-1.00" in outcomes[0]["detail"]
    assert outcomes[1] == {
        "type": "not_null",
        "field": "category",
        "status": "n/a",
        "detail": "field not in result",
    }
