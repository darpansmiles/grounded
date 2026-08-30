from __future__ import annotations

from types import SimpleNamespace

from datasets.tpch.source import generate_and_load


def test_tpch_compose_initializes_its_own_database(monkeypatch):
    calls: list[tuple[list[str], dict[str, str]]] = []

    def run(command: list[str], *, check: bool, env: dict[str, str]):
        assert check
        calls.append((command, env))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(generate_and_load.subprocess, "run", run)

    generate_and_load._compose("up", "-d", "postgres")

    command, environment = calls[0]
    assert command[-3:] == ["up", "-d", "postgres"]
    assert environment["GROUNDED_SOURCE_DATABASE"] == "tpch"
    assert environment["GROUNDED_SOURCE_USERNAME"] == "grounded"
