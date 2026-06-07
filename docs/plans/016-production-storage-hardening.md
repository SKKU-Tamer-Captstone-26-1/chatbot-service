# 016 Production Storage Hardening

## Task

Improve conversation persistence reliability under load by preventing silent loss when
the bounded async write queue is full.

## Current State Summary

- Existing files:
  - `src/chatbot_service/storage/async_repository.py`
  - `tests/test_scaling_cache.py`
- Existing behavior:
  - Async writes are enqueued and dropped on queue-full via dead-letter list.
  - In-memory/stable IDs are returned immediately for user responses.
- Missing pieces:
  - Queue-full is treated as write-loss by default.
  - Hardening test coverage for queue-full fallback path is missing.

## Boundary Impact

| Boundary | Impact | Notes |
|---|---|---|
| Auth identity | none | Unchanged |
| Survey ownership | none | Unchanged |
| Recommendation ranking | none | Unchanged |
| Map/place data | none | Unchanged |
| Chatbot storage | medium | Improves durability of chatbot-owned conversation/message/traces |
| LLM prompt behavior | none | Unchanged |
| Deployment/secrets | none | No config/secrets change |

## Files To Add/Change

```text
src/chatbot_service/storage/async_repository.py - On queue-full, execute write operation synchronously with retries instead of dropping silently.
tests/test_scaling_cache.py - Add regression test verifying fallback behavior and metrics.
docs/plans/016-production-storage-hardening.md - Plan and scope for this hardening step.
```

## API Impact

- New RPCs: none
- Changed RPCs: none
- Backward compatibility: no API change
- Auth metadata requirements: no change

## Storage Impact

- New tables: none
- Changed tables: none
- Migration needed: no
- Data retention: existing retention behavior unchanged

## RAG / LLM Impact

- Prompt shape: none
- Context changes: none
- No-answer behavior: unchanged
- Output schema: none

## Test Plan

- Unit tests:
  - `tests/test_scaling_cache.py::test_async_repository_falls_back_to_sync_when_queue_is_full`
- Integration tests:
  - Existing async repository and pipeline persistence flows
- Contract tests:
  - no API contract changes
- Evaluation cases:
  - Not affected
- Manual test:
  - Run staging load test and confirm `storage.queue_full_fallback` appears only under queue pressure.

## Rollback Plan

- Safe rollback:
  - Revert the async-repository fallback path change.
- Data cleanup if needed:
  - If stale partial traces exist from in-flight operations during rollout, existing dead-letter visibility handles diagnostics.
  - No user-data schema migration needed.

## Open Questions

1. Do we want a runtime flag to explicitly disable sync fallback on queue-full?
2. Should queue-full fallback be rate-limited (circuit-breaker) under sustained saturation?
