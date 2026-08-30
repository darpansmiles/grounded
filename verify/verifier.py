"""Run declarative result checks without converting data failures into exceptions."""

from __future__ import annotations


def verify_result(rows: list[dict], verification_rules: list[dict]) -> list[dict]:
    """Return a pass/fail record for every declared verification rule."""
    outcomes: list[dict] = []
    for rule in verification_rules:
        rule_type = rule["type"]
        field = rule["field"]
        no_offense = object()
        offending_value = no_offense

        if rule_type == "non_negative":
            offending_value = next(
                (row.get(field) for row in rows if field not in row or row.get(field) is None or row.get(field) < 0),
                no_offense,
            )
        elif rule_type == "not_null":
            offending_value = next(
                (row.get(field) for row in rows if field not in row or row.get(field) is None),
                no_offense,
            )
        else:
            outcomes.append(
                {
                    "type": rule_type,
                    "field": field,
                    "status": "fail",
                    "detail": f"Unsupported verification rule: {rule_type}",
                }
            )
            continue

        if offending_value is no_offense:
            outcomes.append({"type": rule_type, "field": field, "status": "pass", "detail": "passed"})
        else:
            outcomes.append(
                {
                    "type": rule_type,
                    "field": field,
                    "status": "fail",
                    "detail": f"First offending value: {offending_value!r}",
                }
            )
    return outcomes
