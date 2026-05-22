"""Conversation persistence skeleton.

MVP should store conversations for traceability and future evaluation, but future
training use requires privacy and consent policy.
"""
from typing import Protocol, Any


class ConversationRepository(Protocol):
    async def create_or_get_conversation(self, user_id: str, conversation_id: str | None) -> str: ...
    async def append_message(self, conversation_id: str, role: str, content: str, metadata: dict[str, Any]) -> str: ...
    async def store_retrieval_trace(self, message_id: str, trace: dict[str, Any]) -> None: ...
