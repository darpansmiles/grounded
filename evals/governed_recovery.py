"""Deterministically recover legacy governed rows for an offline score audit.

This module is deliberately separate from ``offline_scoring``. Independent
truth remains resolver-free; this is an opt-in replay of a stored plan only
when an old bounded capture cannot be compared at response precision.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from agent.agent import _execute_tool_call
from packlib import load_pack

GovernedRowsRecoverer = Callable[[dict[str, Any], str, str | Path | None], list[dict[str, Any]]]


@contextmanager
def _active_pack(dataset: str):
    """Set the pack-selection seam only while replaying one stored plan."""
    previous = os.environ.get("GROUNDED_PACK")
    try:
        os.environ["GROUNDED_PACK"] = dataset
        yield
    finally:
        if previous is None:
            os.environ.pop("GROUNDED_PACK", None)
        else:
            os.environ["GROUNDED_PACK"] = previous


def needs_governed_row_recovery(record: dict[str, Any]) -> bool:
    """Return whether a legacy preview would otherwise use an exact-hash fallback."""
    manifest = record.get("_capture_manifest")
    legacy_capture = not isinstance(manifest, dict) or manifest.get("schema_version", 0) < 3
    rows = record.get("governed_rows")
    row_count = record.get("governed_row_count")
    plan = record.get("produced_plan")
    return (
        legacy_capture
        and isinstance(rows, list)
        and isinstance(row_count, int)
        and row_count > len(rows)
        and record.get("governed_executed") is True
        and isinstance(plan, dict)
        and plan.get("tool") != "refuse"
    )


def make_governed_rows_recoverer(
    *, cube_url: str | None = None
) -> GovernedRowsRecoverer:
    """Build a recoverer that executes only the stored plan under its stored role."""

    def recover(
        record: dict[str, Any], dataset: str, db_path: str | Path | None
    ) -> list[dict[str, Any]]:
        pack = load_pack(dataset)
        if pack.semantics is None:
            raise ValueError(f"Dataset pack {dataset!r} has no governed semantic backend")
        plan = record.get("produced_plan")
        role = record.get("role")
        if not isinstance(plan, dict) or not isinstance(role, str):
            raise TypeError("Stored governed replay requires produced_plan and role")
        with _active_pack(dataset):
            response = _execute_tool_call(
                plan,
                role,
                backend=pack.semantics.backend,
                cube_url=cube_url,
                db_path=str(db_path or pack.destination.path),
            )
        rows = response.get("answer_rows")
        if not isinstance(rows, list):
            raise TypeError("Stored governed replay returned no answer_rows list")
        return rows

    return recover
