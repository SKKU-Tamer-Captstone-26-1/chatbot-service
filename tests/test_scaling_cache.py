import asyncio

import pytest

from chatbot_service.cache import InMemoryCache
from chatbot_service.clients.cached_recommendation_client import (
    CachingRecommendationClient,
    RecommendationCacheSettings,
    _location_bucket,
)
from chatbot_service.domain.schemas import CallerContext, ChatbotRequest
from chatbot_service.metrics import MetricsRecorder
from chatbot_service.pipeline.chatbot_pipeline import ChatbotPipeline
from chatbot_service.pipeline.context_builder import RecommendationContextBuilder
from chatbot_service.pipeline.guardrails import Guardrails
from chatbot_service.pipeline.intent_classifier import IntentClassifier
from chatbot_service.pipeline.prompt_builder import PromptBuilder
from chatbot_service.pipeline.response_builder import ResponseBuilder
from chatbot_service.pipeline.response_verifier import ResponseVerifier
from chatbot_service.storage.async_repository import AsyncConversationRepository
from chatbot_service.storage.memory_repository import InMemoryConversationRepository


class CountingRecommendationClient:
    def __init__(self) -> None:
        self.profile_calls = 0
        self.beverage_calls = 0
        self.venue_calls = 0

    async def get_profile_status(self, auth_metadata):
        self.profile_calls += 1
        await asyncio.sleep(0)
        return {"status": "PROFILE_STATUS_ACTIVE", "profile_revision": 7}

    async def get_beverage_recommendations(self, auth_metadata, **filters):
        self.beverage_calls += 1
        await asyncio.sleep(0)
        return {
            "request_id": "bev_req_1",
            "recommendations": [
                {
                    "rank": 1,
                    "result_id": "bev_result_1",
                    "beverage_id": "bev_1",
                    "name_ko": "테스트 위스키",
                    "category": "whiskey",
                    "score": 0.91,
                    "reason_codes": ["MATCHES_PROFILE"],
                    "explanation": "취향 프로필과 잘 맞아요.",
                }
            ],
        }

    async def get_venue_recommendations(self, auth_metadata, lat, lng, **filters):
        self.venue_calls += 1
        await asyncio.sleep(0)
        return {
            "request_id": "venue_req_1",
            "recommendations": [
                {
                    "rank": 1,
                    "result_id": "venue_result_1",
                    "place_id": "place_1",
                    "name": "테스트 바",
                    "distance_m": 120.0,
                    "availability_status": "VENUE_AVAILABILITY_STATUS_AVAILABLE",
                    "freshness_status": "VENUE_FRESHNESS_STATUS_FRESH",
                    "score": 0.83,
                    "reason_codes": ["NEARBY"],
                }
            ],
        }

    async def record_recommendation_event(self, auth_metadata, **event):
        return {"duplicate": False}


class RecordingLLM:
    def __init__(self) -> None:
        self.contexts: list[str] = []

    async def generate(self, system_prompt, context_json, user_message):
        self.contexts.append(context_json)
        return "추천 서비스 결과 기준으로는 테스트 위스키가 가장 잘 맞아요."


def _cached_client(inner, cache=None, metrics=None):
    return CachingRecommendationClient(
        inner,
        cache or InMemoryCache(),
        RecommendationCacheSettings(
            user_id_metadata_key="x-user-id",
            profile_status_ttl_sec=300,
            beverage_recommendations_ttl_sec=300,
            venue_recommendations_ttl_sec=120,
            location_bucket_precision=3,
        ),
        metrics or MetricsRecorder(),
    )


def _pipeline(recommendation_client, llm, cache, metrics):
    return ChatbotPipeline(
        intent_classifier=IntentClassifier(),
        context_builder=RecommendationContextBuilder(recommendation_client),
        guardrails=Guardrails(),
        prompt_builder=PromptBuilder(),
        llm_adapter=llm,
        response_verifier=ResponseVerifier(),
        response_builder=ResponseBuilder(),
        metrics=metrics,
        prompt_context_cache=cache,
        prompt_context_cache_ttl_sec=120,
    )


