# Chatbot Storage and Future Learning

## Purpose

This document defines what chatbot conversation data may be stored and how it may later support improvement or training.

## Storage Decision

MVP must store chatbot conversations because future learning and evaluation are
planned. Storage is chatbot-owned PostgreSQL data only; it must not become
canonical survey, recommendation, map, place, menu, inventory, or auth data.

Initial migration:

```text
migrations/001_create_chatbot_storage.sql
```

Run migrations with:

```bash
chatbot-migrate
```

The runner stores applied versions and checksums in
`chatbot_schema_migrations`. Conversation reads and feedback writes must be
scoped to the authenticated user resolved from trusted metadata.

Assistant message metadata stores response cards, `used_sources`,
`missing_facts`, profile status, and prompt context hash so conversation reads
can show traceable chatbot outputs. `chatbot_retrieval_traces` stores the same
source metadata as the audit-grade trace tied to recommendation-service request
and result IDs.

## Hot Path Cost Rule

`AskChatbot` must not load full conversation history from PostgreSQL by default.
Conversation storage exists for audit, evaluation, feedback, and future
learning, not as the primary source for every answer.

For future multi-turn behavior, fetch only the recent messages needed for the
turn or use a rolling summary. Older raw history must not be copied into every
LLM prompt.

Conversation/message/retrieval writes may start synchronous for correctness, but
production should move them to bounded async persistence if Postgres write
latency becomes part of user-visible response latency. See
`docs/chatbot/scaling-and-cache-plan.md`.

## Chatbot-Owned Tables Draft

```text
chatbot_conversations
- id
- external_user_id
- created_at
- updated_at
- screen_context
- metadata_json

chatbot_messages
- id
- conversation_id
- role
- content
- intent
- confidence
- refused
- refusal_reason
- metadata_json
- created_at

chatbot_retrieval_traces
- id
- message_id
- recommendation_request_id
- beverage_recommendation_request_id
- venue_recommendation_request_id
- profile_revision
- profile_status
- used_sources_json
- missing_facts_json
- prompt_context_hash
- prompt_version
- model_provider
- model_name
- created_at

chatbot_feedback_events
- id
- message_id
- event_type
- idempotency_key
- metadata_json
- created_at
```

Recommended retention is currently configurable with
`CHATBOT_STORAGE_RETENTION_DAYS` and defaults to 365 days. The exact production
retention policy still needs confirmation before using stored data for training.

## Privacy and Learning Rules

- Do not store raw secrets.
- Do not store raw survey answers unless explicitly approved.
- Store derived profile references, not raw survey truth.
- Store recommendation request IDs and source metadata for traceability.
- Future training data must filter PII and private user data.
- Conversation data must not be used for training until consent and policy are finalized.
- User input and model output can be retained for model improvement only after
  the product consent, retention, and deletion policy is finalized.
