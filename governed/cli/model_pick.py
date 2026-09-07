"""Select one installed local Ollama model for the guided payoff."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

Input = Callable[[str], str]
Output = Callable[[str], None]
CommandRunner = Callable[..., Any]


def installed_models(*, runner: CommandRunner = subprocess.run) -> list[str] | None:
    """Return installed Ollama models, or ``None`` when Ollama cannot be reached."""
    try:
        result = runner(["ollama", "list"], capture_output=True, check=False, text=True)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    rows = [line.split() for line in result.stdout.splitlines()[1:] if line.strip()]
    return [row[0] for row in rows if row]


def choose_model(
    *, input_func: Input = input, output: Output = print, runner: CommandRunner = subprocess.run
) -> str | None:
    """Offer any installed model or an explicit, consented Ollama pull."""
    models = installed_models(runner=runner)
    if models is None:
        output("Ollama is not reachable. Start it, then run `make start` again.")
        return None
    if models:
        output("\nPart 2 of 3 · The test · Choose a local model")
        for number, model in enumerate(models, start=1):
            default = " (recommended default)" if number == 1 else ""
            output(f"  {number}. {model}{default}")
    else:
        output("No local Ollama models are installed yet.")
    try:
        choice = input_func("Choose a number, type a model name to pull, or q to skip the test: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if choice.casefold() in {"q", "quit", ""}:
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        selected = models[int(choice) - 1]
        output(f"Using local model: {selected}")
        return selected
    selected = choice
    try:
        consent = input_func(f"Pull `{selected}` from Ollama now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        consent = ""
    if consent not in {"y", "yes"}:
        output("No model was selected. The payoff is skipped for this run.")
        return None
    output(f"Pulling `{selected}`...")
    try:
        result = runner(["ollama", "pull", selected], check=False)
    except OSError:
        result = None
    if result is None or result.returncode != 0:
        output(f"Could not pull `{selected}`. Check Ollama, then retry the tour.")
        return None
    output(f"Pulled `{selected}`.")
    return selected
