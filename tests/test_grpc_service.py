import grpc
import pytest

from chatbot_service.config import ChatbotConfig
from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.domain.schemas import ChatbotAnswer, ChatbotCard
from chatbot_service.grpc_service import build_chatbot_servicer
from chatbot_service.server import load_generated_chatbot_grpc
from chatbot_service.storage.memory_repository import InMemoryConversationRepository


class AbortError(RuntimeError):
    def __init__(self, code, details):
        super().__init__(details)
        self.code = code
        self.details = details


class FakeContext:
    def __init__(self, metadata=None) -> None:
        self._metadata = [("x-user-id", "user_123")] if metadata is None else metadata

    def invocation_metadata(self):
        return self._metadata

    async def abort(self, code, details):
        raise AbortError(code, details)


class FakePipeline:
    def __init__(self) -> None:
        self.request = None
        self.caller = None

    async def ask(self, request, caller):
        self.request = request
        self.caller = caller
        return ChatbotAnswer(
            conversation_id="conversation_1",
            message_id="message_1",
            intent=ChatbotIntent.RECOMMEND_BEVERAGE,
            answer="추천 결과 기준으로는 테스트 위스키가 잘 맞아요.",
            confidence=0.91,
            profile_status="PROFILE_STATUS_ACTIVE",
            cards=[
                ChatbotCard(
                    card_type="CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION",
                    title="테스트 위스키",
                    detail={
                        "beverage_recommendation": {
                            "result_id": "result_1",
                            "beverage_id": "bev_1",
                            "name_ko": "테스트 위스키",
                        }
                    },
                )
            ],
            used_sources={"beverage_result_ids": ["result_1"]},
        )


def _config() -> ChatbotConfig:
    return ChatbotConfig(
        service_addr=":9100",
        auth_mode="validate_token",
        auth_user_id_metadata_key="x-user-id",
        auth_authorization_metadata_key="authorization",
        auth_service_url="",
        recommendation_service_url="recommendation:9090",
        recommendation_service_grpc_tls=False,
        recommendation_service_serverless_auth_mode="none",
        recommendation_service_serverless_audience="",
        recommendation_service_serverless_token_env="GOOGLE_ID_TOKEN",
        map_service_url="",
        llm_provider="none",
        llm_model="",
        llm_endpoint_url="",
        llm_auth_mode="bearer_env",
        llm_api_key_env="HF_TOKEN",
        llm_serverless_auth_mode="none",
        llm_serverless_audience="",
        llm_serverless_token_env="GOOGLE_ID_TOKEN",
        llm_timeout_ms=8000,
        llm_temperature=0.2,
        llm_max_tokens=512,
        default_language="ko",
        max_retrieved_candidates=5,
        min_confidence=0.55,
        require_grounded_facts=True,
        cache_backend="memory",
        cache_redis_url="",
        cache_profile_status_ttl_sec=300,
        cache_beverage_recommendations_ttl_sec=300,
        cache_venue_recommendations_ttl_sec=120,
        cache_prompt_context_ttl_sec=120,
        cache_location_bucket_precision=3,
        store_conversations=True,
        db_dsn="postgres://example",
        storage_retention_days=365,
        async_conversation_persistence=True,
        persistence_queue_max_size=1000,
        persistence_retry_attempts=3,
        metrics_snapshot_path="",
    )


def _servicer(pipeline=None, repository=None):
    generated = load_generated_chatbot_grpc()
    return (
        build_chatbot_servicer(
            generated.chatbot_pb2_grpc.ChatbotServiceServicer,
            _config(),
            generated.chatbot_pb2,
            pipeline or FakePipeline(),
            repository,
        ),
        generated.chatbot_pb2,
    )


@pytest.mark.anyio
async def test_ask_chatbot_resolves_metadata_and_returns_proto_response():
    pipeline = FakePipeline()
    servicer, pb2 = _servicer(pipeline=pipeline)

    response = await servicer.AskChatbot(
        pb2.AskChatbotRequest(
            message="내 취향에 맞는 술 추천해줘",
            screen_context=pb2.SCREEN_CONTEXT_HOME,
            budget_mode=pb2.BUDGET_MODE_STRICT,
        ),
        FakeContext(metadata=[("x-user-id", "user_123"), ("authorization", "Bearer token")]),
    )

    assert pipeline.caller.user_id == "user_123"
    assert pipeline.request.screen_context == "SCREEN_CONTEXT_HOME"
    assert pipeline.request.budget_mode == "BUDGET_MODE_STRICT"
    assert response.intent == pb2.CHATBOT_INTENT_RECOMMEND_BEVERAGE
    assert response.cards[0].beverage_recommendation.result_id == "result_1"
    assert list(response.used_sources.beverage_result_ids) == ["result_1"]


