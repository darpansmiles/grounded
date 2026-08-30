"""Small provider seam for deterministic tests and optional local Ollama runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderUnavailable(RuntimeError):
    """Raised when a configured local model provider cannot be reached."""


class LLMProvider(Protocol):
    """Return one complete text response for a system prompt and user request."""

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        """Complete a single non-streaming request."""


@dataclass
class StubProvider:
    """Deterministic test provider that selects the first matching canned response."""

    responses: dict[str, str]
    default: str = field(default='{"tool":"refuse","args":{}}')

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        del system, temperature
        for substring, response in self.responses.items():
            if substring in user:
                return response
        return self.default


@dataclass
class OllamaProvider:
    """Use Ollama's local non-streaming generation endpoint without API keys."""

    model: str = "llama3.2"
    host: str = "http://localhost:11434"
    temperature: float = 0.0

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        """Request one response or explain how to make the local service available."""
        payload = json.dumps(
            {
                "model": self.model,
                "system": system,
                "prompt": user,
                "stream": False,
                "options": {"temperature": self.temperature if temperature == 0.0 else temperature},
            }
        ).encode("utf-8")
        request = Request(
            f"{self.host.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise ProviderUnavailable(
                f"Ollama is unavailable at {self.host}: {exc}. "
                f"Start it with `ollama serve` and pull `{self.model}`."
            ) from exc

        text = body.get("response")
        if not isinstance(text, str):
            raise ProviderUnavailable("Ollama returned no text response; verify the local model is available.")
        return text
