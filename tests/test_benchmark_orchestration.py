from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from evals.benchmark import run_benchmark
from evals.merge_cards import merge_model_cards
from evals.orchestration import SourceUnavailable, _run_dataset, dataset_names, run_benchmark_queue
from scripts.spine_all import SourceUnavailable as SpineSourceUnavailable
from scripts.spine_all import _run_dataset as run_spine_dataset
from scripts.spine_all import run_spine_queue
from scripts.check_source_secret import source_dsn_is_configured
from scripts.lakehouse import available_pack_databases
from scripts.set_secret import SECRET_NAME, SOURCE_SECRET_NAMES, write_source_dsn, write_source_dsns

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PACKAGES = {
    "agent*",
    "audit*",
    "datasets*",
    "evals*",
    "governed*",
    "harness*",
    "infra*",
    "models*",
    "ontology*",
    "packlib*",
    "policy*",
    "rag*",
    "resolver*",
    "semantics*",
    "verify*",
}

_REVENUE_PLAN = {
    "tool": "query_metric",
    "args": {"metric": "revenue", "dimensions": ["category"], "filters": {}},
}


class ConcurrentProvider:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def complete(self, _system: str, user: str, temperature: float = 0.0) -> str:
        del temperature
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.02)
        with self._lock:
            self.active -= 1
        return json.dumps(_REVENUE_PLAN if "Revenue" in user else {"tool": "refuse", "args": {}})


def _golden(tmp_path):
    path = tmp_path / "golden.yml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "case_id": "revenue",
                    "question": "Revenue by category",
                    "role": "viewer",
                    "expected_plan": _REVENUE_PLAN,
                    "expect": {"type": "metric"},
                },
                {
                    "case_id": "refuse",
                    "question": "Forecast revenue",
                    "role": "viewer",
                    "expected_plan": {"tool": "refuse", "args": {}},
                    "expect": {"type": "refuse"},
                },
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_within_model_concurrency_preserves_scorecard_aggregation(tmp_path):
    golden = _golden(tmp_path)
    serial = run_benchmark(
        ["stub"],
        runs=1,
        golden=golden,
        provider_factory=lambda _model: ConcurrentProvider(),
        output_path=tmp_path / "serial.json",
        concurrency=1,
    )
    provider = ConcurrentProvider()
    concurrent = run_benchmark(
        ["stub"],
        runs=1,
        golden=golden,
        provider_factory=lambda _model: provider,
        output_path=tmp_path / "concurrent.json",
        concurrency=2,
    )

    assert provider.max_active == 2
    for metric in (
        "routing_accuracy",
        "appropriate_refusal_rate",
        "over_refusal_rate",
        "schema_compliance_rate",
    ):
        assert concurrent["scorecards"]["stub"]["scorecard"][metric] == serial["scorecards"]["stub"]["scorecard"][metric]
    assert [sample["case_id"] for sample in concurrent["scorecards"]["stub"]["per_run"][0]["samples"]] == ["revenue", "refuse"]


def _card(model: str, started: str, ended: str, duration: float) -> dict:
    return {
        "dataset": "adventureworks",
        "models": [model],
        "runs": 3,
        "category_counts": {},
        "model_cards": {model: {"status": "completed"}},
        "timing": {"started_at": started, "ended_at": ended, "total_duration_s": duration},
    }


def test_merge_preserves_partial_timing_and_rejects_overlap():
    merged = merge_model_cards(
        [
            _card("small", "2026-08-19T10:00:00+00:00", "2026-08-19T10:10:00+00:00", 600),
            _card("heavy", "2026-08-19T11:00:00+00:00", "2026-08-19T11:30:00+00:00", 1800),
        ]
    )

    assert merged["models"] == ["small", "heavy"]
    assert merged["timing"]["total_duration_s"] == 2400.0
    assert len(merged["timing"]["partial_runs"]) == 2
    try:
        merge_model_cards([_card("small", "a", "b", 1), _card("small", "c", "d", 1)])
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("overlapping partial cards must fail")


def test_benchmark_queue_continues_after_failure_and_resumes(tmp_path):
    first_card = tmp_path / "first.json"
    first_card.write_text("{}", encoding="utf-8")
    calls: list[str] = []

    def run_dataset(dataset: str) -> list[str]:
        calls.append(dataset)
        if dataset == "bad":
            raise RuntimeError("missing source")
        return [str(first_card)]

    summary_path = tmp_path / "summary.json"
    first = run_benchmark_queue(["good", "bad"], run_dataset, summary_path)
    resumed = run_benchmark_queue(["good", "bad"], run_dataset, summary_path)

    assert first["datasets"]["bad"]["status"] == "failed"
    assert resumed["datasets"]["good"]["status"] == "resumed"
    assert calls == ["good", "bad", "bad"]
    assert json.loads(summary_path.read_text(encoding="utf-8"))["datasets"] == resumed["datasets"]


