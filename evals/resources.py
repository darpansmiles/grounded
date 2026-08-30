"""Low-overhead process resource sampling for local benchmark model runs."""

from __future__ import annotations

from threading import Event, Thread
from typing import Any, Protocol

try:
    import psutil
except ImportError:  # pragma: no cover - exercised through the unavailable seam
    psutil = None  # type: ignore[assignment]

_PSUTIL_ERROR = psutil.Error if psutil is not None else OSError


class ResourceSampler(Protocol):
    """Sample resources for one model run without affecting its result."""

    def start(self) -> None: ...

    def stop(self) -> dict[str, Any]: ...


class ProcessResourceSampler:
    """Sample this benchmark process's CPU and RSS at a modest fixed interval."""

    def __init__(self, interval_seconds: float = 0.5) -> None:
        self._interval_seconds = interval_seconds
        self._process: Any | None = None
        self._stop = Event()
        self._thread: Thread | None = None
        self._cpu_samples: list[float] = []
        self._rss_samples_mb: list[float] = []
        self._unavailable_reason: str | None = None
        if psutil is None:
            self._unavailable_reason = "psutil unavailable"

    def _sample(self) -> None:
        if self._process is None:
            return
        try:
            self._cpu_samples.append(float(self._process.cpu_percent(None)))
            self._rss_samples_mb.append(
                float(self._process.memory_info().rss) / (1024 * 1024)
            )
        except (_PSUTIL_ERROR, OSError, RuntimeError) as exc:  # sampling must never fail a benchmark
            self._unavailable_reason = f"resource sampling unavailable: {exc}"
            self._stop.set()

    def _sample_until_stopped(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            self._sample()

    def start(self) -> None:
        if self._unavailable_reason is not None:
            return
        try:
            self._process = psutil.Process()  # type: ignore[union-attr]
            self._process.cpu_percent(None)
            self._sample()
            self._thread = Thread(target=self._sample_until_stopped, daemon=True)
            self._thread.start()
        except (_PSUTIL_ERROR, OSError, RuntimeError) as exc:  # sampling must never fail a benchmark
            self._unavailable_reason = f"resource sampling unavailable: {exc}"

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval_seconds + 0.1)
        self._sample()
        if self._unavailable_reason is not None or not self._rss_samples_mb:
            return {
                "available": False,
                "reason": self._unavailable_reason or "resource sampling unavailable",
            }
        return {
            "available": True,
            "cpu_pct": {"mean": sum(self._cpu_samples) / len(self._cpu_samples)},
            "mem_rss_mb": {
                "mean": sum(self._rss_samples_mb) / len(self._rss_samples_mb),
                "peak": max(self._rss_samples_mb),
            },
        }


def process_resource_sampler() -> ResourceSampler:
    """Create the default sampler lazily so psutil remains an optional runtime aid."""
    return ProcessResourceSampler()
