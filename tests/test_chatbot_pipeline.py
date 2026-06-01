import pytest

from chatbot_service.domain.schemas import (
    CallerContext,
    ChatbotRequest,
    ChatbotResponseStatus,
)
from chatbot_service.pipeline.chatbot_pipeline import ChatbotPipeline
from chatbot_service.pipeline.context_builder import RecommendationContextBuilder
from chatbot_service.pipeline.guardrails import Guardrails
from chatbot_service.pipeline.intent_classifier import IntentClassifier
from chatbot_service.pipeline.llm_adapter import LLMGenerationError
from chatbot_service.pipeline.prompt_builder import PromptBuilder
from chatbot_service.pipeline.response_builder import ResponseBuilder
from chatbot_service.pipeline.response_verifier import ResponseVerifier
from chatbot_service.storage.memory_repository import InMemoryConversationRepository


class FakeRecommendationClient:
    def __init__(
        self,
        *,
        profile_status="PROFILE_STATUS_ACTIVE",
        beverage_recommendations=None,
    ):
        self.profile_status = profile_status
        self.beverage_recommendations = beverage_recommendations
        self.profile_calls = []
        self.beverage_calls = []
        self.venue_calls = []

    async def get_profile_status(self, auth_metadata):
        self.profile_calls.append(auth_metadata)
        return {"status": self.profile_status, "profile_revision": 7}

    async def get_beverage_recommendations(self, auth_metadata, **filters):
        self.beverage_calls.append((auth_metadata, filters))
        if self.beverage_recommendations is not None:
            return {
                "request_id": "bev_req_1",
                "recommendations": self.beverage_recommendations,
            }
        return {
            "request_id": "bev_req_1",
            "recommendations": [
                {
                    "rank": 1,
                    "result_id": "bev_result_1",
                    "beverage_id": "bev_1",
                    "name_ko": "테스트 위스키",
                    "name_en": "Test Whisky",
                    "category": "whiskey",
                    "score": 0.91,
                    "reason_codes": ["MATCHES_PROFILE"],
                    "explanation": "취향 프로필과 잘 맞아요.",
                    "metadata": {"source": "recommendation-service"},
                },
                {
                    "rank": 2,
                    "result_id": "bev_result_2",
                    "beverage_id": "bev_2",
                    "name_ko": "테스트 진",
                    "name_en": "Test Gin",
                    "category": "gin",
                    "score": 0.82,
                    "reason_codes": ["MATCHES_PROFILE"],
                    "explanation": "향 취향과 잘 맞아요.",
                    "metadata": {"source": "recommendation-service"},
                }
            ],
        }

    async def get_venue_recommendations(self, auth_metadata, lat, lng, **filters):
        self.venue_calls.append((auth_metadata, lat, lng, filters))
        return {
            "request_id": "venue_req_1",
            "recommendations": [
                {
                    "rank": 1,
                    "result_id": "venue_result_1",
                    "beverage_id": filters.get("selected_beverage_id", ""),
                    "beverage_name": "테스트 위스키",
                    "place_id": "place_1",
                    "name": "테스트 바틀샵",
                    "place_type": "bottle_shop",
                    "address": "서울시 중구",
                    "option_type": "VENUE_OPTION_TYPE_BEST_PRICE",
                    "distance_m": 320.0,
                    "price_krw": 42000,
                    "availability_status": "VENUE_AVAILABILITY_STATUS_AVAILABLE",
                    "freshness_status": "VENUE_FRESHNESS_STATUS_FRESH",
                    "score": 0.88,
                    "reason_codes": ["BEST_PRICE"],
                    "explanation": "가장 저렴한 구매 선택지예요.",
                    "metadata": {"source": "recommendation-service"},
                },
                {
                    "rank": 2,
                    "result_id": "venue_result_2",
                    "beverage_id": filters.get("selected_beverage_id", ""),
                    "beverage_name": "테스트 위스키",
                    "place_id": "place_2",
                    "name": "테스트 펍",
                    "place_type": "bar",
                    "address": "서울시 종로구",
                    "option_type": "VENUE_OPTION_TYPE_NEAREST_REASONABLE",
                    "distance_m": 180.0,
                    "price_krw": 51000,
                    "availability_status": "VENUE_AVAILABILITY_STATUS_LIKELY_AVAILABLE",
                    "freshness_status": "VENUE_FRESHNESS_STATUS_FRESH",
                    "score": 0.81,
                    "reason_codes": ["NEARBY"],
                    "explanation": "더 가까운 선택지예요.",
                    "metadata": {"source": "recommendation-service"},
                },
            ],
        }

    async def record_recommendation_event(self, auth_metadata, **event):
        return {"interaction_id": "interaction_1", "duplicate": False}


