"""First-run doctor and entry point for the guided Grounded tour."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import socket
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from governed.cli.narration import LANDING_SPLASH
from governed.cli.secrets import ensure_local_source_dsns, local_source_dsns
from governed.cli.style import Presenter
from governed.cli.tour import run_dataset_step

GIB = 1024**3
MINIMUM_FREE_DISK_BYTES = GIB
DISK_WARNING_BYTES = 5 * GIB


@dataclass(frozen=True)
class DoctorCheck:
    """One first-run prerequisite check with a concrete remediation."""

    label: str
    passed: bool
    detail: str
    remedy: str | None = None
    blocks_tour: bool = True
    warning: bool = False


@dataclass(frozen=True)
class Port:
    """A configurable host port used by the existing Make targets."""

    label: str
    environment_variable: str
    default: int


PORTS = (
    Port("PostgreSQL source", "SOURCE_HOST_PORT", 5433),
    Port("Cube", "CUBE_HOST_PORT", 4000),
)

CommandRunner = Callable[..., Any]
Input = Callable[[str], str]
Output = Callable[[str], None]
PortAvailable = Callable[[int], bool]


def _run(command: list[str], runner: CommandRunner) -> Any | None:
    try:
        return runner(command, capture_output=True, check=False, text=True)
    except OSError:
        return None


def _editable_install_present() -> bool:
    """Return whether this interpreter has Grounded as an editable install."""
    try:
        distribution = importlib.metadata.distribution("grounded")
        direct_url = distribution.read_text("direct_url.json")
    except importlib.metadata.PackageNotFoundError:
        return False
    try:
        payload = json.loads(direct_url or "{}")
    except json.JSONDecodeError:
        return False
    return payload.get("dir_info", {}).get("editable") is True


def _port_is_available(port: int) -> bool:
    """Test whether the local host can bind a TCP port without changing state."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("", port))
        except OSError:
            return False
    return True


def _next_available_port(port: int, port_available: PortAvailable) -> int:
    for candidate in range(port + 1, 65536):
        if port_available(candidate):
            return candidate
    raise RuntimeError(f"No free TCP port found after {port}.")


def _docker_container_using_port(port: int, runner: CommandRunner) -> str | None:
    result = _run(["docker", "ps", "-q", "--filter", f"publish={port}"], runner)
    if result is None or result.returncode != 0:
        return None
    container_id = result.stdout.strip().splitlines()
    if not container_id:
        return None
    name = _run(["docker", "inspect", "--format", "{{.Name}}", container_id[0]], runner)
    if name is None or name.returncode != 0:
        return None
    return name.stdout.strip().lstrip("/") or container_id[0]


