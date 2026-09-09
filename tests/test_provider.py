from __future__ import annotations

import json
from typing import Self
from urllib.error import URLError

import pytest

from models.provider import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_NUM_PREDICT,
    OllamaProvider,
    ProviderUnavailable,
)


class _Response:
    def __init__(self, payload: bytes = b'{"response":"done"}') -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_ollama_http_timeout_uses_env_or_safe_default(monkeypatch):
    monkeypatch.delenv("GROUNDED_OLLAMA_HTTP_TIMEOUT", raising=False)
    assert OllamaProvider().timeout == DEFAULT_HTTP_TIMEOUT_SECONDS

    monkeypatch.setenv("GROUNDED_OLLAMA_HTTP_TIMEOUT", "725.5")
    assert OllamaProvider().timeout == 725.5

    for invalid in ("bad", "0", "-4", "inf"):
        monkeypatch.setenv("GROUNDED_OLLAMA_HTTP_TIMEOUT", invalid)
        assert OllamaProvider().timeout == DEFAULT_HTTP_TIMEOUT_SECONDS


def test_ollama_num_predict_uses_env_or_safe_default(monkeypatch):
    monkeypatch.delenv("GROUNDED_OLLAMA_NUM_PREDICT", raising=False)
    assert OllamaProvider().num_predict == DEFAULT_NUM_PREDICT

    monkeypatch.setenv("GROUNDED_OLLAMA_NUM_PREDICT", "768")
    assert OllamaProvider().num_predict == 768

    for invalid in ("bad", "0", "-4", "2.5"):
        monkeypatch.setenv("GROUNDED_OLLAMA_NUM_PREDICT", invalid)
        assert OllamaProvider().num_predict == DEFAULT_NUM_PREDICT


def test_ollama_request_payload_includes_generation_cap(monkeypatch):
    payloads: list[dict] = []

    def available(request, *, timeout: float):
        del timeout
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response()

    monkeypatch.setattr("models.provider.urlopen", available)

    assert OllamaProvider(num_predict=321).complete("system", "question") == "done"
    assert payloads == [
        {
            "model": "llama3.2",
            "system": "system",
            "prompt": "question",
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 321},
        }
    ]


def test_ollama_retries_exactly_once_after_timeout(monkeypatch):
    calls: list[float] = []
    sleeps: list[float] = []

    def timed_out(_request, *, timeout: float):
        calls.append(timeout)
        raise TimeoutError("operation timed out")

    monkeypatch.setattr("models.provider.urlopen", timed_out)
    monkeypatch.setattr("models.provider.time.sleep", sleeps.append)

    with pytest.raises(ProviderUnavailable, match=r"2 attempt\(s\).+timed out"):
        OllamaProvider(timeout=17.0, retry_backoff_seconds=0.25).complete(
            "system", "question"
        )

    assert calls == [17.0, 17.0]
    assert sleeps == [0.25]


def test_ollama_does_not_retry_a_refused_host(monkeypatch):
    calls = 0

    def refused(_request, *, timeout: float):
        nonlocal calls
        calls += 1
        del timeout
        raise URLError(ConnectionRefusedError(61, "Connection refused"))

    monkeypatch.setattr("models.provider.urlopen", refused)
    monkeypatch.setattr(
        "models.provider.time.sleep",
        lambda _seconds: pytest.fail("a refused host must not be retried"),
    )

    with pytest.raises(ProviderUnavailable, match="Connection refused"):
        OllamaProvider().complete("system", "question")

    assert calls == 1


def test_ollama_timeout_retry_can_succeed_without_replaying_more_requests(monkeypatch):
    attempts = 0

    def eventually_available(_request, *, timeout: float):
        nonlocal attempts
        attempts += 1
        del timeout
        if attempts == 1:
            raise TimeoutError("timed out while cold loading")
        return _Response()

    monkeypatch.setattr("models.provider.urlopen", eventually_available)
    monkeypatch.setattr("models.provider.time.sleep", lambda _seconds: None)

    assert OllamaProvider(retry_backoff_seconds=0).complete("system", "question") == "done"
    assert attempts == 2
