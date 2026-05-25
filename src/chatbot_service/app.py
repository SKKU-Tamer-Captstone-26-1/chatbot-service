from __future__ import annotations

from chatbot_service.cache import Cache, build_cache
from chatbot_service.clients.cached_recommendation_client import (
    CachingRecommendationClient,
    RecommendationCacheSettings,
)
from chatbot_service.clients.recommendation_client import RecommendationClient
from chatbot_service.config import ChatbotConfig
from chatbot_service.metrics import MetricsRecorder
from chatbot_service.pipeline.chatbot_pipeline import ChatbotPipeline
from chatbot_service.pipeline.context_builder import RecommendationContextBuilder
from chatbot_service.pipeline.guardrails import Guardrails
from chatbot_service.pipeline.intent_classifier import IntentClassifier
from chatbot_service.pipeline.llm_adapter import LLMAdapter, build_llm_adapter
from chatbot_service.pipeline.prompt_builder import PromptBuilder
from chatbot_service.pipeline.response_builder import ResponseBuilder
from chatbot_service.pipeline.response_verifier import ResponseVerifier
from chatbot_service.storage.async_repository import AsyncConversationRepository
from chatbot_service.storage.conversation_repository import ConversationRepository
from chatbot_service.storage.postgres_repository import PostgresConversationRepository


def build_chatbot_pipeline(
    config: ChatbotConfig,
    recommendation_client: RecommendationClient,
    *,
    llm_adapter: LLMAdapter | None = None,
    conversation_repository: ConversationRepository | None = None,
    cache: Cache | None = None,
    metrics: MetricsRecorder | None = None,
) -> ChatbotPipeline:
    metrics = metrics or MetricsRecorder()
    cache = cache or build_cache(config)
    recommendation_client = CachingRecommendationClient(
        recommendation_client,
        cache,
        RecommendationCacheSettings(
            user_id_metadata_key=config.auth_user_id_metadata_key,
            profile_status_ttl_sec=config.cache_profile_status_ttl_sec,
            beverage_recommendations_ttl_sec=config.cache_beverage_recommendations_ttl_sec,
            venue_recommendations_ttl_sec=config.cache_venue_recommendations_ttl_sec,
            location_bucket_precision=config.cache_location_bucket_precision,
        ),
        metrics,
    )
    repository = conversation_repository
    if repository is None and config.store_conversations:
        repository = build_conversation_repository(config, metrics=metrics)

    return ChatbotPipeline(
        intent_classifier=IntentClassifier(),
        context_builder=RecommendationContextBuilder(recommendation_client),
        guardrails=Guardrails(),
        prompt_builder=PromptBuilder(),
        llm_adapter=llm_adapter or build_llm_adapter(config),
        response_verifier=ResponseVerifier(),
        response_builder=ResponseBuilder(),
        conversation_repository=repository,
        metrics=metrics,
        prompt_context_cache=cache,
        prompt_context_cache_ttl_sec=config.cache_prompt_context_ttl_sec,
    )


def build_conversation_repository(
    config: ChatbotConfig,
    *,
    metrics: MetricsRecorder | None = None,
) -> ConversationRepository | None:
    if not config.store_conversations:
        return None
    repository: ConversationRepository = PostgresConversationRepository(config.db_dsn)
    if config.async_conversation_persistence:
        repository = AsyncConversationRepository(
            repository,
            queue_max_size=config.persistence_queue_max_size,
            retry_attempts=config.persistence_retry_attempts,
            metrics=metrics,
        )
    return repository
