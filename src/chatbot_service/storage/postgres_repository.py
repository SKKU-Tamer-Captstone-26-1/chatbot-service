from __future__ import annotations

import json
from typing import Any


class PostgresConversationRepository:
    """PostgreSQL implementation for chatbot-owned conversation storage."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("CHATBOT_DB_DSN is required when conversation storage is enabled")
        self._dsn = dsn
        self._pool: Any | None = None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def create_or_get_conversation(
        self,
        user_id: str,
        conversation_id: str | None,
        screen_context: str = "SCREEN_CONTEXT_UNSPECIFIED",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        pool = await self._get_pool()
        metadata_json = json.dumps(metadata or {})
        async with pool.acquire() as connection:
            if conversation_id:
                existing = await connection.fetchrow(
                    """
                    SELECT id::text, external_user_id
                    FROM chatbot_conversations
                    WHERE id = $1::uuid
                    """,
                    conversation_id,
                )
                if existing:
                    if str(existing["external_user_id"]) != user_id:
                        raise ValueError("conversation_id was not found")
                    return str(existing["id"])
            row = await connection.fetchrow(
                """
                INSERT INTO chatbot_conversations (
                    id,
                    external_user_id,
                    screen_context,
                    metadata_json
                )
                VALUES (COALESCE($1::uuid, gen_random_uuid()), $2, $3, $4::jsonb)
                RETURNING id::text
                """,
                conversation_id,
                user_id,
                screen_context,
                metadata_json,
            )
            return str(row["id"])

    async def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any],
        message_id: str | None = None,
    ) -> str:
        pool = await self._get_pool()
        metadata_json = json.dumps(metadata)
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO chatbot_messages (
                    id,
                    conversation_id,
                    role,
                    content,
                    intent,
                    confidence,
                    refused,
                    refusal_reason,
                    metadata_json
                )
                VALUES (
                    COALESCE($1::uuid, gen_random_uuid()),
                    $2::uuid,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    $8,
                    $9::jsonb
                )
                RETURNING id::text
                """,
                message_id,
                conversation_id,
                role,
                content,
                str(metadata.get("intent", "CHATBOT_INTENT_UNSPECIFIED")),
                float(metadata.get("confidence", 0.0) or 0.0),
                bool(metadata.get("refused", False)),
                str(metadata.get("refusal_reason", "")),
                metadata_json,
            )
            return str(row["id"])

    async def store_retrieval_trace(self, message_id: str, trace: dict[str, Any]) -> None:
        pool = await self._get_pool()
        used_sources = dict(trace.get("used_sources", {}) or {})
        missing_facts = list(trace.get("missing_facts", []) or [])
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO chatbot_retrieval_traces (
                    message_id,
                    recommendation_request_id,
                    beverage_recommendation_request_id,
                    venue_recommendation_request_id,
                    profile_revision,
                    profile_status,
                    used_sources_json,
                    missing_facts_json,
                    prompt_context_hash,
                    prompt_version,
                    model_provider,
                    model_name
                )
                VALUES (
                    $1::uuid, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11, $12
                )
                """,
                message_id,
                str(used_sources.get("recommendation_request_id", "")),
                str(used_sources.get("beverage_recommendation_request_id", "")),
                str(used_sources.get("venue_recommendation_request_id", "")),
                int(used_sources.get("profile_revision", 0) or 0),
                str(trace.get("profile_status") or used_sources.get("profile_status", "")),
                json.dumps(used_sources),
                json.dumps(missing_facts),
                str(trace.get("prompt_context_hash", "")),
                str(trace.get("prompt_version", "")),
                str(trace.get("model_provider", "")),
                str(trace.get("model_name", "")),
            )

    async def get_messages(
        self,
        user_id: str,
        conversation_id: str,
        page_size: int,
        page_token: str,
    ) -> tuple[list[dict[str, Any]], str]:
        pool = await self._get_pool()
        offset = int(page_token or "0")
        limit = max(1, min(page_size or 50, 100))
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    m.id::text AS message_id,
                    m.conversation_id::text AS conversation_id,
                    m.role,
                    m.content,
                    m.intent,
                    m.confidence,
                    m.refused,
                    m.refusal_reason,
                    m.metadata_json,
                    m.created_at
                FROM chatbot_messages m
                JOIN chatbot_conversations c ON c.id = m.conversation_id
                WHERE m.conversation_id = $1::uuid
                  AND c.external_user_id = $2
                ORDER BY m.created_at ASC, m.id ASC
                LIMIT $3 OFFSET $4
                """,
                conversation_id,
                user_id,
                limit + 1,
                offset,
            )
        page_rows = rows[:limit]
        next_token = str(offset + limit) if len(rows) > limit else ""
        return [dict(row) for row in page_rows], next_token

    async def record_feedback(
        self,
        user_id: str,
        message_id: str,
        event_type: str,
        idempotency_key: str,
        metadata: dict[str, Any],
    ) -> tuple[str, bool]:
        pool = await self._get_pool()
        metadata_json = json.dumps(metadata)
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO chatbot_feedback_events (
                    message_id,
                    event_type,
                    idempotency_key,
                    metadata_json
                )
                SELECT m.id, $2, $3, $4::jsonb
                FROM chatbot_messages m
                JOIN chatbot_conversations c ON c.id = m.conversation_id
                WHERE m.id = $1::uuid
                  AND c.external_user_id = $5
                ON CONFLICT (message_id, idempotency_key)
                DO UPDATE SET metadata_json = chatbot_feedback_events.metadata_json
                RETURNING id::text, (xmax <> 0) AS duplicate
                """,
                message_id,
                event_type,
                idempotency_key,
                metadata_json,
                user_id,
            )
            if row is None:
                raise ValueError("message_id was not found")
            return str(row["id"]), bool(row["duplicate"])

    async def _get_pool(self) -> Any:
        if self._pool is None:
            try:
                import asyncpg
            except ModuleNotFoundError as exc:
                raise RuntimeError("asyncpg is required for PostgreSQL storage") from exc
            self._pool = await asyncpg.create_pool(dsn=self._dsn)
        return self._pool
