from __future__ import annotations

import pytest

from evals.benchmark import (
    GOLDEN_CATEGORIES,
    load_golden_cases,
    validate_categorized_golden,
)


@pytest.mark.parametrize(
    "pack,minimum",
    [
        ("adventureworks", 100),
        ("tpch", 80),
        ("spider_world1", 40),
        ("bird_ca_schools", 40),
        ("fixture", 20),
    ],
)
def test_pm_categorized_goldens_are_valid_for_each_pack(monkeypatch, pack, minimum):
    monkeypatch.setenv("GROUNDED_PACK", pack)
    cases = load_golden_cases(f"datasets/{pack}/golden.yml")

    counts = validate_categorized_golden(cases)

    assert len(cases) >= minimum
    assert set(counts) <= GOLDEN_CATEGORIES
    assert any(case["expected_plan"]["tool"] == "refuse" for case in cases)