@pytest.mark.anyio
async def test_recommendation_cache_reuses_profile_and_beverage_results_without_reranking():
    inner = CountingRecommendationClient()
    metrics = MetricsRecorder()
    client = _cached_client(inner, metrics=metrics)
    auth_metadata = {"x-user-id": "user_123"}

    first = await client.get_profile_status(auth_metadata)
    second = await client.get_profile_status(auth_metadata)
    beverage_first = await client.get_beverage_recommendations(
        auth_metadata,
        profile_revision=7,
        category="whiskey",
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
    )
    beverage_second = await client.get_beverage_recommendations(
        auth_metadata,
        profile_revision=7,
        category="whiskey",
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
    )

    assert first == second
    assert beverage_first == beverage_second
    assert beverage_second["recommendations"][0]["result_id"] == "bev_result_1"
    assert inner.profile_calls == 1
    assert inner.beverage_calls == 1
    counters = metrics.snapshot()["counters"]
    assert counters["recommendation.cache_hit|operation=profile_status"] == 1
    assert counters["recommendation.cache_hit|operation=beverage_recommendations"] == 1


@pytest.mark.anyio
async def test_venue_cache_uses_location_bucket_instead_of_exact_coordinates():
    inner = CountingRecommendationClient()
    client = _cached_client(inner)
    auth_metadata = {"x-user-id": "user_123"}

    first = await client.get_venue_recommendations(
        auth_metadata,
        lat=37.50011,
        lng=127.10011,
        profile_revision=7,
        selected_beverage_id="bev_1",
        radius_m=1000,
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
    )
    second = await client.get_venue_recommendations(
        auth_metadata,
        lat=37.50012,
        lng=127.10012,
        profile_revision=7,
        selected_beverage_id="bev_1",
        radius_m=1000,
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
    )

    assert _location_bucket(37.50011, 127.10011, 3) == "37.500,127.100"
    assert first == second
    assert inner.venue_calls == 1


@pytest.mark.anyio
async def test_beverage_cache_distinguishes_diversity_filters_and_session_context():
    inner = CountingRecommendationClient()
    client = _cached_client(inner)
    auth_metadata = {"x-user-id": "user_123"}

    await client.get_beverage_recommendations(
        auth_metadata,
        profile_revision=7,
        category="whiskey",
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
        exclude_beverage_ids=["bev_2", "bev_1"],
        diversity_mode="DIFFERENT_STYLE",
        session_context_id="conv-1",
    )
    await client.get_beverage_recommendations(
        auth_metadata,
        profile_revision=7,
        category="whiskey",
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
        exclude_beverage_ids=["bev_1", "bev_2"],
        diversity_mode="DIFFERENT_STYLE",
        session_context_id="conv-1",
    )
    await client.get_beverage_recommendations(
        auth_metadata,
        profile_revision=7,
        category="whiskey",
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
        exclude_beverage_ids=["bev_2", "bev_1"],
        diversity_mode="DIFFERENT_STYLE",
        session_context_id="conv-2",
    )

    assert inner.beverage_calls == 2


@pytest.mark.anyio
async def test_venue_cache_includes_diversity_context_filters():
    inner = CountingRecommendationClient()
    client = _cached_client(inner)
    auth_metadata = {"x-user-id": "user_123"}

    await client.get_venue_recommendations(
        auth_metadata,
        lat=37.50011,
        lng=127.10011,
        profile_revision=7,
        selected_beverage_id="bev_1",
        radius_m=1000,
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
        exclude_result_ids=["v1", "v2"],
        diversity_mode="DIFFERENT_STYLE",
        session_context_id="conv-1",
    )
    await client.get_venue_recommendations(
        auth_metadata,
        lat=37.50011,
        lng=127.10011,
        profile_revision=7,
        selected_beverage_id="bev_1",
        radius_m=1000,
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
        exclude_result_ids=["v2", "v1"],
        diversity_mode="DIFFERENT_STYLE",
        session_context_id="conv-1",
    )
    await client.get_venue_recommendations(
        auth_metadata,
        lat=37.50011,
        lng=127.10011,
        profile_revision=7,
        selected_beverage_id="bev_1",
        radius_m=1000,
        budget_mode="BUDGET_MODE_SOFT",
        limit=3,
        exclude_result_ids=["v1", "v2"],
        diversity_mode="MORE_LIKE_THIS",
        session_context_id="conv-1",
    )

    assert inner.venue_calls == 2


