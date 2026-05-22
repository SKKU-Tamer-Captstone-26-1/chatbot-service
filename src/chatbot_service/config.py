"""Configuration contract for ai-chatbot-service.

This is a skeleton only. Do not add real secrets here.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatbotConfig:
    service_addr: str
    auth_mode: str
    auth_service_url: str
    recommendation_service_url: str
    map_service_url: str
    llm_provider: str
    llm_model: str
    llm_timeout_ms: int
    llm_temperature: float
    default_language: str
    max_retrieved_candidates: int
    min_confidence: float
    require_grounded_facts: bool
    store_conversations: bool
    db_dsn: str


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> ChatbotConfig:
    return ChatbotConfig(
        service_addr=os.getenv("CHATBOT_SERVICE_ADDR", ":9100"),
        auth_mode=os.getenv("CHATBOT_AUTH_MODE", "validate_token"),
        auth_service_url=os.getenv("AUTH_SERVICE_URL", ""),
        recommendation_service_url=os.getenv("RECOMMENDATION_SERVICE_URL", ""),
        map_service_url=os.getenv("MAP_SERVICE_URL", ""),
        llm_provider=os.getenv("CHATBOT_LLM_PROVIDER", "none"),
        llm_model=os.getenv("CHATBOT_LLM_MODEL", ""),
        llm_timeout_ms=int(os.getenv("CHATBOT_LLM_TIMEOUT_MS", "8000")),
        llm_temperature=float(os.getenv("CHATBOT_LLM_TEMPERATURE", "0.2")),
        default_language=os.getenv("CHATBOT_DEFAULT_LANGUAGE", "ko"),
        max_retrieved_candidates=int(os.getenv("CHATBOT_MAX_RETRIEVED_CANDIDATES", "5")),
        min_confidence=float(os.getenv("CHATBOT_MIN_CONFIDENCE", "0.55")),
        require_grounded_facts=_env_bool("CHATBOT_REQUIRE_GROUNDED_FACTS", True),
        store_conversations=_env_bool("CHATBOT_STORE_CONVERSATIONS", True),
        db_dsn=os.getenv("CHATBOT_DB_DSN", ""),
    )
