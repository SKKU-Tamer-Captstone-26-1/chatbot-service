# 021 DB Retention And Privacy Policy

## Task

Define production-ready retention and privacy rules for chatbot-owned
conversation, message, retrieval trace, and feedback storage.

## Current State Summary

- Existing files:
  - `docs/chatbot/storage-and-learning.md`
  - `docs/plans/004-storage-feedback-learning-readiness.md`
  - `docs/plans/010-training-data-pipeline.md`
- Existing behavior:
  - Chatbot-owned PostgreSQL tables exist.
  - `CHATBOT_STORAGE_RETENTION_DAYS` defaults to 365 days.
  - Stored logs are scoped to authenticated users and trace recommendation
    result IDs.
- Missing pieces:
  - Concrete production retention policy.
  - Deletion/export handling direction.
  - Training data approval gates.
  - Explicit PII/secrets restrictions for stored metadata.

## Boundary Impact

| Boundary | Impact | Notes |
|---|---|---|
| Auth identity/JWT | low | external user ID is stored, raw JWT must not be stored |
| Survey ownership | none | raw survey answers remain forbidden |
| Recommendation ranking | none | only source IDs and returned facts are retained |
| Map/place data | none | canonical map/place DB data is not copied |
| Chatbot storage | medium | documents retention and deletion policy |
| LLM prompt behavior | none | no prompt change |
| Deployment/secrets | none | no secret changes |

## Files To Add/Change

- `docs/chatbot/storage-and-learning.md` - add concrete retention, privacy,
  export, deletion, and training approval policy.
- `docs/plans/README.md` - add this numbered plan.

## API Impact

- New RPCs: none
- Changed RPCs: none
- Backward compatibility: no API change
- Auth metadata requirements: no change

## Storage Impact

- New tables: none
- Changed tables: none
- Migration needed: no
- Data retention: policy clarified; purge implementation remains a future
  operational task.

## RAG / LLM Impact

- Prompt changes: none
- Context changes: none
- No-answer behavior: none
- Output schema changes: none

## Test Plan

- Documentation review only.
- Existing storage tests continue to verify scoped reads and idempotent feedback.

## Rollback Plan

- Revert this policy doc update if product/legal policy changes.
