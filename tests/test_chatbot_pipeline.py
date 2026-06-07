import pytest

from chatbot_service.clients.recommendation_client import RecommendationClientError
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
                    "metadata": {
                        "source": {
                            "catalog_key": "catalog:test-whisky",
                            "price_min_krw": 15000,
                            "price_max_krw": 25000,
                            "price_observation_summary": "검증된 카탈로그 가격 관측값",
                            "price_policy": "verified_krw_observations_not_live_truth",
                        }
                    },
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


class UnavailableRecommendationClient(FakeRecommendationClient):
    async def get_profile_status(self, auth_metadata):
        self.profile_calls.append(auth_metadata)
        raise RecommendationClientError("unavailable")


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
    assert '"price_min_krw": 15000' in llm.calls[0][1]
    assert '"price_policy": "verified_krw_observations_not_live_truth"' in llm.calls[0][1]
    assert "검증된 가격 관측값과 사람들의 경험적 의견" in answer.answer
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
async def test_pipeline_routes_place_recommendation_to_venue_not_beverage():
    llm = RecordingLLM()
    recommendation_client = FakeRecommendationClient()

    answer = await _pipeline(llm, recommendation_client=recommendation_client).ask(
        ChatbotRequest(message="장소 추천해줘"),
        CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"}),
    )

    assert answer.status == ChatbotResponseStatus.INSUFFICIENT_DATA
    assert answer.intent == "INSUFFICIENT_DATA"
    assert answer.cards == []
    assert answer.missing_facts == ["detailed_location", "selected_beverage_id"]
    assert "장소 추천" in answer.answer
    assert recommendation_client.profile_calls
    assert recommendation_client.beverage_calls == []
    assert recommendation_client.venue_calls == []
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
async def test_pipeline_returns_deterministic_fallback_when_recommendation_service_unavailable():
    llm = RecordingLLM()
    recommendation_client = UnavailableRecommendationClient()

    answer = await _pipeline(llm, recommendation_client=recommendation_client).ask(
        ChatbotRequest(message="내 취향에 맞는 술 추천해줘"),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
        ),
    )

    assert answer.status == ChatbotResponseStatus.INSUFFICIENT_DATA
    assert answer.refusal_reason == "RECOMMENDATION_SERVICE_UNAVAILABLE"
    assert answer.missing_facts == ["recommendation_service_unavailable"]
    assert "추천 데이터를 일시적으로 불러오지 못했어요" in answer.answer
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


@pytest.mark.anyio
async def test_pipeline_forwards_diversity_context_on_follow_up_request():
    llm = RecordingLLM()
    recommendation_client = FakeRecommendationClient()
    caller = CallerContext(
        user_id="user_123",
        metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
    )
    request = ChatbotRequest(
        message="다른 술 추천해줘",
        client_context={
            "previous_beverage_ids": ["bev_2", "bev_1"],
            "previous_result_ids": ["result_2", "result_1"],
            "session_context_id": "conv-1",
        },
    )

    await _pipeline(llm, recommendation_client=recommendation_client).ask(request, caller)

    auth_metadata, filters = recommendation_client.beverage_calls[0]
    assert auth_metadata["authorization"] == "Bearer token"
    assert sorted(filters["exclude_beverage_ids"]) == ["bev_1", "bev_2"]
    assert sorted(filters["exclude_result_ids"]) == ["result_1", "result_2"]
    assert filters["diversity_mode"] == "DIFFERENT_STYLE"
    assert filters["session_context_id"] == "conv-1"


@pytest.mark.anyio
async def test_pipeline_auto_fills_selected_beverage_from_conversation_for_venue_requests():
    repository = InMemoryConversationRepository()
    conversation_id = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    await repository.append_message(
        conversation_id=conversation_id,
        role="ASSISTANT",
        content="추천 결과",
        metadata={
            "used_sources": {
                "beverage_ids": ["bev_prev"],
                "beverage_result_ids": ["bev_prev_result_1", "bev_prev_result_2"],
            },
            "cards": [
                {
                    "card_type": "CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION",
                    "detail": {
                        "beverage_recommendation": {
                            "beverage_id": "bev_prev",
                            "result_id": "bev_prev_result_1",
                        }
                    },
                }
            ],
        },
    )

    recommendation_client = FakeRecommendationClient()
    llm = RecordingLLM()
    answer = await _pipeline(
        llm,
        repository=repository,
        recommendation_client=recommendation_client,
    ).ask(
        ChatbotRequest(
            message="근처 바를 찾아줘",
            conversation_id=conversation_id,
            lat=37.5,
            lng=127.0,
            radius_m=1000,
        ),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
        ),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    assert recommendation_client.venue_calls
    _, _, _, filters = recommendation_client.venue_calls[0]
    assert filters["selected_beverage_id"] == "bev_prev"


