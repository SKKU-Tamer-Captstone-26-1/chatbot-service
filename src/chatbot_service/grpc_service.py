"""ChatbotService gRPC servicer skeleton.

Phase 1 only wires the gRPC surface. Business logic starts after generated proto
modules and upstream service contracts are available.
"""

from __future__ import annotations

from typing import Any

from chatbot_service.config import ChatbotConfig


def build_chatbot_servicer(servicer_base: type[Any], config: ChatbotConfig) -> Any:
    """Create a generated ChatbotServiceServicer implementation.

    The generated base class is passed in at runtime so this module can be
    imported before protobuf code generation has run.
    """

    class ChatbotServicer(servicer_base):  # type: ignore[misc, valid-type]
        async def AskChatbot(self, request: Any, context: Any) -> Any:
            import grpc

            # TODO(auth-service): resolve caller identity only from Authorization
            # metadata or gateway-authenticated context. Do not trust request body
            # user identifiers.
            # TODO(recommendation-service): fetch profile status, ranked beverage
            # and venue candidates, score breakdowns, and reason codes. The LLM
            # must not rank or rerank results.
            # TODO(map-service): use approved map/place APIs or read models for
            # detailed location, venue, price, inventory, distance, and freshness
            # facts. Do not read canonical map/place databases directly.
            # TODO(LLM): generate only grounded polite Korean text from retrieved
            # facts. If evidence is missing, return an insufficient-data answer.
            await context.abort(
                grpc.StatusCode.UNIMPLEMENTED,
                "AskChatbot pipeline is not implemented in Phase 1.",
            )

        async def GetConversation(self, request: Any, context: Any) -> Any:
            import grpc

            # TODO(storage): add chatbot-owned conversation storage only after
            # storage schema and retention policy are approved.
            await context.abort(
                grpc.StatusCode.UNIMPLEMENTED,
                "GetConversation storage is not implemented in Phase 1.",
            )

        async def RecordChatbotFeedback(self, request: Any, context: Any) -> Any:
            import grpc

            # TODO(storage/evaluation): store chatbot feedback events without
            # using them for training until privacy and consent policy is finalized.
            await context.abort(
                grpc.StatusCode.UNIMPLEMENTED,
                "RecordChatbotFeedback storage is not implemented in Phase 1.",
            )

    return ChatbotServicer()


__all__ = ["build_chatbot_servicer"]
