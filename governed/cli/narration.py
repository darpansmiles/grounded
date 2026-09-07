"""Approved narration for the guided quickstart stage walk."""

from __future__ import annotations

FULL_TOUR_NARRATION = {
    "movement": "This stage moves only the declared source tables into bronze and records what arrived. That producer record gives later consumers a concrete origin and row-count boundary. You will see the bronze relations and the OpenLineage handoff.",
    "transform": "Raw source shape is useful for loading, not for answering. This stage builds and audits a silver-to-gold analytical shape so the metric layer has stable relations to read. You will see the resulting tables and their row counts.",
    "semantic": "A schema lists columns but does not say which number is approved. The semantic layer declares the metrics, dimensions, owners, and limits that an agent may use. You will see that catalog rather than a guessed interpretation of tables.",
    "metric_tree": "Derived metrics are composed from declared parents, not recreated in a prompt. Their parent definitions carry compatible dimensions, policy, and lineage into the derived answer. You will see the declared relationship directly.",
    "lineage": "A precise number still needs an evidence path. This stage connects source, bronze, transformed data, and the semantic metric so the path can be inspected. You can open the local graph after seeing the compact citation.",
    "policy": "Policy is applied before execution, not added as a note after a result. The declared rules decide which fields are masked and which rows a role may see. You will see the concrete role decisions that bound an answer.",
}


def metric_tree_bridge(base_parents: list[str]) -> str:
    """Connect the semantic catalog to the subset that composes ratios."""
    return (
        "The other declared metrics — "
        + ", ".join(base_parents)
        + " — are the base parents these ratios compose from (listed in the semantic layer above)."
    )


ROUTING_ANNOTATIONS = {
    "list_metrics": (
        "The model chose to list metrics, not to compute a value. The harness executed exactly that "
        "declared call. No number was fabricated: this is a routing choice, not a hallucination.\n"
        "Smaller models make this choice more often; try the recommended default to see the computed answer."
    ),
    "describe_metric": (
        "The model chose to describe a metric, not to compute a value. The harness executed exactly that "
        "declared call. No number was fabricated: this is a routing choice, not a hallucination.\n"
        "Smaller models make this choice more often; try the recommended default to see the computed answer."
    ),
    "refuse": (
        "The model returned a structured refusal, so the harness did not execute an ungoverned fallback. "
        "No number was fabricated."
    ),
}

QUICK_RUN_NARRATION = (
    "This is a ready-to-use SQLite pack, so movement and transformation do not run here. "
    "We go straight to its declared semantic layer."
)

FIXTURE_NARRATION = (
    "This pack is seeded in DuckDB, so movement and transformation do not run here, "
    "and no Docker service is needed. We go straight to its declared semantic layer."
)

LANDING_SPLASH = """
GROUNDED

   ____ ____   ___  _   _ _   _ ____  _____ ____
  / ___|  _ \\ / _ \\| | | | \\ | |  _ \\| ____|  _ \\
 | |  _| |_) | | | | | | |  \\| | | | |  _| | | | |
 | |_| |  _ <| |_| | |_| | |\\  | |_| | |___| |_| |
  \\____|_| \\_\\___/ \\___/|_| \\_|____/|_____|____/

A governed harness that lets a small local model answer data questions without writing SQL.
The model routes one declared metric call. The platform resolves the definition, enforces policy, verifies the result, and cites lineage.
Hallucination is measured, not asserted.

Intelligence Is a System: https://intelligenceisasystem.substack.com
GitHub: https://github.com/darpansmiles/grounded
LinkedIn: https://www.linkedin.com/in/darpan-vyas/
""".strip()
