from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LatencySummary:
    count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


@dataclass(frozen=True)
class ValidationRunSummary:
    name: str
    total: int
    success: int
    failed: int
    latency: LatencySummary
    errors: dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.success / self.total


@dataclass(frozen=True)
class ThresholdEvaluation:
    passed: bool
    failures: list[str]


def summarize_latencies(latencies_ms: list[float]) -> LatencySummary:
    return LatencySummary(
        count=len(latencies_ms),
        p50_ms=_percentile(latencies_ms, 0.50),
        p95_ms=_percentile(latencies_ms, 0.95),
        p99_ms=_percentile(latencies_ms, 0.99),
        max_ms=max(latencies_ms, default=0.0),
    )


def summarize_run(
    name: str,
    latencies_ms: list[float],
    errors: list[str],
) -> ValidationRunSummary:
    error_counts: dict[str, int] = {}
    for error in errors:
        error_counts[error] = error_counts.get(error, 0) + 1
    total = len(latencies_ms) + len(errors)
    return ValidationRunSummary(
        name=name,
        total=total,
        success=len(latencies_ms),
        failed=len(errors),
        latency=summarize_latencies(latencies_ms),
        errors=error_counts,
    )


def evaluate_thresholds(
    summary: ValidationRunSummary,
    *,
    p95_threshold_ms: float,
) -> ThresholdEvaluation:
    failures: list[str] = []
    if summary.failed:
        failures.append(f"{summary.failed} requests failed")
    if summary.latency.p95_ms > p95_threshold_ms:
        failures.append(
            f"p95 latency {summary.latency.p95_ms:.2f}ms exceeded {p95_threshold_ms:.2f}ms"
        )
    return ThresholdEvaluation(passed=not failures, failures=failures)


def evaluate_warmup_improvement(
    cold: ValidationRunSummary,
    warm: ValidationRunSummary,
    *,
    min_improvement_ratio: float,
) -> ThresholdEvaluation:
    if min_improvement_ratio < 0:
        return ThresholdEvaluation(passed=True, failures=[])

    failures: list[str] = []
    if cold.latency.p95_ms <= 0 or warm.latency.p95_ms <= 0:
        failures.append("cold and warm p95 latency must both be recorded")
    else:
        improvement = (cold.latency.p95_ms - warm.latency.p95_ms) / cold.latency.p95_ms
        if improvement < min_improvement_ratio:
            failures.append(
                f"warm p95 improved {improvement:.2%}, below {min_improvement_ratio:.2%}"
            )
    return ThresholdEvaluation(passed=not failures, failures=failures)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * percentile))
    return ordered[index]
