"""ChatbotService gRPC servicer implementation."""

from __future__ import annotations

from typing import Any

from chatbot_service.clients.auth_client import AuthMetadataError, AuthMetadataResolver
from chatbot_service.config import ChatbotConfig
from chatbot_service.pipeline.chatbot_pipeline import ChatbotPipeline
from chatbot_service.proto_converters import (
    answer_to_proto,
    conversation_message_to_proto,
    request_from_proto,
    struct_to_dict,
)
from chatbot_service.storage.conversation_repository import ConversationRepository


def build_chatbot_servicer(
    servicer_base: type[Any],
    config: ChatbotConfig,
    chatbot_pb2: Any,
    pipeline: ChatbotPipeline,
    conversation_repository: ConversationRepository | None,
    auth_resolver: AuthMetadataResolver | None = None,
) -> Any:
    """Create a generated ChatbotServiceServicer implementation.

    The generated base class is passed in at runtime so this module can be
    imported before protobuf code generation has run.
    """

    auth_resolver = auth_resolver or AuthMetadataResolver(config)

    class ChatbotServicer(servicer_base):  # type: ignore[misc, valid-type]
        async def AskChatbot(self, request: Any, context: Any) -> Any:
            import grpc

            try:
                caller = auth_resolver.resolve(context.invocation_metadata())
                chatbot_request = request_from_proto(request, chatbot_pb2)
                answer = await pipeline.ask(chatbot_request, caller)
                return answer_to_proto(answer, chatbot_pb2)
            except AuthMetadataError as exc:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc))
            except ValueError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
            except grpc.RpcError as exc:
                await context.abort(grpc.StatusCode.UNAVAILABLE, exc.details() or str(exc))

        async def GetConversation(self, request: Any, context: Any) -> Any:
            import grpc

            try:
                caller = auth_resolver.resolve(context.invocation_metadata())
                if conversation_repository is None:
                    await context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION,
                        "Conversation storage is disabled.",
                    )
                conversation_id = request.conversation_id
                if not conversation_id:
                    conversation_id = await conversation_repository.get_latest_conversation_id_for_user(
                        user_id=caller.user_id,
                        screen_context="SCREEN_CONTEXT_UNSPECIFIED",
                    )
                if not conversation_id:
                    return chatbot_pb2.GetConversationResponse(
                        conversation_id="",
                        messages=[],
                        next_page_token="",
                    )
                messages, next_page_token = await conversation_repository.get_messages(
                    user_id=caller.user_id,
                    conversation_id=conversation_id,
                    page_size=request.page_size,
                    page_token=request.page_token,
                )
                return chatbot_pb2.GetConversationResponse(
                    conversation_id=conversation_id,
                    messages=[
                        conversation_message_to_proto(message, chatbot_pb2)
                        for message in messages
                    ],
                    next_page_token=next_page_token,
                )
            except AuthMetadataError as exc:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc))
            except ValueError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        async def RecordChatbotFeedback(self, request: Any, context: Any) -> Any:
            import grpc

            try:
                caller = auth_resolver.resolve(context.invocation_metadata())
                if conversation_repository is None:
                    await context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION,
                        "Conversation storage is disabled.",
                    )
                if not request.message_id:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "message_id is required")
                if not request.idempotency_key:
                    await context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "idempotency_key is required",
                    )
                event_type = chatbot_pb2.ChatbotFeedbackEventType.Name(request.event_type)
                _, duplicate = await conversation_repository.record_feedback(
                    user_id=caller.user_id,
                    message_id=request.message_id,
                    event_type=event_type,
                    idempotency_key=request.idempotency_key,
                    metadata=struct_to_dict(request.metadata),
                )
                return chatbot_pb2.RecordChatbotFeedbackResponse(
                    recorded=True,
                    duplicate=duplicate,
                )
            except AuthMetadataError as exc:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc))
            except ValueError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

    return ChatbotServicer()


__all__ = ["build_chatbot_servicer"]
