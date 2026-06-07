from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from chatbot_service.validation.config import ValidationConfig


@dataclass(frozen=True)
class PreflightResult:
    passed: bool
    checks: dict[str, str]


async def run_preflight_checks(config: ValidationConfig) -> PreflightResult:
    checks: dict[str, str] = {}
    checks.update(_check_validation_settings(config))
    if config.require_runtime_preflight:
        checks.update(_check_runtime_settings(config))
    else:
        checks["runtime_config"] = "skipped"

    if config.require_redis_preflight:
        checks["redis"] = await _check_redis(config)
    else:
        checks["redis"] = "skipped"

    return PreflightResult(
        passed=all(value in {"ok", "skipped"} for value in checks.values()),
        checks=checks,
    )


def _check_validation_settings(config: ValidationConfig) -> dict[str, str]:
    checks = {
        "validation_target": _required("CHATBOT_VALIDATION_TARGET", config.target),
        "validation_user_id": _required("CHATBOT_VALIDATION_USER_ID", config.user_id),
    }
    if config.require_authorization:
        checks["validation_authorization"] = _required(
            "CHATBOT_VALIDATION_AUTHORIZATION",
            config.authorization,
        )
    else:
        checks["validation_authorization"] = "skipped"
    return checks


def _check_runtime_settings(config: ValidationConfig) -> dict[str, str]:
    checks: dict[str, str] = {
        "recommendation_service_grpc_addr": _required(
            "RECOMMENDATION_SERVICE_GRPC_ADDR",
            config.recommendation_service_url,
        )
    }
    if config.store_conversations:
        checks["postgres_dsn"] = _required("CHATBOT_DB_DSN", config.db_dsn)
    else:
        checks["postgres_dsn"] = "skipped"

    llm_provider = config.llm_provider.strip().lower()
    if llm_provider == "huggingface_tgi":
        checks["llm_endpoint_url"] = _required(
            "CHATBOT_LLM_ENDPOINT_URL",
            config.llm_endpoint_url,
        )
        checks["llm_endpoint_format"] = _check_openai_chat_completions_url(
            config.llm_endpoint_url,
        )
        checks["llm_model"] = _required("CHATBOT_LLM_MODEL", config.llm_model)
        checks.update(_check_llm_auth_settings(config))
    elif llm_provider in {"", "none"}:
        checks["llm_provider"] = "failed: CHATBOT_LLM_PROVIDER is required for staging"
    else:
        checks["llm_provider"] = f"failed: unsupported CHATBOT_LLM_PROVIDER {config.llm_provider}"
    return checks


def _check_openai_chat_completions_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return "failed: CHATBOT_LLM_ENDPOINT_URL is required"
    if _looks_like_placeholder(cleaned):
        return "failed: CHATBOT_LLM_ENDPOINT_URL still has a placeholder value"

    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return "failed: CHATBOT_LLM_ENDPOINT_URL must be a valid URL"

    if not parsed.scheme:
        return "failed: CHATBOT_LLM_ENDPOINT_URL must be an HTTP-compatible URL"
    if parsed.scheme not in {"http", "https"}:
        return "failed: CHATBOT_LLM_ENDPOINT_URL must be HTTP or HTTPS"

    path = (parsed.path or "").rstrip("/")
    if path.endswith("/v1/chat/completions"):
        return "ok"
    return "failed: CHATBOT_LLM_ENDPOINT_URL must end with /v1/chat/completions"


def _check_llm_auth_settings(config: ValidationConfig) -> dict[str, str]:
    checks: dict[str, str] = {}
    auth_mode = _normalize_mode(config.llm_auth_mode)
    if auth_mode == "bearer_env":
        api_key_env_status = _required("CHATBOT_LLM_API_KEY_ENV", config.llm_api_key_env)
        checks["llm_api_key_env"] = api_key_env_status
        checks["llm_api_key"] = (
            "ok"
            if api_key_env_status == "ok" and config.llm_api_key_available
            else f"failed: {config.llm_api_key_env} is required"
        )
    elif auth_mode in {"", "none"}:
        checks["llm_api_key"] = "skipped"
    else:
        checks["llm_auth_mode"] = (
            f"failed: unsupported CHATBOT_LLM_AUTH_MODE {config.llm_auth_mode}"
        )
    return checks


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


def _required(name: str, value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return f"failed: {name} is required"
    if _looks_like_placeholder(cleaned):
        return f"failed: {name} still has a placeholder value"
    return "ok"


def _looks_like_placeholder(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in ("REPLACE", "TODO", "CHANGE_ME"))


def _normalize_mode(value: str) -> str:
    return value.strip().lower().replace("-", "_")
