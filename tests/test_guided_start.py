"""Fast, isolated coverage for the first guided-quickstart slice."""

from __future__ import annotations

from types import SimpleNamespace

from governed.cli import finale, model_pick, stages, start, tour
from scripts.set_secret import (
    LOCAL_SOURCE_DSNS,
    SECRET_NAME,
    TPCH_SECRET_NAME,
    ensure_local_source_dsns,
    local_source_dsns,
)


def _result(returncode: int = 0, stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout)


def _stage_ok(*_args, **_kwargs) -> int:
    return 0


def test_doctor_reports_exact_docker_and_ollama_fixes(monkeypatch):
    monkeypatch.setattr(start, "_editable_install_present", lambda: True)

    checks = start.doctor_checks(
        needs_docker=True,
        runner=lambda *_args, **_kwargs: _result(1),
        which=lambda _name: None,
    )
    lines: list[str] = []

    assert not start.render_doctor(checks, lines.append)
    report = "\n".join(lines)
    assert "Docker Desktop" in report
    assert "Install and start Docker Desktop, then retry." in report
    assert "Install Ollama from https://ollama.com, then retry." in report


def test_base_doctor_defers_docker_until_a_docker_pack_is_selected(monkeypatch):
    monkeypatch.setattr(start, "_editable_install_present", lambda: True)

    checks = start.doctor_checks(
        runner=lambda *_args, **_kwargs: _result(1),
        which=lambda _name: "/usr/local/bin/ollama",
    )

    docker = next(check for check in checks if check.label == "Docker Desktop")
    assert not docker.passed
    assert not docker.blocks_tour


def test_local_secrets_fill_defaults_without_overwriting_existing_values(tmp_path):
    path = tmp_path / "secrets.toml"
    path.write_text(f'{SECRET_NAME} = "postgresql://custom/source"\n', encoding="utf-8")

    ensure_local_source_dsns(path)

    contents = path.read_text(encoding="utf-8")
    assert 'postgresql://custom/source' in contents
    assert f'{TPCH_SECRET_NAME} = "{LOCAL_SOURCE_DSNS[TPCH_SECRET_NAME]}"' in contents


def test_local_secrets_follow_an_alternate_source_port(tmp_path):
    path = tmp_path / "secrets.toml"

    ensure_local_source_dsns(path, source_host_port=5434)

    assert local_source_dsns(5434)[SECRET_NAME] in path.read_text(encoding="utf-8")


def test_alternate_source_port_uses_a_temporary_dsn_without_overwriting_user_choice(monkeypatch):
    monkeypatch.delenv(SECRET_NAME, raising=False)
    monkeypatch.setenv(TPCH_SECRET_NAME, "postgresql://custom/tpch")

    start.apply_selected_source_port(5434)

    assert start.os.environ[SECRET_NAME] == local_source_dsns(5434)[SECRET_NAME]
    assert start.os.environ[TPCH_SECRET_NAME] == "postgresql://custom/tpch"


def test_port_collision_can_use_the_next_available_port(monkeypatch):
    monkeypatch.setenv("CUBE_HOST_PORT", "4000")
    monkeypatch.setattr(start, "PORTS", (start.Port("Cube", "CUBE_HOST_PORT", 4000),))
    messages: list[str] = []

    handled = start.resolve_port_collisions(
        input_func=lambda _prompt: "a",
        output=messages.append,
        runner=lambda *_args, **_kwargs: _result(0, ""),
        port_available=lambda port: port != 4000,
    )

    assert handled
    assert start.os.environ["CUBE_HOST_PORT"] == "4001"
    assert "CUBE_HOST_PORT=4001 make start" in "\n".join(messages)


def test_start_writes_secrets_only_after_the_doctor_passes(monkeypatch, tmp_path):
    monkeypatch.setattr(start, "_editable_install_present", lambda: True)
    messages: list[str] = []

    status = start.run_start(
        output=messages.append,
        input_func=lambda _prompt: "",
        runner=lambda *_args, **_kwargs: _result(0, ""),
        which=lambda _name: "/usr/local/bin/ollama",
        port_available=lambda _port: True,
        secrets_path=tmp_path / "secrets.toml",
    )

    assert status == 0
    assert (tmp_path / "secrets.toml").is_file()
    assert "secret values were not printed" in "\n".join(messages)


