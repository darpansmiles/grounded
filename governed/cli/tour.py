"""Capability-aware selection, service bring-up, and cleanup for the guided tour."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from governed.cli.benchmark import offer_benchmark
from governed.cli.finale import run_interactive_finale
from governed.cli.model_pick import choose_model
from governed.cli.stages import run_stage_walk
from packlib import Pack, load_pack, source_is_available

GIB = 1024**3
DOCKER_PACK_MINIMUM_FREE_BYTES = 5 * GIB


@dataclass(frozen=True)
class TourPack:
    """The small tour-specific presentation layer over a declared pack."""

    dataset: str
    title: str
    tier: str
    requirements: str
    needs_source_service: bool
    needs_cube: bool
    external_source: bool = False

    @property
    def needs_docker(self) -> bool:
        return self.needs_source_service or self.needs_cube


TOUR_PACKS = (
    TourPack(
        "adventureworks",
        "AdventureWorks",
        "FULL TOUR",
        "PostgreSQL + Cube, Docker required",
        needs_source_service=True,
        needs_cube=True,
    ),
    TourPack(
        "tpch",
        "TPC-H",
        "FULL TOUR",
        "PostgreSQL + Cube, Docker required",
        needs_source_service=True,
        needs_cube=True,
    ),
    TourPack(
        "spider_world1",
        "Spider world_1",
        "QUICK RUN",
        "one-time source download (third-party, CC BY-SA, official pinned mirror); Cube",
        needs_source_service=False,
        needs_cube=True,
        external_source=True,
    ),
    TourPack(
        "bird_ca_schools",
        "BIRD california_schools",
        "QUICK RUN",
        "one-time source download (third-party, CC BY-SA, official pinned mirror); Cube",
        needs_source_service=False,
        needs_cube=True,
        external_source=True,
    ),
    TourPack(
        "fixture",
        "Fixture",
        "QUICK RUN",
        "seconds, no Docker",
        needs_source_service=False,
        needs_cube=False,
    ),
)

Input = Callable[[str], str]
Output = Callable[[str], None]
CommandRunner = Callable[..., Any]
PackLoader = Callable[[str], Pack]
SourceAvailable = Callable[[Pack], bool]
DiskUsage = Callable[[str | os.PathLike[str]], Any]
StageWalk = Callable[..., int]
ModelPick = Callable[..., str | None]
Finale = Callable[..., int]
Benchmark = Callable[..., int]
PortResolver = Callable[..., bool]


class SourceNotFetched(RuntimeError):
    """A selected third-party source is intentionally absent from this clone."""


def render_dataset_menu(
    *, output: Output = print, pack_loader: PackLoader = load_pack, source_available: SourceAvailable = source_is_available
) -> None:
    """Show all five packs, honestly marking any missing third-party source."""
    output("\nChoose a dataset")
    output("  Full tour: AdventureWorks or TPC-H. Quick run: Spider, BIRD, or Fixture.")
    output("  Fixture is recommended for a first look. AdventureWorks shows the full journey.\n")
    for number, option in enumerate(TOUR_PACKS, start=1):
        status = ""
        if option.external_source:
            pack = pack_loader(option.dataset)
            status = " · source ready" if source_available(pack) else " · source download needed"
        output(f"  {number}. {option.title} · {option.tier.lower()} · {option.requirements}{status}")


def choose_dataset(
    *,
    input_func: Input = input,
    output: Output = print,
    pack_loader: PackLoader = load_pack,
    source_available: SourceAvailable = source_is_available,
) -> TourPack | None:
    """Prompt until a known menu entry is selected or the user leaves the tour."""
    render_dataset_menu(output=output, pack_loader=pack_loader, source_available=source_available)
    try:
        choice = input_func("Select 1-5, or q to quit: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None
    if choice in {"q", "quit", ""}:
        return None
    try:
        return TOUR_PACKS[int(choice) - 1]
    except (ValueError, IndexError):
        output("Please enter a number from 1 to 5, or q to quit.")
        return None


def source_readme(pack: Pack) -> Path:
    """Return the documented, pack-local provenance and manual-fetch instructions."""
    return pack.root / "source" / "README.md"


def _run_make(
    target: str,
    dataset: str,
    *,
    runner: CommandRunner,
) -> bool:
    try:
        result = runner(["make", target, f"DATASET={dataset}"], check=False)
    except OSError:
        return False
    return result.returncode == 0


def ensure_external_source(
    option: TourPack,
    *,
    input_func: Input = input,
    output: Output = print,
    runner: CommandRunner = subprocess.run,
    pack_loader: PackLoader = load_pack,
    source_available: SourceAvailable = source_is_available,
) -> bool:
    """Require an explicit, verified fetch before a third-party pack can proceed."""
    if not option.external_source:
        return True
    pack = pack_loader(option.dataset)
    if source_available(pack):
        return True

    readme = source_readme(pack)
    output(
        f"\n{option.title} uses third-party data that Grounded does not redistribute. "
        "It needs one checksum-verified download from the official pinned source."
    )
    try:
        consent = input_func("Fetch it now from the official source and verify the checksum? [y/N] ")
    except (EOFError, KeyboardInterrupt):
        consent = ""
    if consent.strip().lower() not in {"y", "yes"}:
        output(f"Source not fetched. See {readme} and run `make fetch-source DATASET={option.dataset}`.")
        return False
    output(f"Fetching and verifying {option.title} source...")
    if not _run_make("fetch-source", option.dataset, runner=runner) or not source_available(pack):
        output(
            f"Source fetch did not complete or verify. See {readme} and run "
            f"`make fetch-source DATASET={option.dataset}` when the source is reachable."
        )
        return False
    output("Source checksum verified.")
    return True


def docker_capacity_ok(
    option: TourPack,
    *,
    disk_usage: DiskUsage = shutil.disk_usage,
    project_root: Path | None = None,
    output: Output = print,
) -> bool:
    """Enforce the selected Docker pack's explicit five-GiB capacity floor."""
    if not option.needs_docker:
        return True
    free_bytes = disk_usage(project_root or Path.cwd()).free
    if free_bytes >= DOCKER_PACK_MINIMUM_FREE_BYTES:
        return True
    output(
        f"{option.title} needs Docker images and local data. It requires at least 5 GiB free; "
        f"{free_bytes / GIB:.1f} GiB is available. Choose Fixture or free disk space, then retry."
    )
    return False


