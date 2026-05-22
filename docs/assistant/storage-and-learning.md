# Assistant Storage and Future Learning

## Purpose

This document defines what assistant conversation data may be stored and how it may later support improvement or training.

## Storage Decision

MVP should store assistant conversations because future learning and evaluation are planned.

## Assistant-Owned Tables Draft

```text
assistant_conversations
- id
- external_user_id
- created_at
- updated_at
- screen_context
- metadata_json

assistant_messages
- id
- conversation_id
- role
- content
- intent
- confidence
- refused
- refusal_reason
- created_at

assistant_retrieval_traces
- id
- message_id
- recommendation_request_id
- profile_revision
- used_sources_json
- missing_facts_json
- prompt_version
- model_provider
- model_name
- created_at

assistant_feedback_events
- id
- message_id
- event_type
- metadata_json
- created_at
```

## Privacy and Learning Rules

- Do not store raw secrets.
- Do not store raw survey answers unless explicitly approved.
- Store derived profile references, not raw survey truth.
- Store recommendation request IDs and source metadata for traceability.
- Future training data must filter PII and private user data.
- Conversation data must not be used for training until consent and policy are finalized.
