from __future__ import annotations

import json

import pytest

from evals.render_card import render_all, render_card


def _review() -> dict:
    rate = lambda numerator, denominator: {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }
    arm = {
        "answer_correctness_when_answered": rate(3, 3),
        "wrong_answer_rate": rate(0, 3),
        "interface_compliance_rate": rate(3, 3),
        "policy_compliance_rate": rate(0, 0),
        "evidence_completeness_rate": rate(3, 3),
    }
    return {
        "dataset": "fixture",
        "evaluator_self_test": {"passed": True},
        "models": {
            "stub:latest": {
                "groups": {"in_catalog": {"governed": arm, "ungoverned": arm}},
                "samples": [{"run": 1}, {"run": 2}, {"run": 3}],
            }
        },
    }


def test_render_card_formats_rate_denominators_and_fixture_low_n_caveat(tmp_path):
    capture = tmp_path / "fixture-final-r3.jsonl"
    capture.write_text("capture", encoding="utf-8")

    rendered = render_card(
        _review(),
        capture_path=capture,
        review_path=tmp_path / "fixture-final-r3-review-066.json",
        scoring_commit="066abcd",
        dataset_tree="tree",
    )

    assert "| stub | 100.0% (3/3)" in rendered
    assert "NA (0/0)" in rendered
    assert "Applicable denominators range from 3 to 30" in rendered
    assert "scoring commit: `066abcd`" in rendered
    assert "fixture-final-r3-review-066.json" in rendered


def test_render_card_refuses_a_failed_evaluator_gate(tmp_path):
    review = _review()
    review["evaluator_self_test"]["passed"] = False
    capture = tmp_path / "fixture-final-r3.jsonl"
    capture.write_text("capture", encoding="utf-8")

    with pytest.raises(ValueError, match="passing evaluator self-test"):
        render_card(
            review,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review-066.json",
            scoring_commit="066abcd",
            dataset_tree="tree",
        )


def test_render_all_requires_authoritative_066_review_files(tmp_path):
    scores = tmp_path / "scores"
    captures = tmp_path / "captures"
    scores.mkdir()
    captures.mkdir()
    (scores / "aw-final-r3-review-066.json").write_text(
        json.dumps(_review()), encoding="utf-8"
    )

    with pytest.raises(FileNotFoundError):
        render_all(
            scores_dir=scores,
            captures_dir=captures,
            results_dir=tmp_path / "results",
            scoring_commit="066abcd",
        )
