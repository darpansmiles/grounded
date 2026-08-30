"""Resolve governed lineage through the Marquez service seam."""

from __future__ import annotations

import os
from typing import Any

import yaml

from harness.lineage_source import lineage_source
from packlib import active_pack

LINEAGE_SOURCE = os.environ.get("GROUNDED_LINEAGE_SOURCE", "marquez")


def _source():
    return lineage_source(LINEAGE_SOURCE)


def graph_lineage_for_metric(definition: dict) -> dict[str, Any]:
    """Fetch and validate Contract-B lineage through the selected backend."""
    return _source().verify(definition)


def _definitions() -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    pack = active_pack()
    for definition_path in sorted(pack.semantics.metrics if pack.semantics else ()):
        with definition_path.open(encoding="utf-8") as definition_file:
            definitions.append(yaml.safe_load(definition_file))
    return definitions


def impact_of(dataset: str) -> dict[str, Any]:
    """Return downstream datasets and governed metrics impacted by a dataset change."""
    lineage = _source().downstream(dataset)
    if not lineage["available"]:
        return {"available": False, "downstream_datasets": [], "downstream_metrics": []}
    downstream_datasets = sorted(
        f"{node['namespace']}.{node['name']}"
        for node in lineage["nodes"]
        if f"{node['namespace']}.{node['name']}" != dataset
    )
    impacted_dataset_ids = set(downstream_datasets) | {dataset}
    pack_namespace = active_pack().namespace
    downstream_metrics = [
        definition["metric"]
        for definition in _definitions()
        if {
            f"{pack_namespace}.{table}"
            for table in definition.get("lineage", {}).get("tables", [])
        }
        & impacted_dataset_ids
    ]
    return {
        "available": True,
        "downstream_datasets": downstream_datasets,
        "downstream_metrics": downstream_metrics,
    }