def test_benchmark_queue_records_missing_third_party_source_as_skipped(tmp_path):
    summary = run_benchmark_queue(
        ["external"],
        lambda _dataset: (_ for _ in ()).throw(
            SourceUnavailable(
                "external: skipped — source not present; see datasets/external/source/README.md"
            )
        ),
        tmp_path / "summary.json",
    )

    assert summary["datasets"]["external"] == {
        "status": "skipped",
        "reason": "external: skipped — source not present; see datasets/external/source/README.md",
        "cards": [],
    }


def test_cube_pack_is_reconfigured_before_its_queued_benchmark(monkeypatch, tmp_path):
    """Each Cube-backed pack gets its own semantic service before benchmark queries."""
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[list[str], bool]] = []

    def run(command: list[str], *, check: bool):
        calls.append((command, check))
        if command[0] == "make":
            return SimpleNamespace(returncode=0)
        card = tmp_path / "evals" / "results" / "benchmark-cube-pack-stub.json"
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "evals.orchestration.load_pack",
        lambda _dataset: SimpleNamespace(
            source=SimpleNamespace(type="postgres"),
            semantics=SimpleNamespace(backend="cube"),
        ),
    )
    monkeypatch.setattr("evals.orchestration.subprocess.run", run)

    cards = _run_dataset("cube-pack")

    assert calls == [
        (["make", "source-up", "DATASET=cube-pack"], True),
        (["make", "cube-up", "DATASET=cube-pack"], True),
        (["make", "preflight-benchmark", "DATASET=cube-pack"], True),
        ([sys.executable, "-m", "evals.compare", "--dataset", "cube-pack"], False),
        (["make", "down", "DATASET=cube-pack"], False),
    ]
    assert cards == ["evals/results/benchmark-cube-pack-stub.json"]


def test_failed_dataset_benchmark_still_tears_down_its_compose_project(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[list[str], bool]] = []

    def run(command: list[str], *, check: bool):
        calls.append((command, check))
        if command[0] == sys.executable:
            return SimpleNamespace(returncode=1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "evals.orchestration.load_pack",
        lambda _dataset: SimpleNamespace(
            source=SimpleNamespace(type="postgres"),
            semantics=SimpleNamespace(backend="cube"),
        ),
    )
    monkeypatch.setattr("evals.orchestration.subprocess.run", run)

    with pytest.raises(RuntimeError, match="benchmark command exited 1"):
        _run_dataset("failed-pack")

    assert calls[-1] == (["make", "down", "DATASET=failed-pack"], False)


