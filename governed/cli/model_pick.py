"""Select one installed local Ollama model for the guided payoff."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

Input = Callable[[str], str]
Output = Callable[[str], None]
CommandRunner = Callable[..., Any]

MODEL_PREFERENCE = (
    "phi4",
    "qwen2.5:14b",
    "qwen2.5:7b",
    "gemma2:9b",
    "llama3.1:8b",
    "mistral:7b",
    "qwen2.5:3b",
    "llama3.2:3b",
    "phi3.5",
)


def _model_key(model: str) -> str:
    """Compare a model name with or without its conventional ``:latest`` tag."""
    return model.casefold().removesuffix(":latest")


def _installed_model(choice: str, models: list[str]) -> str | None:
    """Return the installed spelling for a selected model, if any."""
    choice_key = _model_key(choice)
    return next((model for model in models if _model_key(model) == choice_key), None)


def recommended_model(models: list[str]) -> str | None:
    """Choose the strongest declared preference that is actually installed."""
    for preferred in MODEL_PREFERENCE:
        installed = _installed_model(preferred, models)
        if installed is not None:
            return installed
    return models[0] if models else None


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
        default_model = recommended_model(models)
        for number, model in enumerate(models, start=1):
            default = " (recommended default)" if model == default_model else ""
            output(f"  {number}. {model}{default}")
    else:
        default_model = None
        output("No local Ollama models are installed yet.")
    try:
        choice = input_func(
            "Choose a number, press Enter for the recommended model, type a model name to pull, or q to skip the test: "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if choice.casefold() in {"q", "quit"}:
        return None
    if not choice and default_model is not None:
        output(f"Using local model: {default_model}")
        return default_model
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        selected = models[int(choice) - 1]
        output(f"Using local model: {selected}")
        return selected
    installed = _installed_model(choice, models)
    if installed is not None:
        output(f"Using local model: {installed}")
        return installed
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
