"""Render Contract-B lineage blocks as concise agent citations."""

from __future__ import annotations


def render_citation(definition: dict) -> str:
    """Render the declared metric-to-source lineage citation."""
    lineage = definition["lineage"]
    model = lineage["model"].removeprefix("sqlmesh:")
    tables = ", ".join(lineage["tables"])
    sources = ", ".join(lineage["sources"])
    return (
        f"{definition['metric']} ← Cube:{lineage['cube_member']} ← SQLMesh:{model} "
        f"← Tables:[{tables}] ← Source:[{sources}]"
    )
