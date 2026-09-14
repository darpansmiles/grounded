from __future__ import annotations

import hashlib
import json

import pytest

from evals import render_card as card_renderer
from evals.offline_scoring import score_capture_files
from evals.render_card import render_all, render_card
from scripts.seed_duckdb import seed_database


@pytest.fixture(autouse=True)
def _stable_scored_pack_identity(monkeypatch):
    monkeypatch.setattr(card_renderer, "_dataset_tree_at_revision", lambda *_args: "tree")
    monkeypatch.setattr(
        card_renderer, "_expected_case_ids_at_revision", lambda *_args: ["case-1"]
    )


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
                "valid": True,
                "groups": {"in_catalog": {"governed": arm, "ungoverned": arm}},
                "samples": [
                    {"case_id": "case-1", "run": 1},
                    {"case_id": "case-1", "run": 2},
                    {"case_id": "case-1", "run": 3},
                ],
            }
        },
    }


def _write_capture(path, *, runs=(1, 2, 3)) -> None:
    records = [
        {"record_type": "manifest", "dataset": "fixture", "models": ["stub:latest"], "runs": 3}
    ]
    records.extend(
        {
            "record_type": "case",
            "model": "stub:latest",
            "case_id": "case-1",
            "run": run,
        }
        for run in runs
    )
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def _captured_metric_record(run: int) -> dict:
    plan = {
        "tool": "query_metric",
        "args": {
            "metric": "revenue",
            "dimensions": [],
            "filters": {"order_month": "last_month"},
        },
    }
    return {
        "record_type": "case",
        "case_id": "case-1",
        "model": "stub",
        "run": run,
        "category": "total",
        "role": "viewer",
        "expect": {"type": "metric"},
        "expected_plan": plan,
        "produced_plan": plan,
        "schema_valid": True,
        "governed_executed": True,
        "governed_rows": [{"revenue": 1185.0}],
        "policy_decisions": [],
        "evidence": {
            "metric_definition": {"measure": "sum"},
            "lineage_citation": "revenue ← fixture lineage",
            "verification": [],
            "verify_status": "pass",
        },
        "ungoverned": {
            "raw_sql": "SELECT 1185 AS revenue",
            "rows": [{"revenue": 1185.0}],
            "schema_break": False,
        },
    }


def _score_capture_for_publication_gate(
    tmp_path, monkeypatch, *, arm: str, recovery_error: bool = False
):
    database = tmp_path / "fixture.duckdb"
    seed_database(str(database))
    capture = tmp_path / "fixture-final-r3.jsonl"
    records = [
        {"record_type": "manifest", "dataset": "fixture", "models": ["stub"], "runs": 3, "schema_version": 2}
    ]
    for run in (1, 2, 3):
        record = _captured_metric_record(run)
        if arm == "governed":
            record["governed_rows"] = [{"revenue": 1185.0}] * 50
            record["governed_row_count"] = 51
        else:
            record["ungoverned"]["rows"] = [{"revenue": 1185.0}] * 50
            record["ungoverned"]["row_count"] = 51
        records.append(record)
    capture.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        "evals.offline_scoring._golden_case_ids_at_revision", lambda *_args: ["case-1"]
    )
    kwargs = {}
    if recovery_error:
        def fail_recovery(*_args):
            raise RuntimeError("replay unavailable")

        kwargs["raw_rows_recoverer"] = fail_recovery
    report = score_capture_files([capture], db_path=database, **kwargs)
    monkeypatch.setattr(
        card_renderer,
        "_dataset_tree_at_revision",
        lambda *_args: report["provenance"]["dataset_identity"]["tree"],
    )
    monkeypatch.setattr(card_renderer, "_expected_case_ids_at_revision", lambda *_args: ["case-1"])
    return capture, report


def _with_provenance(review: dict, capture) -> dict:
    review["provenance"] = {
        "capture_filename": capture.name,
        "capture_sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
        "collection_commit": None,
        "scoring_commit": "score123",
        "dataset_identity": {"name": "fixture", "path": "datasets/fixture", "tree": "tree"},
        "expected_case_ids": ["case-1"],
        "case_run_inventory": {
            "expected_runs": [1, 2, 3],
            "expected_models": ["stub:latest"],
            "case_ids": ["case-1"],
            "models": {"stub:latest": {"case-1": [1, 2, 3]}},
        },
    }
    return review


def test_render_card_formats_rate_denominators_and_fixture_low_n_caveat(tmp_path):
    capture = tmp_path / "fixture-final-r3.jsonl"
    _write_capture(capture)

    rendered = render_card(
        _with_provenance(_review(), capture),
        capture_path=capture,
        review_path=tmp_path / "fixture-final-r3-review.json",
        rendered_at_commit="render123",
    )

    assert "| stub | 100.0% (3/3)" in rendered
    assert "NA (0/0)" in rendered
    assert "Applicable denominators range from 3 to 30" in rendered
    assert "scoring commit: `score123`" in rendered
    assert "rendered at commit: `render123`" in rendered
    assert "fixture-final-r3-review.json" in rendered
    assert "--recover-raw --recover-governed" in rendered
    assert "Cube must be running for governed recovery" in rendered
    assert "publication gate: unscorable governed=0, raw=0; recovery errors governed=0, raw=0" in rendered


