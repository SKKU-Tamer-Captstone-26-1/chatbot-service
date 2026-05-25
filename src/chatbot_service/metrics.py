from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock


def _metric_key(name: str, labels: dict[str, str] | None = None) -> str:
    if not labels:
        return name
    parts = [f"{key}={labels[key]}" for key in sorted(labels)]
    return f"{name}|{','.join(parts)}"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * percentile))
    return ordered[index]


@dataclass(frozen=True)
class TimerSummary:
    count: int
    p50: float
    p95: float
    p99: float
    max: float


class MetricsRecorder:
    """Small in-process metrics collector.

    Production deployments can later bridge this interface to OpenTelemetry or
    Cloud Monitoring without changing pipeline code.
    """

    def __init__(self, snapshot_path: str | Path | None = None) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = {}
        self._timers: dict[str, list[float]] = {}
        self._snapshot_path = Path(snapshot_path) if snapshot_path else None

    def increment(self, name: str, value: int = 1, **labels: str) -> None:
        key = _metric_key(name, labels or None)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value
            self._write_snapshot_locked()

    def observe(self, name: str, seconds: float, **labels: str) -> None:
        key = _metric_key(name, labels or None)
        with self._lock:
            self._timers.setdefault(key, []).append(seconds)
            self._write_snapshot_locked()

    @contextmanager
    def timer(self, name: str, **labels: str) -> Iterator[None]:
        started_at = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - started_at, **labels)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = dict(self._counters)
            timers = {
                key: TimerSummary(
                    count=len(values),
                    p50=_percentile(values, 0.50),
                    p95=_percentile(values, 0.95),
                    p99=_percentile(values, 0.99),
                    max=max(values, default=0.0),
                )
                for key, values in self._timers.items()
            }
        return {"counters": counters, "timers": timers}

    def snapshot_json(self) -> dict[str, object]:
        with self._lock:
            return self._snapshot_json_locked()

    def _snapshot_json_locked(self) -> dict[str, object]:
        return {
            "counters": dict(self._counters),
            "timers": {
                key: {
                    "count": len(values),
                    "p50": _percentile(values, 0.50),
                    "p95": _percentile(values, 0.95),
                    "p99": _percentile(values, 0.99),
                    "max": max(values, default=0.0),
                }
                for key, values in self._timers.items()
            },
        }

    def _write_snapshot_locked(self) -> None:
        if self._snapshot_path is None:
            return
        try:
            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            self._snapshot_path.write_text(
                json.dumps(self._snapshot_json_locked(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return


__all__ = ["MetricsRecorder", "TimerSummary"]
