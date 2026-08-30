from __future__ import annotations

import json

import yaml

from evals.compare import render_prompt_ablation
from evals.prompt_variants import PROMPT_VARIANTS, render_prompt_variant, run_prompt_ablation


_PLAN = {
    "tool": "query_metric",
    "args": {"metric": "revenue", "dimensions": ["category"], "filters": {}},
}


class VariantStubProvider:
    """Return a different valid planner result for two generic prompt variants."""

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        del temperature
        if "Revenue by category" not in user:
            return '{"tool":"refuse","args":{}}'
        return (
            json.dumps(_PLAN)
            if "Examples demonstrate the governed surface" in system
            or "Before responding" in system
            else '{"tool":"refuse","args":{}}'
        )


def test_prompt_ablation_runs_each_pack_driven_variant_and_reports_cis(tmp_path):
    golden = tmp_path / "golden.yml"
    golden.write_text(
        yaml.safe_dump(
            [
                {
                    "case_id": "revenue-by-category",
                    "question": "Revenue by category",
                    "role": "viewer",
                    "expected_plan": _PLAN,
                    "expect": {"type": "metric"},
                },
                {
                    "case_id": "refuse",
                    "question": "Forecast future revenue",
                    "role": "viewer",
                    "expected_plan": {"tool": "refuse", "args": {}},
                    "expect": {"type": "refuse"},
                },
            ]
        ),
        encoding="utf-8",
    )

    report = run_prompt_ablation(
        models=["stub"],
        runs=1,
        golden=golden,
        provider_factory=lambda _model: VariantStubProvider(),
        output_path=tmp_path / "ablation.json",
    )

    assert tuple(report["variants"]) == PROMPT_VARIANTS
    assert report["variants"]["027-generalized"]["metrics"]["routing_accuracy"]["rate"] == 1.0
    assert report["variants"]["minimal"]["metrics"]["routing_accuracy"]["rate"] == 0.0
    for variant in PROMPT_VARIANTS:
        metrics = report["variants"][variant]["metrics"]
        assert metrics["hallucination_rate"] == {"rate": 0.0, "lo": 0.0, "hi": 0.0}
        assert set(metrics["routing_accuracy"]) == {"rate", "lo", "hi"}
    assert "Routing varied" in report["finding"]
    assert "governed hallucination" in render_prompt_ablation(report)


def test_prompt_variants_are_pack_driven_and_do_not_embed_fixture_answers(monkeypatch):
    monkeypatch.setenv("GROUNDED_PACK", "spider_world1")

    prompts = [render_prompt_variant(variant) for variant in PROMPT_VARIANTS]

    assert all('"total_population"' in prompt for prompt in prompts)
    assert all('"revenue"' not in prompt for prompt in prompts)
