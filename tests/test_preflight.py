from __future__ import annotations

from types import SimpleNamespace

import pytest

from governed.service import governed_query
from scripts import preflight


def _result(returncode: int, stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout)


def test_spine_preflight_lists_docker_and_dsn_remedies(monkeypatch, capsys, tmp_path):
    pack = SimpleNamespace(
        source=SimpleNamespace(type="postgres", dsn_env="GROUNDED_SOURCE_DSN"),
        destination=SimpleNamespace(path=tmp_path / "source.duckdb"),
        semantics=None,
    )
    monkeypatch.setattr("scripts.preflight.load_pack", lambda _dataset: pack)
    monkeypatch.setattr("scripts.preflight.source_dsn_is_configured", lambda _dataset: False)
    original = preflight.check_preflight
    monkeypatch.setattr(
        "scripts.preflight.check_preflight",
        lambda dataset, run: original(
            dataset, run, command_runner=lambda *_args, **_kwargs: _result(1)
        ),
    )

    assert preflight.run_preflight("source", "spine") == 2

    captured = capsys.readouterr()
    assert "Docker Desktop is not running. Fix: start Docker Desktop" in captured.err
    assert "GROUNDED_SOURCE_DSN=... make set-secret" in captured.err
    assert "Traceback" not in captured.err


def test_benchmark_preflight_reports_database_cube_and_model_remedies(monkeypatch, tmp_path):
    pack = SimpleNamespace(
        source=SimpleNamespace(type="duckdb_seed", dsn_env=None),
        destination=SimpleNamespace(path=tmp_path / "missing.duckdb"),
        semantics=SimpleNamespace(backend="cube", cube=tmp_path),
    )
    monkeypatch.setattr("scripts.preflight.load_pack", lambda _dataset: pack)
    monkeypatch.setattr("scripts.preflight._cube_is_pointed_at_pack", lambda *_args: False)

    issues = preflight.check_preflight(
        "cube-pack",
        "benchmark",
        command_runner=lambda *_args, **_kwargs: _result(1),
        models=["small"],
    )

    rendered = [issue.render() for issue in issues]
    assert any("make spine DATASET=cube-pack" in issue for issue in rendered)
    assert any("make cube-up DATASET=cube-pack" in issue for issue in rendered)
    assert any("ollama pull small" in issue for issue in rendered)


def test_cube_metadata_must_match_the_active_pack(tmp_path):
    model_directory = tmp_path / "model"
    model_directory.mkdir()
    (model_directory / "sales.yml").write_text("cubes:\n  - name: Sales\n", encoding="utf-8")
    pack = SimpleNamespace(semantics=SimpleNamespace(cube=tmp_path))

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    responses = iter([Response({}), Response({"cubes": [{"name": "Other"}]})])
    assert not preflight._cube_is_pointed_at_pack(
        pack, lambda *_args, **_kwargs: next(responses), attempts=1
    )


def test_cube_readiness_retries_while_a_newly_started_cube_warms_up(tmp_path):
    model_directory = tmp_path / "model"
    model_directory.mkdir()
    (model_directory / "sales.yml").write_text("cubes:\n  - name: Sales\n", encoding="utf-8")
    pack = SimpleNamespace(semantics=SimpleNamespace(cube=tmp_path))
    sleeps: list[float] = []

    class WarmingResponse:
        def raise_for_status(self):
            raise preflight.httpx.ConnectError("Cube warming")

    class ReadyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    responses = iter(
        [
            WarmingResponse(),
            ReadyResponse({}),
            ReadyResponse({"cubes": [{"name": "Sales"}]}),
        ]
    )

    assert preflight._cube_is_pointed_at_pack(
        pack,
        lambda *_args, **_kwargs: next(responses),
        sleep=sleeps.append,
    )
    assert sleeps == [1.0]


def test_missing_models_treats_bare_and_latest_tags_as_equivalent():
    runner = lambda *_args, **_kwargs: _result(0, "NAME ID SIZE\nphi4:latest abc\nphi3.5:latest def\n")

    assert preflight._missing_models(runner, ["phi4", "phi3.5:latest", "qwen2.5:7b"]) == [
        "qwen2.5:7b"
    ]


def test_preflight_cli_requires_a_known_run_mode():
    with pytest.raises(SystemExit):
        preflight.main(["--run", "unknown"])


def test_governed_missing_database_has_the_spine_remedy(monkeypatch, tmp_path):
    monkeypatch.setenv("GROUNDED_PACK", "fixture")

    with pytest.raises(RuntimeError, match="make spine DATASET=fixture") as error:
        governed_query("revenue", db_path=str(tmp_path / "missing.duckdb"))

    assert "Traceback" not in str(error.value)
