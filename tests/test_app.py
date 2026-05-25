from chatbot_service.app import build_chatbot_pipeline
from chatbot_service.config import load_config
from chatbot_service.pipeline.chatbot_pipeline import ChatbotPipeline
from chatbot_service.pipeline.llm_adapter import NoopLLMAdapter
from chatbot_service.storage.memory_repository import InMemoryConversationRepository


class FakeRecommendationClient:
    async def get_profile_status(self, auth_metadata):
        return {"status": "PROFILE_STATUS_ACTIVE"}

    async def get_beverage_recommendations(self, auth_metadata, **filters):
        return {"recommendations": []}

    async def get_venue_recommendations(self, auth_metadata, lat, lng, **filters):
        return {"recommendations": []}

    async def record_recommendation_event(self, auth_metadata, **event):
        return {"duplicate": False}


def test_build_chatbot_pipeline_accepts_injected_dependencies(monkeypatch):
    monkeypatch.setenv("CHATBOT_STORE_CONVERSATIONS", "false")
    config = load_config()

    pipeline = build_chatbot_pipeline(
        config,
        FakeRecommendationClient(),
        llm_adapter=NoopLLMAdapter(),
        conversation_repository=InMemoryConversationRepository(),
    )

    assert isinstance(pipeline, ChatbotPipeline)
