# Migration Checklist

Use this when adding assistant-owned database tables.

## Allowed Assistant-Owned Tables

Examples:

- `assistant_conversations`
- `assistant_messages`
- `assistant_retrieval_traces`
- `assistant_feedback_events`

## Required Fields to Consider

Conversation:

```text
id
external_user_id or auth subject reference
surface: HOME | BOARD | OTHER
created_at
updated_at
```

Message:

```text
id
conversation_id
role: USER | ASSISTANT | SYSTEM
content
intent
confidence
created_at
```

Retrieval trace:

```text
id
message_id
recommendation_request_id
profile_revision
used_sources_json
missing_facts_json
prompt_context_hash
created_at
```

Feedback:

```text
id
message_id
feedback_type
metadata_json
created_at
```

## Forbidden Storage

- Raw survey answers as canonical data
- Canonical map/place/menu/inventory rows
- Auth tokens
- LLM provider credentials
- Full private prompts containing secrets

## Migration Rules

- Use Alembic if the repository uses Python/PostgreSQL.
- Every table must have timestamps.
- Store trace IDs for auditability.
- Prefer JSONB only for trace/debug payloads, not primary query fields.
- Add indexes for `conversation_id`, user reference, and `created_at`.
- Document rebuild/retention implications.