@pytest.mark.anyio
async def test_pipeline_auto_fills_selected_beverage_from_venue_card_when_used_sources_missing():
    repository = InMemoryConversationRepository()
    conversation_id = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    await repository.append_message(
        conversation_id=conversation_id,
        role="ASSISTANT",
        content="이전엔 여기가 좋아서 추천했어요",
        metadata={
            "intent": "FIND_NEARBY_VENUE",
            "cards": [
                {
                    "card_type": "CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION",
                    "detail": {
                        "venue_recommendation": {
                            "beverage_id": "bev_legacy",
                            "result_id": "venue_prev_1",
                        }
                    },
                }
            ],
        },
    )

    recommendation_client = FakeRecommendationClient()
    llm = RecordingLLM()
    answer = await _pipeline(
        llm,
        repository=repository,
        recommendation_client=recommendation_client,
    ).ask(
        ChatbotRequest(
            message="근처 바를 더 보여줘",
            conversation_id=conversation_id,
            lat=37.5,
            lng=127.0,
            radius_m=1000,
        ),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
        ),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    _, _, _, filters = recommendation_client.venue_calls[0]
    assert filters["selected_beverage_id"] == "bev_legacy"


@pytest.mark.anyio
async def test_pipeline_routes_ambiguous_followup_to_venue_when_previous_intent_was_venue():
    repository = InMemoryConversationRepository()
    conversation_id = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    await repository.append_message(
        conversation_id=conversation_id,
        role="ASSISTANT",
        content="최근에는 근처 바를 추천해드렸어요",
        metadata={
            "intent": "FIND_NEARBY_VENUE",
            "used_sources": {
                "beverage_ids": ["bev_prev_2"],
                "beverage_result_ids": ["bev_prev_2_result_1"],
            },
            "cards": [
                {
                    "card_type": "CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION",
                    "detail": {
                        "venue_recommendation": {
                            "beverage_id": "bev_prev_2",
                            "result_id": "venue_prev_1",
                        }
                    },
                }
            ],
        },
    )

    recommendation_client = FakeRecommendationClient()
    llm = RecordingLLM()
    answer = await _pipeline(
        llm,
        repository=repository,
        recommendation_client=recommendation_client,
    ).ask(
        ChatbotRequest(
            message="다른 곳 추천해줘",
            conversation_id=conversation_id,
            lat=37.5,
            lng=127.0,
            radius_m=1000,
        ),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
        ),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    assert recommendation_client.venue_calls
    assert recommendation_client.beverage_calls == []
    _, _, _, filters = recommendation_client.venue_calls[0]
    assert filters["selected_beverage_id"] == "bev_prev_2"


@pytest.mark.anyio
async def test_pipeline_auto_uses_conversation_candidates_for_diverse_beverage_request():
    repository = InMemoryConversationRepository()
    conversation_id = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    await repository.append_message(
        conversation_id=conversation_id,
        role="ASSISTANT",
        content="이전 추천",
        metadata={
            "used_sources": {
                "beverage_ids": ["bev_prev_a", "bev_prev_b"],
                "beverage_result_ids": ["bev_prev_a_1", "bev_prev_b_1"],
            }
        },
    )

    recommendation_client = FakeRecommendationClient()
    llm = RecordingLLM()

    await _pipeline(
        llm,
        repository=repository,
        recommendation_client=recommendation_client,
    ).ask(
        ChatbotRequest(
            message="다른 술 추천해줘",
            conversation_id=conversation_id,
        ),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
        ),
    )

    _, filters = recommendation_client.beverage_calls[0]
    assert filters["exclude_beverage_ids"] == ["bev_prev_a", "bev_prev_b"]
    assert filters["exclude_result_ids"] == ["bev_prev_a_1", "bev_prev_b_1"]


@pytest.mark.anyio
async def test_pipeline_resolves_selected_beverage_from_client_context_for_venue():
    llm = RecordingLLM()
    recommendation_client = FakeRecommendationClient()
    answer = await _pipeline(llm, recommendation_client=recommendation_client).ask(
        ChatbotRequest(
            message="근처 바 추천해줘",
            lat=37.5,
            lng=127.0,
            radius_m=1500,
            client_context={"selected_beverage_id": "bev_context"},
        ),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
        ),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    _, _, _, filters = recommendation_client.venue_calls[0]
    assert filters["selected_beverage_id"] == "bev_context"