def test_doctor_warns_below_five_gib_and_fails_below_one_gib(monkeypatch, tmp_path):
    monkeypatch.setattr(start, "_editable_install_present", lambda: True)
    disk = lambda _path: SimpleNamespace(free=4 * start.GIB)

    checks = start.doctor_checks(
        runner=lambda *_args, **_kwargs: _result(0),
        which=lambda _name: "/usr/local/bin/ollama",
        disk_usage=disk,
        project_root=tmp_path,
    )
    disk_check = next(check for check in checks if check.label == "Free disk")
    assert disk_check.passed
    assert disk_check.warning

    near_empty = start.doctor_checks(
        runner=lambda *_args, **_kwargs: _result(0),
        which=lambda _name: "/usr/local/bin/ollama",
        disk_usage=lambda _path: SimpleNamespace(free=start.GIB - 1),
        project_root=tmp_path,
    )
    assert not next(check for check in near_empty if check.label == "Free disk").passed


def test_menu_keeps_all_five_packs_and_marks_missing_external_sources(tmp_path):
    missing_pack = SimpleNamespace(root=tmp_path, source=SimpleNamespace(path=tmp_path / "missing.sqlite"))
    messages: list[str] = []

    tour.render_dataset_menu(
        output=messages.append,
        pack_loader=lambda _name: missing_pack,
        source_available=lambda _pack: False,
    )

    menu = "\n".join(messages)
    assert "AdventureWorks" in menu
    assert "TPC-H" in menu
    assert "Spider world_1" in menu
    assert "BIRD california_schools" in menu
    assert "Fixture" in menu
    assert menu.count("source download needed") == 2


def test_bring_up_and_teardown_use_only_declared_services():
    calls: list[list[str]] = []
    runner = lambda command, **_kwargs: calls.append(command) or _result()

    assert tour.bring_up(tour.TOUR_PACKS[0], runner=runner, port_resolver=lambda **_kwargs: True)
    tour.teardown(tour.TOUR_PACKS[0], runner=runner)
    assert calls == [
        ["make", "source-up", "DATASET=adventureworks"],
        ["make", "cube-up", "DATASET=adventureworks"],
        ["make", "down", "DATASET=adventureworks"],
    ]

    calls.clear()
    assert tour.bring_up(tour.TOUR_PACKS[1], runner=runner, port_resolver=lambda **_kwargs: True)
    tour.teardown(tour.TOUR_PACKS[1], runner=runner)
    assert calls == [
        ["make", "source-up", "DATASET=tpch"],
        ["make", "cube-up", "DATASET=tpch"],
        ["make", "down", "DATASET=tpch"],
    ]

    calls.clear()
    assert tour.bring_up(tour.TOUR_PACKS[2], runner=runner, port_resolver=lambda **_kwargs: True)
    tour.teardown(tour.TOUR_PACKS[2], runner=runner)
    assert calls == [
        ["make", "cube-up", "DATASET=spider_world1"],
        ["make", "down", "DATASET=spider_world1"],
    ]

    calls.clear()
    assert tour.bring_up(tour.TOUR_PACKS[3], runner=runner, port_resolver=lambda **_kwargs: True)
    tour.teardown(tour.TOUR_PACKS[3], runner=runner)
    assert calls == [
        ["make", "cube-up", "DATASET=bird_ca_schools"],
        ["make", "down", "DATASET=bird_ca_schools"],
    ]

    calls.clear()
    assert tour.bring_up(tour.TOUR_PACKS[4], runner=runner)
    tour.teardown(tour.TOUR_PACKS[4], runner=runner)
    assert calls == []


