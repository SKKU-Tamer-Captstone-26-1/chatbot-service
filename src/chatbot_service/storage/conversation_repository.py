"""Conversation persistence skeleton.

MVP should store conversations for traceability and future evaluation, but future
training use requires privacy and consent policy.
"""
from typing import Any, Protocol


class ConversationRepository(Protocol):
    async def create_or_get_conversation(
        self,
        user_id: str,
        conversation_id: str | None,
        screen_context: str = "SCREEN_CONTEXT_UNSPECIFIED",
        metadata: dict[str, Any] | None = None,
    ) -> str: ...

    async def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any],
        message_id: str | None = None,
    ) -> str: ...

    async def store_retrieval_trace(self, message_id: str, trace: dict[str, Any]) -> None: ...

    async def get_messages(
        self,
        user_id: str,
        conversation_id: str,
        page_size: int,
        page_token: str,
    ) -> tuple[list[dict[str, Any]], str]: ...

    async def record_feedback(
        self,
        user_id: str,
        message_id: str,
        event_type: str,
        idempotency_key: str,
        metadata: dict[str, Any],
    ) -> tuple[str, bool]: ...
