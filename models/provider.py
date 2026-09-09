"""Small provider seam for deterministic tests and optional local Ollama runs."""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# A single request can be slow while Ollama cold-loads a large model into memory,
# especially on a memory-constrained machine. The default is generous; override with
# GROUNDED_OLLAMA_HTTP_TIMEOUT (seconds). This is per-request; the per-model wall clock
# lives in the benchmark runner (GROUNDED_MODEL_TIMEOUT).
DEFAULT_HTTP_TIMEOUT_SECONDS = 600.0
_HTTP_ATTEMPTS = 2


def _default_http_timeout() -> float:
    raw = os.environ.get("GROUNDED_OLLAMA_HTTP_TIMEOUT")
    if raw is None:
        return DEFAULT_HTTP_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_HTTP_TIMEOUT_SECONDS
    return value if math.isfinite(value) and value > 0 else DEFAULT_HTTP_TIMEOUT_SECONDS


def _looks_like_timeout(exc: Exception) -> bool:
    """A cold-load timeout is transient and worth one retry; a refused host is not."""
    return isinstance(exc, TimeoutError) or "timed out" in str(exc).lower()


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
    timeout: float = field(default_factory=_default_http_timeout)
    retry_backoff_seconds: float = 2.0

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
        body = None
        for attempt in range(1, _HTTP_ATTEMPTS + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except (HTTPError, URLError, OSError, TimeoutError) as exc:
                if attempt < _HTTP_ATTEMPTS and _looks_like_timeout(exc):
                    time.sleep(self.retry_backoff_seconds)
                    continue
                raise ProviderUnavailable(
                    f"Ollama is unavailable at {self.host} "
                    f"(per-request timeout {self.timeout:.0f}s, {attempt} attempt(s)): {exc}. "
                    f"Ensure `ollama serve` is running and `{self.model}` is pulled; "
                    f"raise GROUNDED_OLLAMA_HTTP_TIMEOUT if a large model is slow to load."
                ) from exc

        text = body.get("response")
        if not isinstance(text, str):
            raise ProviderUnavailable("Ollama returned no text response; verify the local model is available.")
        return text
