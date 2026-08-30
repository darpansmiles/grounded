"""Thin stdio MCP registration for Grounded's governed tool surface."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from harness.tools import (
    check_policy,
    describe_metric,
    impact_of,
    list_metrics,
    query_customers,
    query_metric,
    search_docs,
)

server = MCPServer(
    name="grounded",
    description="Governed metrics with policy, verification, audit, and Contract-B lineage citations.",
)


@server.tool(name="list_metrics")
def list_metrics_tool() -> list[dict]:
    """List the available governed metrics an agent may query."""
    return list_metrics()


@server.tool(name="describe_metric")
def describe_metric_tool(metric: str) -> dict:
    """Return a governed metric definition, policies, verification rules, and lineage citation."""
    return describe_metric(metric)


@server.tool(name="query_metric")
def query_metric_tool(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict | None = None,
    role: str = "viewer",
) -> dict:
    """Execute a governed metric query with policy, verification, audit, and lineage attached."""
    return query_metric(metric, dimensions, filters, role)


@server.tool(name="query_customers")
def query_customers_tool(role: str = "viewer") -> dict:
    """Governed read of the customer directory; email is masked unless the role is permitted; every call is audited."""
    return query_customers(role)


@server.tool(name="check_policy")
def check_policy_tool(target: str, role: str) -> dict:
    """Explain whether a role is allowed, masked, or denied for a governed target column."""
    return check_policy(target, role)


@server.tool(name="impact_of")
def impact_of_tool(dataset: str) -> dict:
    """Return datasets and governed metrics downstream of a dataset change."""
    return impact_of(dataset)


@server.tool(name="search_docs")
def search_docs_tool(query: str, k: int = 3) -> list[dict]:
    """Retrieve cited metric-definition and governance prose; it does not answer numeric questions."""
    return search_docs(query, k)


def main() -> None:
    """Run the seven governed tools over the MCP stdio transport."""
    server.run("stdio")


if __name__ == "__main__":
    main()