def test_capture_report_renderer_rejects_unscorable_outcomes(tmp_path, monkeypatch):
    capture, report = _score_capture_for_publication_gate(
        tmp_path, monkeypatch, arm="governed"
    )

    assert report["models"]["stub"]["valid"] is False
    assert report["publication"]["unscorable_counts"] == {"governed": 3, "ungoverned": 0}
    with pytest.raises(ValueError, match=r"unscorable outcomes \(governed=3, raw=0\)"):
        render_card(
            report,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )


def test_capture_report_renderer_rejects_raw_recovery_errors(tmp_path, monkeypatch):
    capture, report = _score_capture_for_publication_gate(
        tmp_path, monkeypatch, arm="raw", recovery_error=True
    )

    assert report["models"]["stub"]["valid"] is False
    assert report["publication"]["recovery_error_counts"] == {"governed": 0, "ungoverned": 3}
    with pytest.raises(ValueError, match=r"recovery errors \(governed=0, raw=3\)"):
        render_card(
            report,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )


def test_render_card_refuses_a_failed_evaluator_gate(tmp_path):
    review = _review()
    review["evaluator_self_test"]["passed"] = False
    capture = tmp_path / "fixture-final-r3.jsonl"
    _write_capture(capture)

    with pytest.raises(ValueError, match="passing evaluator self-test"):
        render_card(
            review,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )


def test_render_card_rejects_capture_hash_mismatch(tmp_path):
    capture = tmp_path / "fixture-final-r3.jsonl"
    _write_capture(capture)
    review = _with_provenance(_review(), capture)
    capture.write_text(capture.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        render_card(
            review,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )


def test_render_card_rejects_incomplete_runs_and_invalid_models(tmp_path):
    capture = tmp_path / "fixture-final-r3.jsonl"
    _write_capture(capture, runs=(1, 3))
    review = _with_provenance(_review(), capture)
    review["provenance"]["capture_sha256"] = hashlib.sha256(capture.read_bytes()).hexdigest()
    review["provenance"]["case_run_inventory"]["models"]["stub:latest"]["case-1"] = [1, 3]
    review["models"]["stub:latest"]["samples"] = [
        {"case_id": "case-1", "run": 1},
        {"case_id": "case-1", "run": 3},
    ]

    with pytest.raises(ValueError, match="Incomplete runs"):
        render_card(
            review,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )


def test_render_card_rejects_invalid_model(tmp_path):
    capture = tmp_path / "fixture-final-r3.jsonl"
    _write_capture(capture)
    review = _with_provenance(_review(), capture)
    review["models"]["stub:latest"]["valid"] = False

    with pytest.raises(ValueError, match="invalid model"):
        render_card(
            review,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )


def test_render_card_rejects_missing_expected_case(tmp_path, monkeypatch):
    capture = tmp_path / "fixture-final-r3.jsonl"
    _write_capture(capture)
    review = _with_provenance(_review(), capture)
    review["provenance"]["expected_case_ids"] = ["case-1", "case-2"]
    monkeypatch.setattr(
        card_renderer, "_expected_case_ids_at_revision", lambda *_args: ["case-1", "case-2"]
    )

    with pytest.raises(ValueError, match="missing an expected case"):
        render_card(
            review,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )


def test_render_card_rejects_sample_inventory_mismatch(tmp_path):
    capture = tmp_path / "fixture-final-r3.jsonl"
    _write_capture(capture)
    review = _with_provenance(_review(), capture)
    review["models"]["stub:latest"]["samples"].pop()

    with pytest.raises(ValueError, match="samples do not reconcile"):
        render_card(
            review,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )


def test_render_card_rejects_dataset_identity_mismatch(tmp_path):
    capture = tmp_path / "fixture-final-r3.jsonl"
    _write_capture(capture)
    review = _with_provenance(_review(), capture)
    review["provenance"]["dataset_identity"]["tree"] = "different-tree"

    with pytest.raises(ValueError, match="dataset tree"):
        render_card(
            review,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )


def test_render_card_rejects_rate_arithmetic_mismatch(tmp_path):
    capture = tmp_path / "fixture-final-r3.jsonl"
    _write_capture(capture)
    review = _with_provenance(_review(), capture)
    review["models"]["stub:latest"]["groups"]["in_catalog"]["governed"][
        "wrong_answer_rate"
    ]["rate"] = 0.5

    with pytest.raises(ValueError, match="Rate does not equal"):
        render_card(
            review,
            capture_path=capture,
            review_path=tmp_path / "fixture-final-r3-review.json",
            rendered_at_commit="render123",
        )

def test_render_all_requires_authoritative_review_files(tmp_path):
    scores = tmp_path / "scores"
    captures = tmp_path / "captures"
    scores.mkdir()
    captures.mkdir()
    (scores / "aw-final-r3-review.json").write_text(
        json.dumps(_review()), encoding="utf-8"
    )

    with pytest.raises(FileNotFoundError):
        render_all(
            scores_dir=scores,
            captures_dir=captures,
            results_dir=tmp_path / "results",
        )
