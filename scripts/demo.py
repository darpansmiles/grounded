"""Run Grounded's deterministic governed-data walkthrough from a clean checkout."""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The fixture walkthrough is deliberately local and deterministic: it does not
# start or query the real Marquez service.
os.environ.setdefault("GROUNDED_PACK", "fixture")
os.environ.setdefault("GROUNDED_LINEAGE_SOURCE", "none")

from agent.agent import answer
from evals.metrics import compute_scorecard
from evals.runner import run_evals
from evals.scorecard import render_scorecard
from evals.trace import read_traces
from governed.service import governed_query
from harness.tools import check_policy, describe_metric, impact_of
from scripts.seed_duckdb import seed_database


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


def _print_payload(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=_json_default, ensure_ascii=False))


def _section(number: int, title: str, proof: str) -> None:
    print(f"\n{'=' * 72}\n{number}. {title}\n{'=' * 72}")
    print(f"Proves: {proof}")


def main() -> None:
    """Run every deterministic component used in the reviewer walkthrough."""
    os.chdir(ROOT)

    _section(1, "Seed the governed DuckDB fixture", "The demo data is reproducible.")
    seed_database("grounded.duckdb")
    print("Seeded grounded.duckdb with the completed-order fixture.")

    _section(2, "Use the Marquez lineage service", "Lineage verification has a dedicated OSS server.")
    print("Run `make marquez-up` and `make lineage` to inspect the real spine at http://localhost:3000.")

    _section(
        3,
        "Ask the agent for governed revenue",
        "The agent gets a defined, verified, cited answer instead of raw SQL access.",
    )
    agent_answer = answer("What was revenue last month by product category?")
    metric_description = describe_metric("revenue")
    _print_payload(
        {
            "answer_rows": agent_answer["answer_rows"],
            "metric_definition": agent_answer["metric_definition"],
            "policy_applied": agent_answer["policy_applied"],
            "verify_status": agent_answer["verify_status"],
            "lineage_citation": agent_answer["lineage_citation"],
            "lineage_graph_verified": metric_description["lineage_graph_verified"],
        }
    )

    _section(
        4,
        "Show governance enforcement",
        "The same metric obeys row policy, while PII policy is explainable.",
    )
    eu_revenue = governed_query(
        "revenue", ["category"], {"order_month": "last_month"}, role="eu_analyst"
    )
    email_policy = check_policy("customers.email", "viewer")
    _print_payload(
        {
            "eu_analyst_rows": eu_revenue["rows"],
            "row_filter_decisions": eu_revenue["policy_decisions"],
            "viewer_email_policy": email_policy,
        }
    )

    _section(
        5,
        "Ask what a raw-table change impacts",
        "Lineage makes downstream blast radius queryable.",
    )
    _print_payload(impact_of("raw.order_items"))

    _section(
        6,
        "Run the deterministic evaluation scorecard",
        "The golden set makes quality, policy, citation, and known gaps visible.",
    )
    with TemporaryDirectory() as temporary_directory:
        traces_path = Path(temporary_directory) / "traces.jsonl"
        run_evals(traces_path=traces_path)
        print(render_scorecard(compute_scorecard(read_traces(traces_path))))
    print(
        "For the real governed-vs-ungoverned model comparison, install Ollama and run `make benchmark`."
    )


if __name__ == "__main__":
    main()