def docker_is_ready(*, runner: CommandRunner = subprocess.run) -> bool:
    """Check Docker only after the user has selected a Docker-backed pack."""
    try:
        result = runner(["docker", "info"], capture_output=True, check=False, text=True)
    except OSError:
        return False
    return result.returncode == 0


def bring_up(
    option: TourPack,
    *,
    output: Output = print,
    runner: CommandRunner = subprocess.run,
    port_resolver: PortResolver | None = None,
) -> bool:
    """Start only services declared by the selected pack's existing Make targets."""
    commands: list[tuple[str, str]] = []
    if option.needs_source_service:
        commands.append(("source-up", "PostgreSQL source"))
    if option.needs_cube:
        commands.append(("cube-up", "Cube semantic service"))
    if not commands:
        output("Fixture uses the seeded backend. No containers are needed.")
        return True
    for target, label in commands:
        # Ports can change after the doctor has run, so apply the same authoritative
        # wildcard-bind remediation immediately before each service starts.
        from governed.cli.start import (
            PORTS,
            apply_selected_cube_port,
            apply_selected_source_port,
            resolve_port_collisions,
        )

        resolver = port_resolver or resolve_port_collisions
        port = PORTS[0] if target == "source-up" else PORTS[1]
        if not resolver(output=output, runner=runner, ports=(port,)):
            return False
        apply_selected_source_port(int(os.environ.get("SOURCE_HOST_PORT", "5433")))
        apply_selected_cube_port(int(os.environ.get("CUBE_HOST_PORT", "4000")))
        output(f"Starting {label} for {option.title}...")
        if not _run_make(target, option.dataset, runner=runner):
            output(f"Could not start {label}. The tour will clean up this pack.")
            return False
    return True