def _leftover_grounded_containers(runner: CommandRunner) -> list[str]:
    """Return stopped or running Grounded containers left by an earlier local run."""
    result = _run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "name=grounded-",
            "--format",
            "{{.Names}}\t{{.Image}}\t{{.Ports}}",
        ],
        runner,
    )
    if result is None or result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def offer_stale_container_cleanup(
    *, input_func: Input = input, output: Output = print, runner: CommandRunner = subprocess.run
) -> None:
    """Offer to remove only clearly named leftovers from previous Grounded runs."""
    leftovers = _leftover_grounded_containers(runner)
    if not leftovers:
        return
    output(f"Found {len(leftovers)} leftover Grounded container(s) from previous runs:")
    Presenter(output).table(
        "Leftover Grounded containers",
        ["Name", "Image", "Ports"],
        [line.split("\t", 2) for line in leftovers],
    )
    try:
        answer = input_func("Remove them now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer not in {"y", "yes"}:
        output("Leaving those containers unchanged. You can remove them with `docker rm -f <name>`.")
        return
    names = [line.split("\t", 1)[0] for line in leftovers]
    result = _run(["docker", "rm", "-f", *names], runner)
    if result is None or result.returncode != 0:
        output("Could not remove the leftover containers. Run `docker rm -f <name>` and retry.")
    else:
        output("Removed leftover Grounded containers.")


def doctor_checks(
    *,
    needs_docker: bool = False,
    runner: CommandRunner = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
    disk_usage: Callable[[str | os.PathLike[str]], Any] = shutil.disk_usage,
    project_root: Path | None = None,
) -> list[DoctorCheck]:
    """Inspect local prerequisites without starting services or the pipeline."""
    root = project_root or Path.cwd()
    free_bytes = disk_usage(root).free
    editable_install = _editable_install_present()
    checks = [
        DoctorCheck(
            "Editable install",
            editable_install,
            "Grounded is installed for this Python environment"
            if editable_install
            else "Grounded is not installed in editable mode",
            "Run `.venv/bin/python -m pip install -e .`, then retry.",
        ),
        DoctorCheck(
            "Free disk",
            free_bytes >= MINIMUM_FREE_DISK_BYTES,
            f"{free_bytes / (1024 ** 3):.1f} GiB available",
            "Free disk space, then retry.",
            warning=MINIMUM_FREE_DISK_BYTES <= free_bytes < DISK_WARNING_BYTES,
        ),
    ]

    docker = _run(["docker", "info"], runner)
    docker_ready = docker is not None and docker.returncode == 0
    checks.append(
        DoctorCheck(
            "Docker Desktop",
            docker_ready,
            "running" if docker_ready else "not running or not installed",
            "Install and start Docker Desktop, then retry.",
            blocks_tour=needs_docker,
        )
    )

    if which("ollama") is None:
        checks.append(
            DoctorCheck(
                "Ollama",
                False,
                "not installed",
                "Install Ollama from https://ollama.com, then retry.",
            )
        )
    else:
        ollama = _run(["ollama", "list"], runner)
        checks.append(
            DoctorCheck(
                "Ollama",
                ollama is not None and ollama.returncode == 0,
                "reachable" if ollama is not None and ollama.returncode == 0 else "not reachable",
                "Start Ollama, then retry.",
            )
        )
    return checks


def render_doctor(checks: Iterable[DoctorCheck], output: Output = print) -> bool:
    """Print a compact table and return whether all required checks passed."""
    output("\nDoctor\n")
    required_passed = True
    for check in checks:
        if check.passed:
            status = "WARN" if check.warning else "PASS"
        elif check.blocks_tour:
            status = "FAIL"
            required_passed = False
        else:
            status = "LATER"
        output(f"  {status:<5} {check.label:<18} {check.detail}")
        if not check.passed and check.remedy:
            output(f"        Fix: {check.remedy}")
        if check.warning:
            output("        Note: full-tour Docker packs need a few GB for images and data; Fixture needs almost none.")
    return required_passed


def resolve_port_collisions(
    *,
    input_func: Input = input,
    output: Output = print,
    runner: CommandRunner = subprocess.run,
    port_available: PortAvailable = _port_is_available,
    ports: Iterable[Port] = PORTS,
) -> bool:
    """Offer safe, explicit handling for ports supported by existing Make targets."""
    for port in ports:
        selected = int(os.environ.get(port.environment_variable, port.default))
        container = _docker_container_using_port(selected, runner)
        if port_available(selected) and container is None:
            output(f"  PASS  {port.label:<18} port {selected} is available")
            continue

        alternate = _next_available_port(
            selected,
            lambda candidate: port_available(candidate)
            and _docker_container_using_port(candidate, runner) is None,
        )
        output(f"  IN USE {port.label:<18} port {selected} is already in use")
        output(f"        [a] Use port {alternate} for this tour")
        if container:
            output(f"        [s] Stop Docker container `{container}` with `docker stop {container}`")
        output("        [q] Exit without changing any service")
        choice = input_func("Choose a port action [a/s/q]: ").strip().lower() or "a"
        if choice == "a":
            os.environ[port.environment_variable] = str(alternate)
            output(
                f"        Using {port.environment_variable}={alternate} for this tour. "
                f"Reuse it manually with `{port.environment_variable}={alternate} make start`."
            )
            continue
        if choice == "s" and container:
            result = _run(["docker", "stop", container], runner)
            if result is not None and result.returncode == 0 and port_available(selected):
                output(f"        Stopped {container}; port {selected} is now available.")
                continue
            output(f"        Could not stop {container}. Run `docker stop {container}` and retry.")
            return False
        output("        No service was changed. Restart with a free port to continue.")
        return False
    return True


def apply_selected_source_port(source_host_port: int) -> None:
    """Use an alternate local source port for this tour without rewriting user secrets."""
    if source_host_port == 5433:
        return
    for name, dsn in local_source_dsns(source_host_port).items():
        os.environ.setdefault(name, dsn)


def apply_selected_cube_port(cube_host_port: int) -> None:
    """Keep the in-process resolver pointed at the tour's selected Cube port."""
    if cube_host_port != 4000:
        os.environ.setdefault("GROUNDED_CUBE_URL", f"http://localhost:{cube_host_port}/cubejs-api/v1")


def run_start(
    *,
    input_func: Input = input,
    output: Output = print,
    runner: CommandRunner = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
    port_available: PortAvailable = _port_is_available,
    secrets_path: Path | None = None,
) -> int:
    """Run the 057a greeting, doctor, local secrets, and port preflight only."""
    output(LANDING_SPLASH)
    output("\nThis guided tour will prepare one governed data journey in this terminal.\n")

    checks = doctor_checks(runner=runner, which=which)
    ready = render_doctor(checks, output)
    if not ready:
        output("\nSetup is incomplete. Apply the fixes above, then run `make start` again.")
        return 2

    offer_stale_container_cleanup(input_func=input_func, output=output, runner=runner)

    if not resolve_port_collisions(
        input_func=input_func,
        output=output,
        runner=runner,
        port_available=port_available,
    ):
        return 2

    source_host_port = int(os.environ.get("SOURCE_HOST_PORT", "5433"))
    path = ensure_local_source_dsns(
        secrets_path or Path(".dlt/secrets.toml"),
        source_host_port=source_host_port,
    )
    apply_selected_source_port(source_host_port)
    apply_selected_cube_port(int(os.environ.get("CUBE_HOST_PORT", "4000")))
    output(f"\nSaved local source settings to {path}; secret values were not printed.")
    output("Setup is ready.")
    return run_dataset_step(input_func=input_func, output=output, runner=runner)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the guided Grounded tour.")
    parser.add_argument("command", nargs="?", choices=("start",), default="start")
    parser.add_argument("--doctor", action="store_true", help="run the setup doctor and exit")
    arguments = parser.parse_args(argv)
    if arguments.doctor:
        return 0 if render_doctor(doctor_checks()) else 2
    return run_start()


if __name__ == "__main__":
    raise SystemExit(main())
