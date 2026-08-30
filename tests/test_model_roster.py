from __future__ import annotations

import json

import yaml

from evals.benchmark import run_benchmark
from evals.roster import model_roster
from models.provider import StubProvider


def test_configured_roster_drives_stubbed_n_model_matrix(tmp_path, monkeypatch):
    roster_path = tmp_path / "roster.yml"
    roster_path.write_text("models: [stub-one, stub-two, stub-three, stub-four]\n")
    golden_path = tmp_path / "golden.yml"
    golden_path.write_text(
        yaml.safe_dump(
            [{"case_id": "refuse", "question": "Forecast", "role": "viewer", "expected_plan": {"tool": "refuse", "args": {}}, "expect": {"type": "refuse"}}]
        )
    )
    monkeypatch.setenv("GROUNDED_MODEL_ROSTER", str(roster_path))

    result = run_benchmark(
        runs=1,
        golden=golden_path,
        provider_factory=lambda _model: StubProvider({"Forecast": json.dumps({"tool": "refuse", "args": {}})}),
        output_path=tmp_path / "benchmark.json",
    )

    assert model_roster() == ["stub-one", "stub-two", "stub-three", "stub-four"]
    assert result["models"] == model_roster()
    assert all(card["status"] == "completed" for card in result["scorecards"].values())