class RecordingLLM:
    def __init__(self):
        self.calls = []

    async def generate(self, system_prompt, context_json, user_message):
        self.calls.append((system_prompt, context_json, user_message))
        return "추천 서비스 결과 기준으로는 테스트 위스키가 가장 잘 맞아요."


class RaisingLLM:
    def __init__(self):
        self.calls = []

    async def generate(self, system_prompt, context_json, user_message):
        self.calls.append((system_prompt, context_json, user_message))
        raise LLMGenerationError("LLM unavailable")


def _pipeline(llm, repository=None, recommendation_client=None):
    return ChatbotPipeline(
        intent_classifier=IntentClassifier(),
        context_builder=RecommendationContextBuilder(
            recommendation_client or FakeRecommendationClient()
        ),
        guardrails=Guardrails(),
        prompt_builder=PromptBuilder(),
        llm_adapter=llm,
        response_verifier=ResponseVerifier(),
        response_builder=ResponseBuilder(),
        conversation_repository=repository,
    )


@pytest.mark.anyio
async def test_pipeline_uses_recommendation_candidates_for_cards():
    llm = RecordingLLM()
    repository = InMemoryConversationRepository()
    recommendation_client = FakeRecommendationClient()
    answer = await _pipeline(llm, repository, recommendation_client=recommendation_client).ask(
        ChatbotRequest(message="내 취향에 맞는 술 추천해줘"),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer access-token"},
        ),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    assert [card.title for card in answer.cards] == ["테스트 위스키", "테스트 진"]
    assert answer.cards[0].detail["beverage_recommendation"]["result_id"] == "bev_result_1"
    assert answer.used_sources["beverage_recommendation_request_id"] == "bev_req_1"
    assert answer.used_sources["beverage_result_ids"] == ["bev_result_1", "bev_result_2"]
    assert len(llm.calls) == 1
    assert '"user_profile_status": "ACTIVE"' in llm.calls[0][1]
    assert '"recommendation_id": "bev_result_1"' in llm.calls[0][1]
    assert '"name": "테스트 위스키"' in llm.calls[0][1]
    assert recommendation_client.profile_calls[0]["authorization"] == "Bearer access-token"
    auth_metadata, filters = recommendation_client.beverage_calls[0]
    assert auth_metadata["authorization"] == "Bearer access-token"
    assert filters["profile_revision"] == 7
    assert len(repository.messages) == 2
    assistant_message = repository.messages[answer.message_id]
    assert assistant_message["metadata"]["used_sources"]["beverage_result_ids"] == [
        "bev_result_1",
        "bev_result_2",
    ]
    assert repository.traces[answer.message_id]["used_sources"]["beverage_result_ids"] == [
        "bev_result_1",
        "bev_result_2",
    ]


@pytest.mark.anyio
async def test_pipeline_returns_no_answer_without_location_for_venue():
    llm = RecordingLLM()
    answer = await _pipeline(llm).ask(
        ChatbotRequest(message="근처에서 살 수 있는 곳 알려줘", selected_beverage_id="bev_1"),
        CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"}),
    )

    assert answer.status == ChatbotResponseStatus.INSUFFICIENT_DATA
    assert answer.missing_facts == ["detailed_location"]
    assert llm.calls == []


