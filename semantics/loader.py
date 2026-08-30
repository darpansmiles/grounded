"""Load semantic metric definitions and expand declared derived inheritance."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml

from packlib import active_pack


def _raw_definition(metric: str) -> dict[str, Any]:
    pack = active_pack()
    if pack.semantics is None:
        raise FileNotFoundError(metric)
    definition_path = next(
        (path for path in pack.semantics.metrics if path.stem == metric), None
    )
    if definition_path is None or not definition_path.is_file():
        raise FileNotFoundError(metric)
    with definition_path.open(encoding="utf-8") as definition_file:
        definition = yaml.safe_load(definition_file)
    if definition.get("metric") != metric:
        raise FileNotFoundError(metric)
    return definition


def _union(items: list[list[Any]]) -> list[Any]:
    combined: list[Any] = []
    for values in items:
        for value in values:
            if value not in combined:
                combined.append(deepcopy(value))
    return combined


def _inherited_dimensions(parents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dimensions: list[dict[str, Any]] = []
    for parent in parents:
        for dimension in parent["dimensions"]:
            existing = next((item for item in dimensions if item["name"] == dimension["name"]), None)
            if existing is not None and existing != dimension:
                raise ValueError(f"Conflicting inherited dimension: {dimension['name']}")
            if existing is None:
                dimensions.append(deepcopy(dimension))
    return dimensions


def load_expanded_definition(metric: str) -> dict[str, Any]:
    """Return a base definition or a ratio definition with parent fields inherited once."""
    definition = deepcopy(_raw_definition(metric))
    if definition.get("definition", {}).get("derived") != "ratio":
        return definition

    parents = [load_expanded_definition(parent) for parent in definition.get("inherits", [])]
    if not parents:
        raise ValueError(f"Derived metric {metric} must declare inherited parents")
    definition["dimensions"] = _inherited_dimensions(parents)
    first_lineage = deepcopy(parents[0]["lineage"])
    first_lineage["tables"] = _union([parent["lineage"]["tables"] for parent in parents])
    first_lineage["sources"] = _union([parent["lineage"]["sources"] for parent in parents])
    definition["lineage"] = first_lineage
    definition["policies"] = _union([parent.get("policies", []) for parent in parents])
    return definition
