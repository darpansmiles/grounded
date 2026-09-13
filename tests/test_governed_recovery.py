from __future__ import annotations

from evals import governed_recovery


def test_recovery_detects_only_a_legacy_truncated_executed_plan():
    record = {
        "_capture_manifest": {"schema_version": 2},
        "governed_rows": [{"revenue": 1}],
        "governed_row_count": 51,
        "governed_executed": True,
        "produced_plan": {"tool": "query_metric", "args": {}},
    }

    assert governed_recovery.needs_governed_row_recovery(record)
    assert not governed_recovery.needs_governed_row_recovery(
        {**record, "governed_row_count": 1}
    )
    assert not governed_recovery.needs_governed_row_recovery(
        {**record, "produced_plan": {"tool": "refuse", "args": {}}}
    )


def test_recoverer_uses_the_stored_plan_role_and_active_pack(monkeypatch, tmp_path):
    captured: dict = {}

    class Pack:
        semantics = type("Semantics", (), {"backend": "cube"})()
        destination = type("Destination", (), {"path": tmp_path / "pack.duckdb"})()

    monkeypatch.setattr(governed_recovery, "load_pack", lambda _dataset: Pack())
    monkeypatch.setenv("GROUNDED_PACK", "previous")

    def execute(plan, role, **kwargs):
        captured.update(
            plan=plan,
            role=role,
            kwargs=kwargs,
            active_pack=governed_recovery.os.environ["GROUNDED_PACK"],
        )
        return {"answer_rows": [{"revenue": 1.0}]}

    monkeypatch.setattr(governed_recovery, "_execute_tool_call", execute)

    rows = governed_recovery.make_governed_rows_recoverer(
        cube_url="http://cube.test"
    )(
        {
            "produced_plan": {
                "tool": "query_metric",
                "args": {"metric": "revenue"},
            },
            "role": "eu_analyst",
        },
        "bird_ca_schools",
        tmp_path / "truth.duckdb",
    )

    assert rows == [{"revenue": 1.0}]
    assert captured == {
        "plan": {"tool": "query_metric", "args": {"metric": "revenue"}},
        "role": "eu_analyst",
        "kwargs": {
            "backend": "cube",
            "cube_url": "http://cube.test",
            "db_path": str(tmp_path / "truth.duckdb"),
        },
        "active_pack": "bird_ca_schools",
    }
    assert governed_recovery.os.environ["GROUNDED_PACK"] == "previous"
