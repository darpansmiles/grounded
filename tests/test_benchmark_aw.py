from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import duckdb

from agent.agent import answer
from agent.ungoverned import answer_ungoverned
from evals.benchmark import load_golden_cases
from evals.compare import run_comparison
from models.provider import StubProvider
from packlib import active_pack
from resolver.backends import cube

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_GOLDEN = active_pack().golden
_LAKEHOUSE = active_pack().destination.path


class _RecordedResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _PromptRecordingProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        del user, temperature
        self.prompts.append(system)
        return self.response


def _recorded_post(payload: dict, calls: list[dict]):
    def post(url: str, *, json: dict, timeout: float) -> _RecordedResponse:
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _RecordedResponse(payload)

    return post


def _cube_revenue_payload() -> dict:
    return json.loads(
        (_FIXTURES / "cube_revenue_by_category.json").read_text(encoding="utf-8")
    )


def test_agent_threads_cube_backend_to_recorded_load(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls: list[dict] = []
    monkeypatch.setattr(
        cube.httpx, "post", _recorded_post(_cube_revenue_payload(), calls)
    )

    result = answer(
        "What was revenue last month by product category?",
        backend="cube",
        cube_url="http://cube.test/cubejs-api/v1",
    )

    assert result["answer_rows"] == [
        {"category": "Bikes", "revenue": 94651172.72},
        {"category": "Components", "revenue": 11802593.29},
        {"category": "Clothing", "revenue": 2120542.53},
        {"category": "Accessories", "revenue": 1272072.89},
    ]
    assert calls[0]["url"] == "http://cube.test/cubejs-api/v1/load"
    assert calls[0]["json"]["query"]["measures"] == ["Sales.revenue"]


def test_aw_comparison_routes_cube_and_persists_publishable_record(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    cube_calls: list[dict] = []

    def cube_truth(
        metric: str,
        dimensions: list[str],
        filters: dict,
        role: str,
        *,
        db_path: str,
        backend: str,
        cube_url: str | None,
    ) -> dict:
        cube_calls.append(
            {
                "metric": metric,
                "dimensions": dimensions,
                "filters": filters,
                "role": role,
                "db_path": db_path,
                "backend": backend,
                "cube_url": cube_url,
            }
        )
        row = {dimension: "Bikes" for dimension in dimensions}
        row[metric] = Decimal("1.00")
        return {"rows": [row]}

    monkeypatch.setattr("evals.compare.governed_query", cube_truth)
    cases = load_golden_cases(_GOLDEN)
    planned = {case["question"]: json.dumps(case["expected_plan"]) for case in cases}
    ungoverned = _PromptRecordingProvider("SELECT 0 AS revenue")

    card = run_comparison(
        ["stub"],
        runs=1,
        dataset="adventureworks",
        cube_url="http://cube.test/cubejs-api/v1",
        governed_provider_factory=lambda _model: StubProvider(planned),
        ungoverned_provider_factory=lambda _model: ungoverned,
        output_path=tmp_path / "model_card.json",
        results_dir=tmp_path / "results",
    )

    record_path = next((tmp_path / "results").glob("benchmark-adventureworks-*.json"))
    markdown_path = next(
        path
        for path in (tmp_path / "results").glob("benchmark-adventureworks-*.md")
        if not path.name.endswith("-failures.md")
    )
    failures_path = next((tmp_path / "results").glob("benchmark-adventureworks-*-failures.md"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    governed = card["model_cards"]["stub"]["governed"]

    assert cube_calls and all(call["backend"] == "cube" for call in cube_calls)
    assert all(call["db_path"] == str(_LAKEHOUSE) for call in cube_calls)
    assert governed["hallucination_rate"] == 0.0
    assert card["model_cards"]["stub"]["ungoverned"]["hallucination_rate"] > 0
    assert "gold.fct_sales" in ungoverned.prompts[0]
    assert record["metadata"]["dataset"] == "adventureworks"
    assert record["metadata"]["cube_on"] is True
    assert record["metadata"]["golden_set"] == "golden.yml"
    assert "| hallucination_rate | 0.0% |" in markdown_path.read_text(encoding="utf-8")
    assert "SELECT 0 AS revenue" in failures_path.read_text(encoding="utf-8")


def test_aw_ungoverned_wrong_sql_and_write_rejection_leave_gold_intact():
    connection = duckdb.connect(str(_LAKEHOUSE), read_only=True)
    try:
        before = connection.execute("SELECT COUNT(*) FROM gold.fct_sales").fetchone()[0]
    finally:
        connection.close()

    wrong = answer_ungoverned(
        "What is revenue by category?",
        StubProvider({"revenue": "SELECT 0 AS revenue"}),
        str(_LAKEHOUSE),
        dataset="aw",
    )
    rejected = answer_ungoverned(
        "Delete the gold table",
        StubProvider({"Delete": "DROP TABLE gold.fct_sales"}),
        str(_LAKEHOUSE),
        dataset="aw",
    )

    connection = duckdb.connect(str(_LAKEHOUSE), read_only=True)
    try:
        after = connection.execute("SELECT COUNT(*) FROM gold.fct_sales").fetchone()[0]
    finally:
        connection.close()

    assert wrong["schema_break"] is False
    assert rejected["schema_break"] is True
    assert rejected["rejection_reason"] == "only one SELECT statement is allowed"
    assert after == before


def test_golden_v3_has_only_declared_tools_and_metrics():
    cases = load_golden_cases(_GOLDEN)

    assert len(cases) == 105
    assert {
        case["expected_plan"]["args"]["metric"]
        for case in cases
        if case["expected_plan"]["tool"] == "query_metric"
    } == {
        "revenue",
        "orders",
        "aov",
    }
