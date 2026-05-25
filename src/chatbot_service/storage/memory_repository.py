from __future__ import annotations

from typing import Any
from uuid import uuid4


class InMemoryConversationRepository:
    """Test-only repository with the production repository protocol."""

    def __init__(self) -> None:
        self.conversations: dict[str, dict[str, Any]] = {}
        self.messages: dict[str, dict[str, Any]] = {}
        self.traces: dict[str, dict[str, Any]] = {}
        self.feedback: dict[tuple[str, str], dict[str, Any]] = {}

    async def create_or_get_conversation(
        self,
        user_id: str,
        conversation_id: str | None,
        screen_context: str = "SCREEN_CONTEXT_UNSPECIFIED",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if conversation_id and conversation_id in self.conversations:
            conversation = self.conversations[conversation_id]
            if conversation["user_id"] != user_id:
                raise ValueError("conversation_id was not found")
            return conversation_id
        new_id = conversation_id or str(uuid4())
        self.conversations[new_id] = {
            "user_id": user_id,
            "screen_context": screen_context,
            "metadata": metadata or {},
        }
        return new_id

    async def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any],
        message_id: str | None = None,
    ) -> str:
        new_message_id = message_id or str(uuid4())
        self.messages[new_message_id] = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "metadata": metadata,
        }
        return new_message_id

    async def store_retrieval_trace(self, message_id: str, trace: dict[str, Any]) -> None:
        self.traces[message_id] = trace

    async def get_messages(
        self,
        user_id: str,
        conversation_id: str,
        page_size: int,
        page_token: str,
    ) -> tuple[list[dict[str, Any]], str]:
        conversation = self.conversations.get(conversation_id)
        if not conversation or conversation["user_id"] != user_id:
            return [], ""
        offset = int(page_token or "0")
        matching = [
            {"message_id": message_id, **message}
            for message_id, message in self.messages.items()
            if message["conversation_id"] == conversation_id
        ]
        limit = max(1, page_size or 50)
        page = matching[offset : offset + limit]
        next_offset = offset + limit
        next_token = str(next_offset) if next_offset < len(matching) else ""
        return page, next_token

    async def record_feedback(
        self,
        user_id: str,
        message_id: str,
        event_type: str,
        idempotency_key: str,
        metadata: dict[str, Any],
    ) -> tuple[str, bool]:
        message = self.messages.get(message_id)
        if message is None:
            raise ValueError("message_id was not found")
        conversation = self.conversations.get(str(message["conversation_id"]))
        if not conversation or conversation["user_id"] != user_id:
            raise ValueError("message_id was not found")
        key = (message_id, idempotency_key)
        duplicate = key in self.feedback
        feedback_id = self.feedback.get(key, {}).get("feedback_id", str(uuid4()))
        self.feedback[key] = {
            "feedback_id": feedback_id,
            "event_type": event_type,
            "metadata": metadata,
        }
        return feedback_id, duplicate