@pytest.mark.anyio
async def test_pipeline_uses_venue_cards_for_nearby_sources():
    llm = RecordingLLM()
    answer = await _pipeline(llm).ask(
        ChatbotRequest(
            message="근처에서 살 수 있는 곳 알려줘",
            selected_beverage_id="bev_1",
            lat=37.5,
            lng=127.0,
            radius_m=1500,
        ),
        CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"}),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    assert [card.card_type for card in answer.cards] == [
        "CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION",
        "CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION",
    ]
    assert [
        card.detail["venue_recommendation"]["result_id"] for card in answer.cards
    ] == ["venue_result_1", "venue_result_2"]
    assert answer.used_sources["venue_recommendation_request_id"] == "venue_req_1"
    assert answer.used_sources["venue_result_ids"] == ["venue_result_1", "venue_result_2"]


@pytest.mark.anyio
async def test_pipeline_uses_purchase_option_cards_for_comparison_sources():
    llm = RecordingLLM()
    answer = await _pipeline(llm).ask(
        ChatbotRequest(
            message="가격 비교해줘",
            selected_beverage_id="bev_1",
            lat=37.5,
            lng=127.0,
            radius_m=1500,
        ),
        CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"}),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    assert [card.card_type for card in answer.cards] == [
        "CHATBOT_CARD_TYPE_PURCHASE_OPTION",
        "CHATBOT_CARD_TYPE_PURCHASE_OPTION",
    ]
    assert [
        card.detail["purchase_option"]["result_id"] for card in answer.cards
    ] == ["venue_result_1", "venue_result_2"]
    assert answer.used_sources["venue_recommendation_request_id"] == "venue_req_1"
    assert answer.used_sources["venue_result_ids"] == ["venue_result_1", "venue_result_2"]


@pytest.mark.anyio
async def test_pipeline_returns_profile_fallback_without_llm_when_profile_missing():
    llm = RecordingLLM()
    recommendation_client = FakeRecommendationClient(profile_status="PROFILE_STATUS_MISSING")

    answer = await _pipeline(llm, recommendation_client=recommendation_client).ask(
        ChatbotRequest(message="내 취향에 맞는 술 추천해줘"),
        CallerContext(
            user_id="trusted_user",
            metadata={"x-user-id": "trusted_user", "authorization": "Bearer token"},
        ),
    )

    assert answer.status == ChatbotResponseStatus.INSUFFICIENT_DATA
    assert answer.intent == "PROFILE_STATUS"
    assert answer.profile_status == "PROFILE_STATUS_MISSING"
    assert "추천 프로필" in answer.answer
    assert answer.missing_facts == ["active_recommendation_profile"]
    assert llm.calls == []
    assert recommendation_client.beverage_calls == []


@pytest.mark.anyio
async def test_pipeline_returns_no_answer_when_recommendation_service_has_no_candidates():
    llm = RecordingLLM()
    recommendation_client = FakeRecommendationClient(beverage_recommendations=[])

    answer = await _pipeline(llm, recommendation_client=recommendation_client).ask(
        ChatbotRequest(message="내 취향에 맞는 술 추천해줘"),
        CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"}),
    )

    assert answer.status == ChatbotResponseStatus.INSUFFICIENT_DATA
    assert answer.cards == []
    assert answer.missing_facts == ["beverage_recommendation_candidates"]
    assert llm.calls == []


@pytest.mark.anyio
async def test_pipeline_returns_grounded_cards_when_llm_is_unavailable():
    llm = RaisingLLM()

    answer = await _pipeline(llm).ask(
        ChatbotRequest(message="내 취향에 맞는 술 추천해줘"),
        CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"}),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    assert "테스트 위스키" in answer.answer
    assert [card.title for card in answer.cards] == ["테스트 위스키", "테스트 진"]
    assert answer.used_sources["beverage_result_ids"] == ["bev_result_1", "bev_result_2"]
    assert len(llm.calls) == 1


@pytest.mark.anyio
async def test_pipeline_refuses_out_of_scope_without_recommendation_or_llm_calls():
    llm = RecordingLLM()
    recommendation_client = FakeRecommendationClient()

    answer = await _pipeline(llm, recommendation_client=recommendation_client).ask(
        ChatbotRequest(message="오늘 서울 날씨 알려줘"),
        CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"}),
    )

    assert answer.status == ChatbotResponseStatus.REFUSED
    assert answer.refused is True
    assert answer.refusal_reason == "OUT_OF_SCOPE"
    assert llm.calls == []
    assert recommendation_client.profile_calls == []