@pytest.mark.anyio
async def test_concurrent_identical_requests_singleflight_recommendation_cache():
    inner = CountingRecommendationClient()
    client = _cached_client(inner)
    auth_metadata = {"x-user-id": "user_123"}

    await asyncio.gather(
        *[
            client.get_beverage_recommendations(
                auth_metadata,
                profile_revision=7,
                category="whiskey",
                budget_mode="BUDGET_MODE_SOFT",
                limit=3,
            )
            for _ in range(500)
        ]
    )

    assert inner.beverage_calls == 1


@pytest.mark.anyio
async def test_pipeline_caches_prompt_context_and_records_metrics():
    cache = InMemoryCache()
    metrics = MetricsRecorder()
    llm = RecordingLLM()
    pipeline = _pipeline(
        CountingRecommendationClient(),
        llm,
        cache,
        metrics,
    )
    caller = CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"})

    await pipeline.ask(ChatbotRequest(message="내 취향에 맞는 술 추천해줘"), caller)
    await pipeline.ask(ChatbotRequest(message="내 취향에 맞는 술 추천해줘"), caller)

    assert len(llm.contexts) == 2
    assert llm.contexts[0] == llm.contexts[1]
    counters = metrics.snapshot()["counters"]
    assert counters["prompt_context.cache_miss"] == 1
    assert counters["prompt_context.cache_hit"] == 1
    assert "chatbot.ask|status=ANSWERED" in metrics.snapshot()["timers"]


@pytest.mark.anyio
async def test_async_conversation_repository_defers_writes_but_preserves_ids():
    inner = InMemoryConversationRepository()
    metrics = MetricsRecorder()
    repository = AsyncConversationRepository(inner, metrics=metrics)

    conversation_id = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    message_id = await repository.append_message(
        conversation_id=conversation_id,
        role="ASSISTANT",
        content="답변",
        metadata={"intent": "RECOMMEND_BEVERAGE"},
    )
    await repository.store_retrieval_trace(
        message_id,
        {"used_sources": {"beverage_ids": ["bev_1"]}},
    )

    assert inner.messages == {}
    await repository.drain()

    assert conversation_id in inner.conversations
    assert message_id in inner.messages
    assert message_id in inner.traces
    queue_depth = metrics.snapshot()["timers"]["storage.queue_depth"]
    assert queue_depth.count >= 3
    assert queue_depth.max >= 1
    feedback_id, duplicate = await repository.record_feedback(
        user_id="user_123",
        message_id=message_id,
        event_type="HELPFUL",
        idempotency_key="idem-1",
        metadata={},
    )
    assert feedback_id
    assert duplicate is False
    await repository.close()


@pytest.mark.anyio
async def test_stale_venue_facts_preserve_service_result_but_are_not_cached():
    class StaleVenueClient(CountingRecommendationClient):
        async def get_venue_recommendations(self, auth_metadata, lat, lng, **filters):
            self.venue_calls += 1
            return {
                "request_id": "venue_req_stale",
                "recommendations": [
                    {
                        "rank": 1,
                        "result_id": "venue_result_stale",
                        "place_id": "place_stale",
                        "name": "오래된 장소",
                        "distance_m": 120.0,
                        "freshness_status": "VENUE_FRESHNESS_STATUS_EXPIRED",
                        "availability_status": "VENUE_AVAILABILITY_STATUS_AVAILABLE",
                        "score": 0.83,
                    }
                ],
            }

    inner = StaleVenueClient()
    client = _cached_client(inner)
    caller = CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"})
    pipeline = _pipeline(client, RecordingLLM(), InMemoryCache(), MetricsRecorder())

    answer = await pipeline.ask(
        ChatbotRequest(
            message="근처에서 살 수 있는 곳 알려줘",
            selected_beverage_id="bev_1",
            lat=37.5,
            lng=127.1,
        ),
        caller,
    )
    await client.get_venue_recommendations(
        {"x-user-id": "user_123"},
        lat=37.5,
        lng=127.1,
        profile_revision=7,
        selected_beverage_id="bev_1",
        radius_m=0,
        budget_mode="BUDGET_MODE_UNSPECIFIED",
        limit=0,
    )

    assert answer.status == "ANSWERED"
    assert answer.cards[0].title == "오래된 장소"
    assert inner.venue_calls == 2
