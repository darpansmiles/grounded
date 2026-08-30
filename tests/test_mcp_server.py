from __future__ import annotations

import asyncio

import harness.server as grounded_server


def test_mcp_server_lists_exactly_seven_described_tools():
    tools = asyncio.run(grounded_server.server.list_tools())

    assert [tool.name for tool in tools] == [
        "list_metrics",
        "describe_metric",
        "query_metric",
        "query_customers",
        "check_policy",
        "impact_of",
        "search_docs",
    ]
    assert all(tool.description for tool in tools)
    assert all(tool.input_schema is not None for tool in tools)
