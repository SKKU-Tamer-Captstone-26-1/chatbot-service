# Chatbot Storage and Future Learning

## Purpose

This document defines what chatbot conversation data may be stored and how it
may later support evaluation, rule improvement, prompt improvement, and future
training after policy approval.

## Storage Decision

MVP must store chatbot conversations because evaluation and future learning are
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

## Retention Policy

Default retention is controlled by `CHATBOT_STORAGE_RETENTION_DAYS` and remains
365 days unless product/legal policy sets a shorter value.

Production policy:

- Keep chatbot conversations, messages, retrieval traces, and feedback events
  for at most `CHATBOT_STORAGE_RETENTION_DAYS`.
- Use the same retention window for `chatbot_conversations`,
  `chatbot_messages`, `chatbot_retrieval_traces`, and
  `chatbot_feedback_events` unless a narrower table-specific policy is approved.
- Do not keep data indefinitely for future model training.
- Do not extend retention only because data may be useful for ML.
- Retention purge must delete or irreversibly anonymize rows after the configured
  retention window.
- Before production launch, add a scheduled purge job or database maintenance
  process. Until that exists, production retention is a known operational gap.

Recommended purge order:

1. Delete expired `chatbot_feedback_events`.
2. Delete expired `chatbot_retrieval_traces`.
3. Delete expired `chatbot_messages`.
4. Delete expired `chatbot_conversations` with no remaining messages.

The purge job must log counts and age ranges only. It must not log message
content, raw metadata, JWTs, or secrets.

## Privacy Policy

Allowed stored data:

- Authenticated external user ID used for ownership and audit.
- User chatbot message text.
- Assistant chatbot response text.
- Chatbot intent, response status, confidence, refusal reason, and missing facts.
- Recommendation request IDs, result IDs, beverage IDs, venue/place IDs, reason
  codes, profile revision, and profile status returned by service APIs.
- UI card metadata returned by chatbot-service.
- Feedback event type, idempotency key, and non-sensitive feedback metadata.

Forbidden stored data:

- Raw JWTs, refresh tokens, access tokens, service account keys, API keys, or
  bearer headers.
- Raw survey answers as canonical truth.
- Auth DB rows, survey DB rows, map/place DB rows, or recommendation DB rows.
- Full canonical inventory, menu, price, or place records copied from owner DBs.
- Payment data, government IDs, contact lists, or unrelated personal data.
- LLM provider secrets or Cloud Run ID tokens.

Metadata rules:

- `metadata_json` and `used_sources_json` may contain source IDs and returned
  recommendation facts only.
- `client_context` may be stored only as app hints. It must not be trusted as
  user identity and must not contain tokens.
- If a future client sends sensitive data in `client_context`, the gateway or
  chatbot-service must redact or drop it before persistence.

## User Deletion And Export

Deletion:

- User deletion requests must remove chatbot-owned rows linked to the external
  user ID.
- Deletion must cover conversations, messages, retrieval traces, and feedback.
- Deletion must not attempt to delete canonical data owned by auth, survey,
  recommendation, map, or place services.
- For audit, the deletion job may record aggregate counts and job status without
  storing message content.

Export:

- User export should include chatbot-owned conversations and assistant responses
  tied to the user.
- Export should include user-visible cards and high-level source references.
- Export should not include raw internal prompts, auth metadata, raw JWTs,
  secrets, or hidden model/provider credentials.
- Export should label recommendation source IDs as references, not canonical
  recommendation truth.

## Privacy and Learning Rules

- Do not store raw secrets.
- Do not store raw survey answers unless explicitly approved.
- Store derived profile references, not raw survey truth.
- Store recommendation request IDs and source metadata for traceability.
- Future training data must filter PII and private user data.
- Conversation data must not be used for training until consent and policy are finalized.
- User input and model output can be retained for model improvement only after
  the product consent, retention, and deletion policy is finalized.

## Training And Evaluation Approval Gate

Current allowed use:

- Manual debugging by authorized developers.
- Evaluation fixture creation after removing sensitive personal data.
- Rule, prompt, and verifier regression analysis.
- Aggregate product quality metrics.

Current forbidden use:

- Fine-tuning or pretraining any model with stored chatbot logs.
- Exporting raw user messages to third-party tools without approval.
- Keeping a separate long-term ML dataset outside the retention window.

Before any training export is implemented, the project needs:

1. User-facing consent wording.
2. Deletion and export process.
3. PII redaction policy.
4. Human review policy for examples.
5. Dataset retention period.
6. Evaluation split rules.
7. Approval from the product owner and any required legal/privacy reviewer.

Training export must be a separate explicit job, not an implicit side effect of
normal chatbot request handling.
