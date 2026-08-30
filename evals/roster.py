"""Load the local-only benchmark roster from configuration."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT_ROSTER_PATH = Path(__file__).with_name("model_roster.yml")


def model_roster() -> list[str]:
    """Return configured Ollama tags, optionally overridden for a bounded local run."""
    override = os.environ.get("GROUNDED_MODELS")
    if override is not None:
        models = [model.strip() for model in override.split(",") if model.strip()]
    else:
        path = Path(os.environ.get("GROUNDED_MODEL_ROSTER", DEFAULT_ROSTER_PATH))
        with path.open(encoding="utf-8") as roster_file:
            data = yaml.safe_load(roster_file)
        models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list) or not models or any(
        not isinstance(model, str) or not model for model in models
    ):
        raise ValueError("Model roster must be a non-empty list of Ollama tags")
    return models
