"""Apply Contract-B masking and deny policies to governed result rows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

MASK_TOKEN = "***@example.com"


def row_predicates_for_role(definition: dict, role: str) -> list[dict]:
    """Return trusted Contract-B row-filter decisions applicable to a role."""
    decisions: list[dict] = []
    for policy in definition.get("policies", []):
        if policy.get("rule") != "row_filter" or role not in policy.get(
            "when_role", []
        ):
            continue
        predicate = policy["predicate"]
        policy_id = policy["id"]
        decision = {
            "id": policy_id,
            "target": policy["applies_to"],
            "rule": "row_filter",
            "decision": "row_filter",
            "predicate": predicate,
            "reason": f"{policy_id}: rows filtered to {predicate} for role {role}",
        }
        for field in ("cube_member", "operator", "values"):
            if field in policy:
                decision[field] = policy[field]
        decisions.append(decision)
    return decisions


def mask_email(value: Any) -> Any:
    """Keep an email domain while replacing its local part with a fixed mask."""
    if value is None:
        return None
    if not isinstance(value, str) or "@" not in value:
        return MASK_TOKEN
    return f"***@{value.rsplit('@', 1)[1]}"


def _policy_for_target(target: str, definition: dict) -> dict | None:
    return next(
        (
            policy
            for policy in definition.get("policies", [])
            if policy.get("applies_to") == target
        ),
        None,
    )


def _is_pii_column(target: str, definition: dict) -> bool:
    return any(
        column.get("pii") is True and column.get("source") == target
        for column in definition.get("columns", [])
    )


def check_policy(target: str, role: str, definition: dict) -> dict:
    """Return the declared access decision for one governed target column."""
    policy = _policy_for_target(target, definition)
    if policy is None:
        if _is_pii_column(target, definition):
            return {
                "target": target,
                "rule": "mask",
                "decision": "mask",
                "reason": f"{target} is PII and is masked by default",
            }
        return {
            "target": target,
            "rule": "allow",
            "decision": "allow",
            "reason": f"No policy applies to {target}",
        }

    rule = policy["rule"]
    policy_id = policy["id"]
    if rule == "deny":
        return {
            "target": target,
            "rule": rule,
            "decision": "deny",
            "reason": f"{policy_id}: {target} denied",
        }
    if rule == "mask":
        allowed_roles = policy.get("unless_role", [])
        if role in allowed_roles:
            return {
                "target": target,
                "rule": rule,
                "decision": "allow",
                "reason": f"{policy_id}: {target} allowed for role {role}",
            }
        return {
            "target": target,
            "rule": rule,
            "decision": "mask",
            "reason": f"{policy_id}: {target} masked unless role in [{', '.join(allowed_roles)}]",
        }
    return {
        "target": target,
        "rule": rule,
        "decision": "allow",
        "reason": f"{policy_id}: {target} allowed",
    }


def apply_masking(
    rows: list[dict], definition: dict, role: str
) -> tuple[list[dict], list[dict]]:
    """Mask declared PII fields in result rows and return the decisions applied."""
    masked_rows = deepcopy(rows)
    present_fields = {field for row in masked_rows for field in row}
    decisions: list[dict] = []

    policy_targets = {
        policy.get("applies_to") for policy in definition.get("policies", [])
    }
    targets = [policy.get("applies_to") for policy in definition.get("policies", [])]
    targets.extend(
        column["source"]
        for column in definition.get("columns", [])
        if column.get("pii") is True and column["source"] not in policy_targets
    )

    for target in targets:
        field = target.rsplit(".", 1)[-1]
        if field not in present_fields:
            continue
        decision = check_policy(target, role, definition)
        decisions.append(decision)
        if decision["decision"] == "mask":
            for row in masked_rows:
                if field in row:
                    row[field] = mask_email(row[field])
        elif decision["decision"] == "deny":
            raise PermissionError(decision["reason"])

    return masked_rows, decisions
