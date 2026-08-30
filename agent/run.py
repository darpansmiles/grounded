"""CLI renderer for the deterministic governed-agent demo."""

from __future__ import annotations

import sys
from decimal import Decimal

from agent.agent import answer


def _format_value(value: object) -> str:
    if isinstance(value, (float, Decimal)):
        return f"{value:.2f}"
    return str(value)


def main() -> None:
    """Print a readable governed answer for one question."""
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -m agent.run "<question>"')

    result = answer(sys.argv[1])
    if "message" in result:
        print(result["message"])
        return

    print("Answer rows:")
    for row in result["answer_rows"]:
        print("  " + " | ".join(f"{field}: {_format_value(value)}" for field, value in row.items()))
    if result["metric_definition"]:
        definition = result["metric_definition"]
        print(
            "Metric: revenue = "
            f"{definition['measure']} (grain: {definition['grain']}; filter: {definition['filter']})"
        )
    if result["policy_applied"]:
        print(f"Policy applied: {result['policy_applied']}")
    else:
        print("Policy applied: none blocks this aggregate (no PII exposed; customers.email remains masked at the source-facing layer).")
    print(f"Verification: {result['verify_status']}")
    if result["lineage_citation"]:
        print(f"Lineage: {result['lineage_citation']}")


if __name__ == "__main__":
    main()
