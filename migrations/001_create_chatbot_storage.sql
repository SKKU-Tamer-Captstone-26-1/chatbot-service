-- Chatbot-owned storage for conversation traceability and future evaluation.
-- This data is not canonical survey, recommendation, map, place, menu, or
-- inventory data.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS chatbot_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_user_id TEXT NOT NULL,
    screen_context TEXT NOT NULL DEFAULT 'SCREEN_CONTEXT_UNSPECIFIED',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chatbot_conversations_user_created_at
    ON chatbot_conversations (external_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chatbot_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chatbot_conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    intent TEXT NOT NULL DEFAULT 'CHATBOT_INTENT_UNSPECIFIED',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    refused BOOLEAN NOT NULL DEFAULT false,
    refusal_reason TEXT NOT NULL DEFAULT '',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chatbot_messages_conversation_created_at
    ON chatbot_messages (conversation_id, created_at ASC);

CREATE TABLE IF NOT EXISTS chatbot_retrieval_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES chatbot_messages(id) ON DELETE CASCADE,
    recommendation_request_id TEXT NOT NULL DEFAULT '',
    beverage_recommendation_request_id TEXT NOT NULL DEFAULT '',
    venue_recommendation_request_id TEXT NOT NULL DEFAULT '',
    profile_revision INTEGER NOT NULL DEFAULT 0,
    profile_status TEXT NOT NULL DEFAULT 'PROFILE_STATUS_UNSPECIFIED',
    used_sources_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    missing_facts_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    prompt_context_hash TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    model_provider TEXT NOT NULL DEFAULT '',
    model_name TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chatbot_retrieval_traces_message_id
    ON chatbot_retrieval_traces (message_id);

CREATE TABLE IF NOT EXISTS chatbot_feedback_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES chatbot_messages(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL DEFAULT '',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (message_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_chatbot_feedback_events_message_created_at
    ON chatbot_feedback_events (message_id, created_at DESC);
