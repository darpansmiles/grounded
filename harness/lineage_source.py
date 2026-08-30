"""Lineage backends for the governed harness."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from packlib import active_pack

DEFAULT_MARQUEZ_URL = "http://localhost:5050"
_LOGGER = logging.getLogger(__name__)


def _split_dataset(dataset: str) -> tuple[str, str]:
    pack_namespace = active_pack().namespace
    prefix = f"{pack_namespace}."
    if dataset.startswith(prefix):
        layer, name = dataset.removeprefix(prefix).split(".", maxsplit=1)
        return f"{pack_namespace}.{layer}", name
    return dataset.split(".", maxsplit=1)


def _dataset_id(node: dict[str, Any]) -> str:
    return f"{node['namespace']}.{node['name']}"


def _scoped_dataset_id(dataset: str) -> str:
    """Resolve a public layer-qualified ID into the active pack's graph ID."""
    namespace = active_pack().namespace
    return dataset if dataset.startswith(f"{namespace}.") else f"{namespace}.{dataset}"


def _empty_lineage() -> dict[str, Any]:
    return {"available": False, "nodes": [], "edges": []}


def _verify(definition: dict[str, Any], lineage: dict[str, Any]) -> dict[str, Any]:
    if not lineage["available"]:
        return {**lineage, "verified": False}
    node_ids = {_dataset_id(node) for node in lineage["nodes"]}
    pack_namespace = active_pack().namespace
    declared_tables = {
        f"{pack_namespace}.{table}" for table in definition["lineage"]["tables"]
    }
    source_nodes = {
        _dataset_id(node)
        for node in lineage["nodes"]
        if node.get("namespace") == f"{pack_namespace}.postgres"
    }
    return {
        **lineage,
        "verified": node_ids - source_nodes == declared_tables and bool(source_nodes),
    }


class NoneLineageSource:
    """Graceful no-lineage implementation for an unavailable server."""

    def upstream(self, _dataset: str) -> dict[str, Any]:
        return _empty_lineage()

    def downstream(self, _dataset: str) -> dict[str, Any]:
        return _empty_lineage()

    def verify(self, definition: dict[str, Any]) -> dict[str, Any]:
        return _verify(definition, self.upstream(definition["lineage"]["tables"][0]))


class MarquezLineageSource(NoneLineageSource):
    """Dataset-level lineage reader backed by Marquez's REST graph endpoint."""

    def __init__(self, base_url: str = DEFAULT_MARQUEZ_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def _query(self, dataset: str) -> list[dict[str, Any]] | None:
        namespace, name = _split_dataset(dataset)
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    f"{self._base_url}/api/v1/lineage",
                    params={"nodeId": f"dataset:{namespace}:{name}", "depth": 10},
                )
                response.raise_for_status()
                graph = response.json()["graph"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            _LOGGER.warning("Marquez lineage is unavailable: %s", exc)
            return None
        if not isinstance(graph, list):
            _LOGGER.warning("Marquez lineage response did not contain a graph list")
            return None
        return graph

    @staticmethod
    def _dataset_nodes(graph: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
        nodes: dict[str, dict[str, str]] = {}
        for node in graph:
            if node.get("type") != "DATASET" or not str(node.get("id", "")).startswith("dataset:"):
                continue
            _, namespace, name = node["id"].split(":", maxsplit=2)
            nodes[node["id"]] = {"type": "Dataset", "namespace": namespace, "name": name}
        return nodes

    @staticmethod
    def _dataset_edges(graph: list[dict[str, Any]]) -> list[tuple[str, str, dict[str, str]]]:
        graph_nodes = {node.get("id"): node for node in graph}
        edges: list[tuple[str, str, dict[str, str]]] = []
        for job_id, job in graph_nodes.items():
            if not isinstance(job_id, str) or job.get("type") != "JOB":
                continue
            inputs = [
                edge["origin"]
                for edge in job.get("inEdges", [])
                if str(edge.get("origin", "")).startswith("dataset:")
            ]
            outputs = [
                edge["destination"]
                for edge in job.get("outEdges", [])
                if str(edge.get("destination", "")).startswith("dataset:")
            ]
            _, job_namespace, job_name = job_id.split(":", maxsplit=2)
            for source in inputs:
                for target in outputs:
                    edges.append((source, target, {"namespace": job_namespace, "name": job_name}))
        return edges

    def _traverse(self, dataset: str, direction: str) -> dict[str, Any]:
        graph = self._query(dataset)
        if graph is None:
            return _empty_lineage()
        nodes_by_id = self._dataset_nodes(graph)
        namespace, name = _split_dataset(dataset)
        start = f"dataset:{namespace}:{name}"
        if start not in nodes_by_id:
            return _empty_lineage()
        all_edges = self._dataset_edges(graph)
        visited = {start}
        frontier = [start]
        selected_edges: set[tuple[str, str, str, str]] = set()
        while frontier:
            current = frontier.pop()
            for source, target, job in all_edges:
                if direction == "upstream" and target == current:
                    next_node = source
                elif direction == "downstream" and source == current:
                    next_node = target
                else:
                    continue
                selected_edges.add((source, target, job["namespace"], job["name"]))
                if next_node not in visited:
                    visited.add(next_node)
                    frontier.append(next_node)

        nodes = [nodes_by_id[node_id] for node_id in sorted(visited)]
        edges = [
            {
                "type": direction,
                "from": nodes_by_id[source],
                "to": nodes_by_id[target],
                "job": {"namespace": namespace, "name": name},
                "relation": "reads_from" if direction == "upstream" else "produces",
            }
            for source, target, namespace, name in sorted(selected_edges)
        ]
        return {"available": True, "nodes": nodes, "edges": edges}

    def upstream(self, dataset: str) -> dict[str, Any]:
        return self._traverse(_scoped_dataset_id(dataset), "upstream")

    def downstream(self, dataset: str) -> dict[str, Any]:
        return self._traverse(_scoped_dataset_id(dataset), "downstream")

    def verify(self, definition: dict[str, Any]) -> dict[str, Any]:
        return _verify(definition, self.upstream(definition["lineage"]["tables"][0]))


def lineage_source(name: str) -> NoneLineageSource:
    """Return the selected lineage backend without changing harness contracts."""
    if name == "marquez":
        return MarquezLineageSource()
    if name == "none":
        return NoneLineageSource()
    raise ValueError(f"Unsupported lineage source: {name}")
