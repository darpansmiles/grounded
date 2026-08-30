from __future__ import annotations

from decimal import Decimal

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
