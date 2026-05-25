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
from chatbot_service.pipeline.prompt_builder import PromptBuilder
from chatbot_service.pipeline.response_builder import ResponseBuilder
from chatbot_service.pipeline.response_verifier import ResponseVerifier
from chatbot_service.storage.memory_repository import InMemoryConversationRepository


class FakeRecommendationClient:
    async def get_profile_status(self, auth_metadata):
        return {"status": "PROFILE_STATUS_ACTIVE", "profile_revision": 7}

    async def get_beverage_recommendations(self, auth_metadata, **filters):
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
                }
            ],
        }

    async def get_venue_recommendations(self, auth_metadata, lat, lng, **filters):
        return {"request_id": "venue_req_1", "recommendations": []}

    async def record_recommendation_event(self, auth_metadata, **event):
        return {"interaction_id": "interaction_1", "duplicate": False}


class RecordingLLM:
    def __init__(self):
        self.calls = []

    async def generate(self, system_prompt, context_json, user_message):
        self.calls.append((system_prompt, context_json, user_message))
        return "추천 서비스 결과 기준으로는 테스트 위스키가 가장 잘 맞아요."


def _pipeline(llm, repository=None):
    return ChatbotPipeline(
        intent_classifier=IntentClassifier(),
        context_builder=RecommendationContextBuilder(FakeRecommendationClient()),
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
    answer = await _pipeline(llm, repository).ask(
        ChatbotRequest(message="내 취향에 맞는 술 추천해줘"),
        CallerContext(user_id="user_123", metadata={"x-user-id": "user_123"}),
    )

    assert answer.status == ChatbotResponseStatus.ANSWERED
    assert answer.cards[0].title == "테스트 위스키"
    assert answer.cards[0].detail["beverage_recommendation"]["result_id"] == "bev_result_1"
    assert answer.used_sources["beverage_recommendation_request_id"] == "bev_req_1"
    assert answer.used_sources["beverage_result_ids"] == ["bev_result_1"]
    assert len(llm.calls) == 1
    assert len(repository.messages) == 2


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
