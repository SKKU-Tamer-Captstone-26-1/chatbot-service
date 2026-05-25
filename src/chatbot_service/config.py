"""Configuration contract for ai-chatbot-service.

This is a skeleton only. Do not add real secrets here.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatbotConfig:
    service_addr: str
    auth_mode: str
    auth_user_id_metadata_key: str
    auth_authorization_metadata_key: str
    auth_service_url: str
    recommendation_service_url: str
    map_service_url: str
    llm_provider: str
    llm_model: str
    llm_endpoint_url: str
    llm_api_key_env: str
    llm_timeout_ms: int
    llm_temperature: float
    llm_max_tokens: int
    default_language: str
    max_retrieved_candidates: int
    min_confidence: float
    require_grounded_facts: bool
    cache_backend: str
    cache_redis_url: str
    cache_profile_status_ttl_sec: int
    cache_beverage_recommendations_ttl_sec: int
    cache_venue_recommendations_ttl_sec: int
    cache_prompt_context_ttl_sec: int
    cache_location_bucket_precision: int
    store_conversations: bool
    db_dsn: str
    storage_retention_days: int
    async_conversation_persistence: bool
    persistence_queue_max_size: int
    persistence_retry_attempts: int


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> ChatbotConfig:
    return ChatbotConfig(
        service_addr=os.getenv("CHATBOT_SERVICE_ADDR", ":9100"),
        auth_mode=os.getenv("CHATBOT_AUTH_MODE", "validate_token"),
        auth_user_id_metadata_key=os.getenv("CHATBOT_AUTH_USER_ID_METADATA_KEY", "x-user-id"),
        auth_authorization_metadata_key=os.getenv(
            "CHATBOT_AUTH_AUTHORIZATION_METADATA_KEY",
            "authorization",
        ),
        auth_service_url=os.getenv("AUTH_SERVICE_URL", ""),
        recommendation_service_url=os.getenv("RECOMMENDATION_SERVICE_URL", ""),
        map_service_url=os.getenv("MAP_SERVICE_URL", ""),
        llm_provider=os.getenv("CHATBOT_LLM_PROVIDER", "none"),
        llm_model=os.getenv("CHATBOT_LLM_MODEL", ""),
        llm_endpoint_url=os.getenv("CHATBOT_LLM_ENDPOINT_URL", ""),
        llm_api_key_env=os.getenv("CHATBOT_LLM_API_KEY_ENV", "HF_TOKEN"),
        llm_timeout_ms=int(os.getenv("CHATBOT_LLM_TIMEOUT_MS", "8000")),
        llm_temperature=float(os.getenv("CHATBOT_LLM_TEMPERATURE", "0.2")),
        llm_max_tokens=int(os.getenv("CHATBOT_LLM_MAX_TOKENS", "512")),
        default_language=os.getenv("CHATBOT_DEFAULT_LANGUAGE", "ko"),
        max_retrieved_candidates=int(os.getenv("CHATBOT_MAX_RETRIEVED_CANDIDATES", "5")),
        min_confidence=float(os.getenv("CHATBOT_MIN_CONFIDENCE", "0.55")),
        require_grounded_facts=_env_bool("CHATBOT_REQUIRE_GROUNDED_FACTS", True),
        cache_backend=os.getenv("CHATBOT_CACHE_BACKEND", "memory"),
        cache_redis_url=os.getenv("CHATBOT_CACHE_REDIS_URL", ""),
        cache_profile_status_ttl_sec=int(os.getenv("CHATBOT_CACHE_PROFILE_STATUS_TTL_SEC", "300")),
        cache_beverage_recommendations_ttl_sec=int(
            os.getenv("CHATBOT_CACHE_BEVERAGE_RECOMMENDATIONS_TTL_SEC", "300")
        ),
        cache_venue_recommendations_ttl_sec=int(
            os.getenv("CHATBOT_CACHE_VENUE_RECOMMENDATIONS_TTL_SEC", "120")
        ),
        cache_prompt_context_ttl_sec=int(os.getenv("CHATBOT_CACHE_PROMPT_CONTEXT_TTL_SEC", "120")),
        cache_location_bucket_precision=int(
            os.getenv("CHATBOT_CACHE_LOCATION_BUCKET_PRECISION", "3")
        ),
        store_conversations=_env_bool("CHATBOT_STORE_CONVERSATIONS", True),
        db_dsn=os.getenv("CHATBOT_DB_DSN", ""),
        storage_retention_days=int(os.getenv("CHATBOT_STORAGE_RETENTION_DAYS", "365")),
        async_conversation_persistence=_env_bool("CHATBOT_ASYNC_CONVERSATION_PERSISTENCE", True),
        persistence_queue_max_size=int(os.getenv("CHATBOT_PERSISTENCE_QUEUE_MAX_SIZE", "1000")),
        persistence_retry_attempts=int(os.getenv("CHATBOT_PERSISTENCE_RETRY_ATTEMPTS", "3")),
    )
