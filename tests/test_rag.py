from __future__ import annotations

import asyncio
import json

import harness.server as grounded_server
from agent.agent import answer
from agent.llm_planner import plan_llm
from harness.tools import search_docs
from models.provider import StubProvider
from packlib import PROJECT_ROOT, active_pack
from rag.retriever import search
from scripts.seed_duckdb import seed_database


def test_retriever_returns_the_revenue_definition_as_the_top_chunk():
    result = search("what does revenue mean")

    revenue_path = next(
        path for path in active_pack().semantics.metrics if path.stem == "revenue"
    )
    assert result[0]["doc"] == str(revenue_path.relative_to(PROJECT_ROOT))
    assert result[0]["heading"] == "Revenue"
    assert result[0]["score"] > result[1]["score"]


def test_retriever_returns_pii_masking_as_the_top_chunk():
    result = search("how is customer email protected")

    assert result[0]["doc"] == "rag/data_dictionary.md"
    assert result[0]["heading"] == "PII masking"
    assert result[0]["score"] > result[1]["score"]


def test_search_docs_returns_scored_chunks_and_is_registered_on_mcp_server():
    results = search_docs("what does revenue mean", k=2)
    tools = asyncio.run(grounded_server.server.list_tools())

    assert len(results) == 2
    assert results[0]["chunk"]["heading"] == "Revenue"
    assert results[0]["score"] > 0
    assert "search_docs" in [tool.name for tool in tools]


def test_agent_routes_meaning_to_cited_docs_but_numbers_to_the_metric_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_database("grounded.duckdb")
    meaning = answer("What does revenue mean?")
    numeric = answer("What was revenue last month by product category?")

    assert meaning["doc_citation"] == "[datasets/adventureworks/semantics/revenue.yml#Revenue]"
    assert meaning["doc_citation"] in meaning["answer"]
    assert numeric["answer_rows"][0] == {"category": "Electronics", "revenue": 500.0}
    assert numeric["lineage_citation"]


def test_llm_planner_allows_search_docs_but_refuses_an_out_of_surface_tool():
    search_call = {"tool": "search_docs", "args": {"query": "how is PII handled?"}}
    provider = StubProvider(
        {
            "pii": json.dumps(search_call),
            "outside": '{"tool":"vector_search","args":{"query":"revenue"}}',
        }
    )

    assert plan_llm("pii", provider) == search_call
    assert plan_llm("outside", provider) == {"tool": "refuse", "args": {}}
