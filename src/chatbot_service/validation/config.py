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
        service_metrics_path=source.get("CHATBOT_VALIDATION_SERVICE_METRICS_PATH", ""),
    )


def _normalize_target(raw: str) -> tuple[str, bool]:
    if raw.startswith("https://"):
        return raw.removeprefix("https://"), True
    if raw.startswith("http://"):
        return raw.removeprefix("http://"), False
    return raw, False


def _env_bool(source: dict[str, str], name: str, default: bool) -> bool:
    raw = source.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
