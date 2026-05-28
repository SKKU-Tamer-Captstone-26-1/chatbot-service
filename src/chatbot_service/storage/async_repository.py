from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from chatbot_service.metrics import MetricsRecorder
from chatbot_service.storage.conversation_repository import ConversationRepository

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PersistenceOperation:
    name: str
    factory: Callable[[], Awaitable[object]]


class AsyncConversationRepository:
    """Bounded async write wrapper for chatbot conversation persistence.

    `AskChatbot` can return stable conversation/message IDs without waiting for
    every audit log write. Reads and feedback drain pending writes first because
    those calls directly observe persisted state.
    """

    def __init__(
        self,
        inner: ConversationRepository,
        *,
        queue_max_size: int = 1000,
        retry_attempts: int = 3,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._inner = inner
        self._queue: asyncio.Queue[_PersistenceOperation | None] = asyncio.Queue(
            maxsize=max(1, queue_max_size)
        )
        self._retry_attempts = max(1, retry_attempts)
        self._metrics = metrics or MetricsRecorder()
        self._worker_task: asyncio.Task[None] | None = None
        self._known_conversations: set[tuple[str, str]] = set()
        self.dead_letters: list[tuple[str, str]] = []

    async def create_or_get_conversation(
        self,
        user_id: str,
        conversation_id: str | None,
        screen_context: str = "SCREEN_CONTEXT_UNSPECIFIED",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if conversation_id and (user_id, conversation_id) not in self._known_conversations:
            verified_id = await self._inner.create_or_get_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
                screen_context=screen_context,
                metadata=metadata,
            )
            self._known_conversations.add((user_id, verified_id))
            return verified_id

        stable_conversation_id = conversation_id or str(uuid4())
        self._known_conversations.add((user_id, stable_conversation_id))
        self._enqueue(
            _PersistenceOperation(
                name="create_or_get_conversation",
                factory=lambda: self._inner.create_or_get_conversation(
                    user_id=user_id,
                    conversation_id=stable_conversation_id,
                    screen_context=screen_context,
                    metadata=metadata,
                ),
            )
        )
        return stable_conversation_id

    async def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any],
        message_id: str | None = None,
    ) -> str:
        stable_message_id = message_id or str(uuid4())
        self._enqueue(
            _PersistenceOperation(
                name="append_message",
                factory=lambda: self._inner.append_message(
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    metadata=metadata,
                    message_id=stable_message_id,
                ),
            )
        )
        return stable_message_id

    async def store_retrieval_trace(self, message_id: str, trace: dict[str, Any]) -> None:
        self._enqueue(
            _PersistenceOperation(
                name="store_retrieval_trace",
                factory=lambda: self._inner.store_retrieval_trace(message_id, trace),
            )
        )

    async def get_messages(
        self,
        user_id: str,
        conversation_id: str,
        page_size: int,
        page_token: str,
    ) -> tuple[list[dict[str, Any]], str]:
        await self.drain()
        return await self._inner.get_messages(
            user_id=user_id,
            conversation_id=conversation_id,
            page_size=page_size,
            page_token=page_token,
        )

    async def record_feedback(
        self,
        user_id: str,
        message_id: str,
        event_type: str,
        idempotency_key: str,
        metadata: dict[str, Any],
    ) -> tuple[str, bool]:
        await self.drain()
        return await self._inner.record_feedback(
            user_id=user_id,
            message_id=message_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    async def drain(self) -> None:
        if self._worker_task is None:
            return
        await self._queue.join()

    async def close(self) -> None:
        if self._worker_task is not None:
            await self.drain()
            await self._queue.put(None)
            await self._worker_task
            self._worker_task = None
        close = getattr(self._inner, "close", None)
        if close is not None:
            await close()

    def _enqueue(self, operation: _PersistenceOperation) -> None:
        self._ensure_worker()
        try:
            self._queue.put_nowait(operation)
            self._metrics.increment("storage.queue_enqueued", operation=operation.name)
            self._metrics.observe("storage.queue_depth", float(self._queue.qsize()))
        except asyncio.QueueFull:
            self._metrics.increment("storage.queue_full", operation=operation.name)
            self._metrics.observe("storage.queue_depth", float(self._queue.qsize()))
            self.dead_letters.append((operation.name, "queue_full"))
            LOGGER.error("chatbot persistence queue is full; operation=%s", operation.name)

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        while True:
            operation = await self._queue.get()
            try:
                if operation is None:
                    return
                await self._run_with_retry(operation)
            finally:
                self._queue.task_done()
                self._metrics.observe("storage.queue_depth", float(self._queue.qsize()))

    async def _run_with_retry(self, operation: _PersistenceOperation) -> None:
        for attempt in range(1, self._retry_attempts + 1):
            try:
                with self._metrics.timer("storage.write", operation=operation.name):
                    await operation.factory()
                self._metrics.increment("storage.write_success", operation=operation.name)
                return
            except Exception as exc:
                if attempt >= self._retry_attempts:
                    self._metrics.increment("storage.write_dead_letter", operation=operation.name)
                    self.dead_letters.append((operation.name, str(exc)))
                    LOGGER.exception(
                        "chatbot persistence operation failed permanently; operation=%s",
                        operation.name,
                    )
                    return
                self._metrics.increment("storage.write_retry", operation=operation.name)
                await asyncio.sleep(0)


__all__ = ["AsyncConversationRepository"]