@pytest.mark.anyio
async def test_ask_chatbot_does_not_trust_client_context_user_id():
    pipeline = FakePipeline()
    servicer, pb2 = _servicer(pipeline=pipeline)
    request = pb2.AskChatbotRequest(message="내 취향에 맞는 술 추천해줘")
    request.client_context.update({"user_id": "attacker_user"})

    await servicer.AskChatbot(
        request,
        FakeContext(metadata=[("x-user-id", "trusted_user"), ("authorization", "Bearer token")]),
    )

    assert pipeline.caller.user_id == "trusted_user"
    assert pipeline.request.client_context == {"user_id": "attacker_user"}


@pytest.mark.anyio
async def test_ask_chatbot_rejects_missing_authenticated_user_metadata():
    servicer, pb2 = _servicer()

    with pytest.raises(AbortError) as exc_info:
        await servicer.AskChatbot(
            pb2.AskChatbotRequest(message="추천해줘"),
            FakeContext(metadata=[]),
        )

    assert exc_info.value.code == grpc.StatusCode.UNAUTHENTICATED


@pytest.mark.anyio
async def test_get_conversation_and_feedback_are_scoped_to_authenticated_user():
    repository = InMemoryConversationRepository()
    conversation_id = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    message_id = await repository.append_message(
        conversation_id,
        "ASSISTANT",
        "답변",
        {"intent": "RECOMMEND_BEVERAGE"},
    )
    servicer, pb2 = _servicer(repository=repository)

    conversation = await servicer.GetConversation(
        pb2.GetConversationRequest(conversation_id=conversation_id),
        FakeContext(
            metadata=[("x-user-id", "user_123"), ("authorization", "Bearer token")]
        ),
    )
    feedback = await servicer.RecordChatbotFeedback(
        pb2.RecordChatbotFeedbackRequest(
            message_id=message_id,
            event_type=pb2.CHATBOT_FEEDBACK_EVENT_TYPE_HELPFUL,
            idempotency_key="idem-1",
        ),
        FakeContext(
            metadata=[("x-user-id", "user_123"), ("authorization", "Bearer token")]
        ),
    )

    assert conversation.messages[0].message_id == message_id
    assert conversation.messages[0].intent == pb2.CHATBOT_INTENT_RECOMMEND_BEVERAGE
    assert feedback.recorded is True
    assert feedback.duplicate is False

    other_user_conversation = await servicer.GetConversation(
        pb2.GetConversationRequest(conversation_id=conversation_id),
        FakeContext(
            metadata=[("x-user-id", "other_user"), ("authorization", "Bearer token")]
        ),
    )
    assert list(other_user_conversation.messages) == []

    with pytest.raises(AbortError) as exc_info:
        await servicer.RecordChatbotFeedback(
            pb2.RecordChatbotFeedbackRequest(
            message_id=message_id,
            event_type=pb2.CHATBOT_FEEDBACK_EVENT_TYPE_HELPFUL,
            idempotency_key="idem-2",
        ),
        FakeContext(
            metadata=[("x-user-id", "other_user"), ("authorization", "Bearer token")]
        ),
    )

    assert exc_info.value.code == grpc.StatusCode.INVALID_ARGUMENT


@pytest.mark.anyio
async def test_get_conversation_without_id_returns_latest_for_user():
    repository = InMemoryConversationRepository()
    home_conversation = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    board_conversation = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_BOARD",
    )
    message_id = await repository.append_message(
        conversation_id=board_conversation,
        role="ASSISTANT",
        content="latest",
        metadata={"intent": "RECOMMEND_BEVERAGE"},
    )

    servicer, pb2 = _servicer(repository=repository)

    response = await servicer.GetConversation(
        pb2.GetConversationRequest(),
        FakeContext(
            metadata=[("x-user-id", "user_123"), ("authorization", "Bearer token")]
        ),
    )
    assert response.conversation_id == board_conversation
    assert len(response.messages) == 1
    assert response.messages[0].message_id == message_id

    home = await servicer.GetConversation(
        pb2.GetConversationRequest(conversation_id=home_conversation),
        FakeContext(
            metadata=[("x-user-id", "user_123"), ("authorization", "Bearer token")]
        ),
    )
    assert home.conversation_id == home_conversation