def test_spine_queue_tears_down_each_postgres_pack_before_the_next(monkeypatch):
    """The next Postgres pack cannot inherit a source port from the previous one."""
    calls: list[tuple[list[str], bool]] = []

    def run(command: list[str], *, check: bool):
        calls.append((command, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "scripts.spine_all.load_pack",
        lambda _dataset: SimpleNamespace(source=SimpleNamespace(path=None)),
    )
    monkeypatch.setattr("scripts.spine_all.subprocess.run", run)

    assert run_spine_queue(["first-postgres", "second-postgres"], run_spine_dataset) == [
        "first-postgres",
        "second-postgres",
    ]
    assert calls == [
        (["make", "spine", "DATASET=first-postgres"], True),
        (["make", "down", "DATASET=first-postgres"], False),
        (["make", "spine", "DATASET=second-postgres"], True),
        (["make", "down", "DATASET=second-postgres"], False),
    ]


def test_spine_queue_skips_missing_third_party_source_with_status(capsys):
    def unavailable(_dataset: str) -> None:
        raise SpineSourceUnavailable(
            "external: skipped — source not present; see datasets/external/source/README.md"
        )

    assert run_spine_queue(["external"], unavailable) == []
    assert "external: skipped — source not present" in capsys.readouterr().out


def test_failed_spine_still_tears_down_its_compose_project(monkeypatch):
    calls: list[tuple[list[str], bool]] = []

    def run(command: list[str], *, check: bool):
        calls.append((command, check))
        if command[1] == "spine":
            raise subprocess.CalledProcessError(2, command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "scripts.spine_all.load_pack",
        lambda _dataset: SimpleNamespace(source=SimpleNamespace(path=None)),
    )
    monkeypatch.setattr("scripts.spine_all.subprocess.run", run)

    with pytest.raises(subprocess.CalledProcessError):
        run_spine_dataset("failed-pack")

    assert calls[-1] == (["make", "down", "DATASET=failed-pack"], False)


def test_makefile_names_each_data_stack_after_the_active_dataset():
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "COMPOSE_PROJECT := grounded-$(DATASET)" in makefile
    assert "docker compose -p $(COMPOSE_PROJECT) -f infra/docker-compose.yml" in makefile
    assert "$(COMPOSE) down" in makefile


def test_cube_up_stops_only_a_conflicting_port_4000_container(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "docker.log"
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/bin/sh
printf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"
case \"$1\" in
  info) exit 0 ;;
  ps) printf 'active-cube\\nstale-cube\\n' ;;
  inspect) printf '/grounded-old-cube-1\\n' ;;
  stop) exit 0 ;;
  compose)
    case \" $* \" in
      *" ps -q cube "*) printf 'active-cube\\n' ;;
      *" up -d cube "*) exit 0 ;;
    esac
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_DOCKER_LOG": str(log),
    }

    completed = subprocess.run(
        ["make", "DATASET=adventureworks", "cube-up"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Stopping conflicting Cube container grounded-old-cube-1 on host port 4000" in completed.stdout
    commands = log.read_text(encoding="utf-8")
    assert "stop stale-cube" in commands
    assert "stop active-cube" not in commands


def test_lakehouse_ignores_template_style_pack_directories(monkeypatch, tmp_path):
    (tmp_path / "_template").mkdir()
    (tmp_path / "_template" / "pack.yml").write_text("name: template", encoding="utf-8")
    live = tmp_path / "live"
    live.mkdir()
    (live / "pack.yml").write_text("name: live", encoding="utf-8")
    database = tmp_path / "live.duckdb"
    database.touch()
    calls: list[str] = []

    monkeypatch.setattr("scripts.lakehouse.PACKS_DIRECTORY", tmp_path)
    monkeypatch.setattr(
        "scripts.lakehouse.load_pack",
        lambda name: calls.append(name) or SimpleNamespace(
            namespace=name, destination=SimpleNamespace(path=database)
        ),
    )

    assert available_pack_databases()[0].alias == "live"
    assert calls == ["live"]


def test_source_secret_writer_preserves_other_entries(tmp_path):
    path = tmp_path / "secrets.toml"
    path.write_text('OTHER_SECRET = "kept"\n', encoding="utf-8")

    write_source_dsn("postgresql://local", path)
    write_source_dsn("postgresql://updated", path)

    contents = path.read_text(encoding="utf-8")
    assert 'OTHER_SECRET = "kept"' in contents
    assert contents.count(SECRET_NAME) == 1
    assert 'postgresql://updated' in contents
    assert set(dataset_names()) >= {"adventureworks", "fixture", "tpch", "spider_world1", "bird_ca_schools"}


def test_source_secret_writer_populates_every_declared_postgres_dsn(tmp_path):
    path = tmp_path / "secrets.toml"
    values = {name: f"postgresql://local/{index}" for index, name in enumerate(SOURCE_SECRET_NAMES)}

    write_source_dsns(values, path)

    contents = path.read_text(encoding="utf-8")
    for name, value in values.items():
        assert contents.count(name) == 1
        assert value in contents


def test_postgres_source_preflight_accepts_environment_without_printing_value(monkeypatch):
    monkeypatch.setattr("scripts.check_source_secret.dlt.secrets.get", lambda _key: None)
    monkeypatch.delenv(SECRET_NAME, raising=False)
    assert not source_dsn_is_configured("adventureworks")

    monkeypatch.setenv(SECRET_NAME, "postgresql://local")
    assert source_dsn_is_configured("adventureworks")


def test_project_packages_are_discoverable_after_editable_install():
    """Keep the editable-install package list aligned with every import boundary."""
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    discovery = pyproject["tool"]["setuptools"]["packages"]["find"]

    assert PROJECT_PACKAGES <= set(discovery["include"])


def test_make_and_direct_scripts_do_not_depend_on_ambient_import_paths():
    """Make exports the root globally and all executable scripts add it themselves."""
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "export PYTHONPATH := $(ROOT)" in makefile

    for script in sorted((PROJECT_ROOT / "scripts").glob("*.py")):
        source = script.read_text(encoding="utf-8")
        assert "Path(__file__).resolve().parents[1]" in source, script.name
        assert "sys.path.insert(0," in source, script.name