def teardown(option: TourPack, *, output: Output = print, runner: CommandRunner = subprocess.run) -> None:
    """Release only the selected pack's source and Cube Compose project."""
    if not option.needs_docker:
        output(
            "The Fixture tour is complete. It ran in-process with no Docker, so there is nothing to clean up. "
            "To see real movement, transformation, and end-to-end lineage, run `make start` again and choose AdventureWorks or TPC-H."
        )
        return
    output(f"Tearing down services for {option.title}...")
    if not _run_make("down", option.dataset, runner=runner):
        output(f"Could not confirm teardown. Run `make down DATASET={option.dataset}`.")


def run_dataset_step(
    *,
    input_func: Input = input,
    output: Output = print,
    runner: CommandRunner = subprocess.run,
    pack_loader: PackLoader = load_pack,
    source_available: SourceAvailable = source_is_available,
    disk_usage: DiskUsage = shutil.disk_usage,
    stage_walk: StageWalk = run_stage_walk,
    model_pick: ModelPick = choose_model,
    finale: Finale = run_interactive_finale,
    benchmark: Benchmark = offer_benchmark,
    port_resolver: PortResolver | None = None,
) -> int:
    """Select, start, walk, and clean up one declared dataset pack."""
    started: TourPack | None = None
    try:
        while True:
            option = choose_dataset(
                input_func=input_func,
                output=output,
                pack_loader=pack_loader,
                source_available=source_available,
            )
            if option is None:
                output("No dataset selected. Exiting the guided tour.")
                return 0
            if not ensure_external_source(
                option,
                input_func=input_func,
                output=output,
                runner=runner,
                pack_loader=pack_loader,
                source_available=source_available,
            ):
                output("Returning to the dataset menu.")
                continue
            if not docker_capacity_ok(option, disk_usage=disk_usage, output=output):
                return 2
            if option.needs_docker and not docker_is_ready(runner=runner):
                output("Docker Desktop is required for this pack. Install and start Docker Desktop, then retry.")
                return 2
            if not bring_up(option, output=output, runner=runner, port_resolver=port_resolver):
                teardown(option, output=output, runner=runner)
                return 2
            started = option
            output(f"{option.title} is ready. Beginning the guided stage walk.")
            stage_status = stage_walk(
                option.dataset,
                input_func=input_func,
                output=output,
                runner=runner,
                pack_loader=pack_loader,
            )
            if stage_status != 0:
                teardown(option, output=output, runner=runner)
                return 0 if stage_status == 1 else stage_status
            output("\nPart 2 of 3 · The test")
            output("Setup is done. You have seen how an answer is built and governed.")
            output("Now a small local model will answer once through the governed harness and once by writing raw SQL, so you can inspect the difference yourself.")
            model = model_pick(input_func=input_func, output=output, runner=runner)
            if model is None:
                output("No local model was selected, so the interactive payoff and benchmark are skipped for this run.")
            else:
                finale_status = finale(
                    option.dataset,
                    model,
                    input_func=input_func,
                    output=output,
                    pack_loader=pack_loader,
                )
                if finale_status != 0:
                    teardown(option, output=output, runner=runner)
                    return finale_status
                benchmark(option.dataset, model, input_func=input_func, output=output, runner=runner)
            if option.needs_docker:
                try:
                    answer = input_func("Tear down this pack's services now? [Y/n] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    answer = ""
                if answer not in {"n", "no"}:
                    teardown(option, output=output, runner=runner)
            else:
                teardown(option, output=output, runner=runner)
            return 0
    except KeyboardInterrupt:
        output("\nTour interrupted.")
        if started is not None:
            teardown(started, output=output, runner=runner)
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        output(f"Tour setup failed: {exc}")
        if started is not None:
            teardown(started, output=output, runner=runner)
        return 2