def test_missing_source_decline_returns_to_menu_without_starting_cube(tmp_path):
    pack = SimpleNamespace(root=tmp_path, source=SimpleNamespace(path=tmp_path / "world_1.sqlite"))
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "README.md").write_text("manual instructions", encoding="utf-8")
    responses = iter(["3", "n", "q"])
    calls: list[list[str]] = []
    messages: list[str] = []

    status = tour.run_dataset_step(
        input_func=lambda _prompt: next(responses),
        output=messages.append,
        runner=lambda command, **_kwargs: calls.append(command) or _result(),
        pack_loader=lambda _name: pack,
        source_available=lambda _pack: False,
    )

    assert status == 0
    assert calls == []
    report = "\n".join(messages)
    assert "make fetch-source DATASET=spider_world1" in report
    assert "Returning to the dataset menu." in report


def test_missing_source_fetches_with_consent_then_brings_up_and_tears_down(tmp_path):
    pack = SimpleNamespace(root=tmp_path, source=SimpleNamespace(path=tmp_path / "world_1.sqlite"))
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "README.md").write_text("manual instructions", encoding="utf-8")
    fetched = False
    calls: list[list[str]] = []
    responses = iter(["3", "y", ""])

    def runner(command, **_kwargs):
        nonlocal fetched
        calls.append(command)
        if command[1] == "fetch-source":
            fetched = True
        return _result()

    status = tour.run_dataset_step(
        input_func=lambda _prompt: next(responses),
        runner=runner,
        pack_loader=lambda _name: pack,
        source_available=lambda _pack: fetched,
        stage_walk=_stage_ok,
        model_pick=lambda **_kwargs: None,
        port_resolver=lambda **_kwargs: True,
    )

    assert status == 0
    assert calls == [
        ["make", "fetch-source", "DATASET=spider_world1"],
        ["docker", "info"],
        ["make", "cube-up", "DATASET=spider_world1"],
        ["make", "down", "DATASET=spider_world1"],
    ]


def test_full_tour_runs_existing_targets_and_shows_declared_artifacts():
    calls: list[list[str]] = []
    messages: list[str] = []
    responses = iter(["", "", "", "", "n", "", ""])

    status = stages.run_stage_walk(
        "adventureworks",
        input_func=lambda _prompt: next(responses),
        output=messages.append,
        runner=lambda command, **_kwargs: calls.append(command) or _result(),
    )

    assert status == 0
    assert calls == [
        ["make", "source-load", "DATASET=adventureworks"],
        ["make", "ingest", "DATASET=adventureworks"],
        ["make", "bronze-verify", "DATASET=adventureworks"],
        ["make", "transform", "DATASET=adventureworks"],
    ]
    report = "\n".join(messages)
    assert "bronze.salesorderdetail" in report
    assert "gold.fct_sales" in report
    assert "Average Order Value = revenue / orders" in report
    assert "Marquez was not started" in report
    assert "customers.email | viewer | mask" in report


def test_quick_run_labels_skips_honestly_and_fixture_needs_no_docker():
    calls: list[list[str]] = []
    spider_messages: list[str] = []

    assert stages.run_stage_walk(
        "spider_world1",
        input_func=lambda _prompt: "",
        output=spider_messages.append,
        runner=lambda command, **_kwargs: calls.append(command) or _result(),
    ) == 0
    assert calls == []
    spider_report = "\n".join(spider_messages)
    assert "ready-to-use SQLite pack" in spider_report
    assert "Skipped: data movement and transformation" in spider_report
    assert "Marquez lineage is skipped" in spider_report

    fixture_messages: list[str] = []
    assert stages.run_stage_walk(
        "fixture",
        input_func=lambda _prompt: "",
        output=fixture_messages.append,
        runner=lambda *_args, **_kwargs: _result(),
    ) == 0
    fixture_report = "\n".join(fixture_messages)
    assert "seeded in DuckDB" in fixture_report
    assert "no Docker service is needed" in fixture_report


