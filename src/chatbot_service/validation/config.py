from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationConfig:
    target: str
    secure: bool
    user_id_metadata_key: str
    user_id: str
    authorization_metadata_key: str
    authorization: str
    timeout_sec: float
    beverage_message: str
    venue_message: str
    selected_beverage_id: str
    category: str
    budget_mode: str
    beverage_limit: int
    venue_limit: int
    lat: float
    lng: float
    radius_m: int
    concurrency: int
    requests: int
    p95_threshold_ms: float
    cache_warmup_min_improvement_ratio: float
    cache_backend: str
    cache_redis_url: str
    require_redis_preflight: bool
    require_runtime_preflight: bool
    require_authorization: bool
    recommendation_service_url: str
    recommendation_service_grpc_tls: bool
    store_conversations: bool
    db_dsn: str
    llm_provider: str
    llm_model: str
    llm_endpoint_url: str
    llm_auth_mode: str
    llm_api_key_env: str
    llm_api_key_available: bool
    service_metrics_path: str

    @property
    def metadata(self) -> list[tuple[str, str]]:
        metadata = [(self.user_id_metadata_key, self.user_id)]
        if self.authorization:
            metadata.append((self.authorization_metadata_key, self.authorization))
        return metadata


def load_validation_config(env: dict[str, str] | None = None) -> ValidationConfig:
    source = env or os.environ
    raw_target = source.get("CHATBOT_VALIDATION_TARGET", "localhost:9100")
    target, secure = _normalize_target(raw_target)
    llm_api_key_env = source.get("CHATBOT_LLM_API_KEY_ENV", "HF_TOKEN")
    return ValidationConfig(
        target=target,
        secure=_env_bool(source, "CHATBOT_VALIDATION_SECURE", secure),
        user_id_metadata_key=source.get("CHATBOT_AUTH_USER_ID_METADATA_KEY", "x-user-id"),
        user_id=source.get("CHATBOT_VALIDATION_USER_ID", "validation-user"),
        authorization_metadata_key=source.get(
            "CHATBOT_AUTH_AUTHORIZATION_METADATA_KEY",
            "authorization",
        ),
        authorization=source.get("CHATBOT_VALIDATION_AUTHORIZATION", ""),
        timeout_sec=float(source.get("CHATBOT_VALIDATION_TIMEOUT_SEC", "15")),
        beverage_message=source.get(
            "CHATBOT_VALIDATION_BEVERAGE_MESSAGE",
            "내 취향에 맞는 술 추천해줘",
        ),
        venue_message=source.get(
            "CHATBOT_VALIDATION_VENUE_MESSAGE",
            "근처에서 살 수 있는 곳 알려줘",
        ),
        selected_beverage_id=source.get("CHATBOT_VALIDATION_SELECTED_BEVERAGE_ID", "bev_1"),
        category=source.get("CHATBOT_VALIDATION_CATEGORY", ""),
        budget_mode=source.get("CHATBOT_VALIDATION_BUDGET_MODE", "BUDGET_MODE_SOFT"),
        beverage_limit=int(source.get("CHATBOT_VALIDATION_BEVERAGE_LIMIT", "3")),
        venue_limit=int(source.get("CHATBOT_VALIDATION_VENUE_LIMIT", "3")),
        lat=float(source.get("CHATBOT_VALIDATION_LAT", "37.5665")),
        lng=float(source.get("CHATBOT_VALIDATION_LNG", "126.9780")),
        radius_m=int(source.get("CHATBOT_VALIDATION_RADIUS_M", "1500")),
        concurrency=int(source.get("CHATBOT_VALIDATION_CONCURRENCY", "500")),
        requests=int(source.get("CHATBOT_VALIDATION_REQUESTS", "500")),
        p95_threshold_ms=float(source.get("CHATBOT_VALIDATION_P95_THRESHOLD_MS", "5000")),
        cache_warmup_min_improvement_ratio=float(
            source.get("CHATBOT_VALIDATION_CACHE_WARMUP_MIN_IMPROVEMENT_RATIO", "-1")
        ),
        cache_backend=source.get("CHATBOT_CACHE_BACKEND", ""),
        cache_redis_url=source.get("CHATBOT_CACHE_REDIS_URL", ""),
        require_redis_preflight=_env_bool(
            source,
            "CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT",
            source.get("CHATBOT_CACHE_BACKEND", "").strip().lower() == "redis",
        ),
        require_runtime_preflight=_env_bool(
            source,
            "CHATBOT_VALIDATION_REQUIRE_RUNTIME_PREFLIGHT",
            True,
        ),
        require_authorization=_env_bool(
            source,
            "CHATBOT_VALIDATION_REQUIRE_AUTHORIZATION",
            True,
        ),
        recommendation_service_url=_recommendation_service_target(source),
        recommendation_service_grpc_tls=_env_bool(
            source,
            "RECOMMENDATION_SERVICE_GRPC_TLS",
            _recommendation_service_default_tls(_recommendation_service_target(source)),
        ),
        store_conversations=_env_bool(source, "CHATBOT_STORE_CONVERSATIONS", True),
        db_dsn=source.get("CHATBOT_DB_DSN", ""),
        llm_provider=source.get("CHATBOT_LLM_PROVIDER", "none"),
        llm_model=source.get("CHATBOT_LLM_MODEL", ""),
        llm_endpoint_url=source.get("CHATBOT_LLM_ENDPOINT_URL", ""),
        llm_auth_mode=source.get("CHATBOT_LLM_AUTH_MODE", "bearer_env"),
        llm_api_key_env=llm_api_key_env,
        llm_api_key_available=bool(source.get(llm_api_key_env, "").strip()),
        service_metrics_path=source.get("CHATBOT_VALIDATION_SERVICE_METRICS_PATH", ""),
    )


def _normalize_target(raw: str) -> tuple[str, bool]:
    if raw.startswith("https://"):
        return raw.removeprefix("https://"), True
    if raw.startswith("http://"):
        return raw.removeprefix("http://"), False
    return raw, False


def _recommendation_service_target(source: dict[str, str]) -> str:
    return source.get("RECOMMENDATION_SERVICE_GRPC_ADDR", "").strip() or source.get(
        "RECOMMENDATION_SERVICE_URL",
        "",
    ).strip()


def _recommendation_service_default_tls(target: str) -> bool:
    target = target.strip()
    return target.startswith("https://") or target.endswith(":443")


def _env_bool(source: dict[str, str], name: str, default: bool) -> bool:
    raw = source.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
