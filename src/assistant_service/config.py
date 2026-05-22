"""Configuration contract for ai-assistant-service.

This is a skeleton only. Do not add real secrets here.
"""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AssistantConfig:
    service_addr: str
    auth_service_url: str
    recommendation_service_url: str
    map_service_url: str
    llm_provider: str
    llm_model: str
    default_language: str
    min_confidence: float
    store_conversations: bool


def load_config() -> AssistantConfig:
    return AssistantConfig(
        service_addr=os.getenv("ASSISTANT_SERVICE_ADDR", ":9100"),
        auth_service_url=os.getenv("AUTH_SERVICE_URL", ""),
        recommendation_service_url=os.getenv("RECOMMENDATION_SERVICE_URL", ""),
        map_service_url=os.getenv("MAP_SERVICE_URL", ""),
        llm_provider=os.getenv("ASSISTANT_LLM_PROVIDER", "none"),
        llm_model=os.getenv("ASSISTANT_LLM_MODEL", ""),
        default_language=os.getenv("ASSISTANT_DEFAULT_LANGUAGE", "ko"),
        min_confidence=float(os.getenv("ASSISTANT_MIN_CONFIDENCE", "0.55")),
        store_conversations=os.getenv("ASSISTANT_STORE_CONVERSATIONS", "true").lower() == "true",
    )