def test_failed_source_fetch_returns_to_menu_without_starting_cube(tmp_path):
    pack = SimpleNamespace(root=tmp_path, source=SimpleNamespace(path=tmp_path / "world_1.sqlite"))
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "README.md").write_text("manual instructions", encoding="utf-8")
    responses = iter(["3", "y", "q"])
    calls: list[list[str]] = []

    status = tour.run_dataset_step(
        input_func=lambda _prompt: next(responses),
        runner=lambda command, **_kwargs: calls.append(command) or _result(1),
        pack_loader=lambda _name: pack,
        source_available=lambda _pack: False,
    )

    assert status == 0
    assert calls == [["make", "fetch-source", "DATASET=spider_world1"]]


def test_docker_pack_capacity_blocks_before_starting_services():
    calls: list[list[str]] = []

    status = tour.run_dataset_step(
        input_func=lambda _prompt: "1",
        runner=lambda command, **_kwargs: calls.append(command) or _result(),
        disk_usage=lambda _path: SimpleNamespace(free=4 * tour.GIB),
    )

    assert status == 2
    assert calls == []


def test_landing_splash_and_plain_style_are_capture_safe(monkeypatch, tmp_path):
    monkeypatch.setattr(start, "_editable_install_present", lambda: True)
    messages: list[str] = []

    start.run_start(
        input_func=lambda _prompt: "q",
        output=messages.append,
        runner=lambda *_args, **_kwargs: _result(),
        which=lambda _name: "/usr/local/bin/ollama",
        port_available=lambda _port: True,
        secrets_path=tmp_path / "secrets.toml",
    )

    report = "\n".join(messages)
    assert "GROUNDED" in report
    assert "https://intelligenceisasystem.substack.com" in report
    assert "https://github.com/darpansmiles/grounded" in report
    assert "https://www.linkedin.com/in/darpan-vyas/" in report
    assert "\x1b" not in report


def test_model_picker_uses_installed_model():
    messages: list[str] = []

    selected = model_pick.choose_model(
        input_func=lambda _prompt: "1",
        output=messages.append,
        runner=lambda *_args, **_kwargs: _result(0, "NAME ID SIZE\nlocal-model latest 1GB\n"),
    )

    assert selected == "local-model"
    assert "recommended default" in "\n".join(messages)


def test_payoff_and_optional_proof_run_before_fixture_completion(monkeypatch):
    order: list[str] = []
    monkeypatch.setattr(tour, "teardown", lambda *_args, **_kwargs: order.append("teardown"))

    status = tour.run_dataset_step(
        input_func=lambda _prompt: "5",
        output=lambda _line: None,
        runner=lambda *_args, **_kwargs: _result(),
        stage_walk=lambda *_args, **_kwargs: order.append("stages") or 0,
        model_pick=lambda **_kwargs: order.append("model") or "local-model",
        finale=lambda *_args, **_kwargs: order.append("finale") or 0,
        benchmark=lambda *_args, **_kwargs: order.append("benchmark") or 0,
    )

    assert status == 0
    assert order == ["stages", "model", "finale", "benchmark", "teardown"]


def test_fixture_finale_explains_its_minimal_lineage_capability():
    messages: list[str] = []

    assert (
        finale.run_interactive_finale(
            "fixture",
            "local-model",
            input_func=lambda _prompt: "q",
            output=messages.append,
            provider_factory=lambda _model: object(),
        )
        == 0
    )

    assert any("Fixture runs Docker-free" in message for message in messages)


def test_governed_receipt_displays_a_not_applicable_check():
    messages: list[str] = []

    finale._show_governed(
        {
            "answer_rows": [{"revenue": 1.0}],
            "metric_definition": {"measure": "sum(revenue)"},
            "policy_applied": [],
            "verify_status": "pass",
            "verification": [
                {
                    "type": "not_null",
                    "field": "category",
                    "status": "n/a",
                    "detail": "field not in result",
                }
            ],
            "lineage_citation": None,
        },
        output=messages.append,
    )

    assert "not_null:category — n/a · field not in result" in "\n".join(messages)
