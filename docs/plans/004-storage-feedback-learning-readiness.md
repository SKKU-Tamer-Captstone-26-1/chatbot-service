# 004 Storage, Feedback, And Learning Readiness

## Goal

Store chatbot-owned conversation data for audit, evaluation, feedback, and
future model improvement without becoming a source of truth for external
domains.

## Deliverables

- PostgreSQL migrations create chatbot-owned tables.
- Conversation, message, retrieval trace, and feedback repositories exist.
- `GetConversation` is scoped to authenticated caller identity.
- Feedback writes are idempotent.
- Async persistence can move chatbot logs off the hot path.

## Acceptance Gate

- `chatbot-migrate --list` shows migration versions and checksums.
- Storage tests pass.
- `AskChatbot` does not load full conversation history by default.
- Stored `used_sources` can trace a response back to recommendation-service
  request/result IDs.
- Training use remains blocked until policy is approved.

## Current Status

Implemented locally. Production policy still requires human approval.

## Next Step

Continue with `005-cache-load-readiness.md`.
