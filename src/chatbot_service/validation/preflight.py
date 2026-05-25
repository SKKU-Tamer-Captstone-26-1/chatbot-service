from __future__ import annotations

from dataclasses import dataclass

from chatbot_service.validation.config import ValidationConfig


@dataclass(frozen=True)
class PreflightResult:
    passed: bool
    checks: dict[str, str]


async def run_preflight_checks(config: ValidationConfig) -> PreflightResult:
    checks: dict[str, str] = {}
    if config.require_redis_preflight:
        checks["redis"] = await _check_redis(config)
    else:
        checks["redis"] = "skipped"

    return PreflightResult(
        passed=all(value in {"ok", "skipped"} for value in checks.values()),
        checks=checks,
    )


async def _check_redis(config: ValidationConfig) -> str:
    if config.cache_backend.strip().lower() != "redis":
        return "failed: CHATBOT_CACHE_BACKEND is not redis"
    if not config.cache_redis_url:
        return "failed: CHATBOT_CACHE_REDIS_URL is required"
    try:
        from redis import asyncio as redis_asyncio

        client = redis_asyncio.from_url(
            config.cache_redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            pong = await client.ping()
        finally:
            await client.aclose()
    except Exception as exc:
        return f"failed: {type(exc).__name__}"
    return "ok" if pong else "failed: ping returned false"