@pytest.mark.anyio
async def test_pipeline_forwards_venue_filters_for_diversity_request():
    llm = RecordingLLM()
    recommendation_client = FakeRecommendationClient()
    answer = await _pipeline(llm, recommendation_client=recommendation_client).ask(
        ChatbotRequest(
            message="다른 장소 추천해줘",
            lat=37.5,
            lng=127.0,
            radius_m=1500,
            selected_beverage_id="bev_1",
            client_context={
                "previous_beverage_ids": ["bev_2"],
                "previous_result_ids": ["venue_result_2"],
                "session_context_id": "conv-1",
            },
        ),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
        ),
    )

    _, _, _, filters = recommendation_client.venue_calls[0]
    assert filters["exclude_beverage_ids"] == ["bev_2"]
    assert filters["exclude_result_ids"] == ["venue_result_2"]
    assert filters["session_context_id"] == "conv-1"
    assert filters["diversity_mode"] == "DIFFERENT_STYLE"
    assert answer.status == ChatbotResponseStatus.ANSWERED


@pytest.mark.anyio
async def test_pipeline_auto_fills_selected_beverage_from_purchase_option_card():
    repository = InMemoryConversationRepository()
    conversation_id = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    await repository.append_message(
        conversation_id=conversation_id,
        role="ASSISTANT",
        content="가격 비교를 마쳤어요",
        metadata={
            "intent": "COMPARE_PURCHASE_OPTIONS",
            "cards": [
                {
                    "card_type": "CHATBOT_CARD_TYPE_PURCHASE_OPTION",
                    "detail": {
                        "purchase_option": {
                            "beverage_id": "bev_purchase",
                            "result_id": "venue_prev_2",
                        }
                    },
                }
            ],
        },
    )

    recommendation_client = FakeRecommendationClient()
    llm = RecordingLLM()
    answer = await _pipeline(
        llm,
        repository=repository,
        recommendation_client=recommendation_client,
    ).ask(
        ChatbotRequest(
            message="다른 곳 추천해줘",
            conversation_id=conversation_id,
            lat=37.5,
            lng=127.0,
            radius_m=1000,
        ),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
        ),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    _, _, _, filters = recommendation_client.venue_calls[0]
    assert filters["selected_beverage_id"] == "bev_purchase"


@pytest.mark.anyio
async def test_pipeline_reads_conversation_context_metadata_json_from_storage_rows():
    class MetadataJsonConversationRepository:
        def __init__(self, messages: list[dict[str, object]]) -> None:
            self._messages = messages

        async def create_or_get_conversation(
            self,
            user_id: str,
            conversation_id: str | None,
            screen_context: str = "SCREEN_CONTEXT_UNSPECIFIED",
            metadata: dict[str, object] | None = None,
        ) -> str:
            return conversation_id or "conversation_1"

        async def append_message(
            self,
            conversation_id: str,
            role: str,
            content: str,
            metadata: dict[str, object],
            message_id: str | None = None,
        ) -> str:
            return message_id or "message_1"

        async def store_retrieval_trace(self, message_id: str, trace: dict[str, object]) -> None:
            return None

        async def get_messages(
            self,
            user_id: str,
            conversation_id: str,
            page_size: int,
            page_token: str,
        ) -> tuple[list[dict[str, object]], str]:
            return list(self._messages), ""

    recommendation_client = FakeRecommendationClient()
    llm = RecordingLLM()

    repository = MetadataJsonConversationRepository(
        [
            {
                "message_id": "message_123",
                "role": "ASSISTANT",
                "metadata_json": {
                    "used_sources": {
                        "beverage_ids": ["bev_prev_a", "bev_prev_b"],
                        "beverage_result_ids": ["result_prev_a", "result_prev_b"],
                    },
                    "cards": [
                        {
                            "card_type": "CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION",
                            "detail": {
                                "beverage_recommendation": {
                                    "beverage_id": "bev_prev_a",
                                    "result_id": "result_prev_a",
                                }
                            },
                        }
                    ],
                },
            }
        ]
    )

    await _pipeline(
        llm,
        repository=repository,
        recommendation_client=recommendation_client,
    ).ask(
        ChatbotRequest(
            message="다른 술 추천해줘",
            conversation_id="conversation_1",
        ),
        CallerContext(
            user_id="user_123",
            metadata={"x-user-id": "user_123", "authorization": "Bearer token"},
        ),
    )

    _, filters = recommendation_client.beverage_calls[0]
    assert sorted(filters["exclude_beverage_ids"]) == ["bev_prev_a", "bev_prev_b"]
    assert sorted(filters["exclude_result_ids"]) == ["result_prev_a", "result_prev_b"]
