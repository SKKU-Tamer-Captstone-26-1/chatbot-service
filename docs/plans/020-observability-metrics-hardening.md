# 020 Observability Metrics Hardening

## Task

Add production-facing chatbot metrics for request intent, response outcome,
missing facts, recommendation-service unavailability, LLM failure, and verifier
fallbacks.

## Current State Summary

- Existing files:
  - `src/chatbot_service/metrics.py`
  - `src/chatbot_service/pipeline/chatbot_pipeline.py`
  - `tests/test_chatbot_pipeline.py`
  - `docs/chatbot/scaling-and-cache-plan.md`
- Existing behavior:
  - The pipeline records `chatbot.ask` latency by final status.
  - The pipeline records `llm.call` latency.
  - Recommendation cache and storage wrappers emit cache/write counters.
- Missing pieces:
  - Counters for LLM failure and verifier fallback rates.
  - Counters for `recommendation_service_unavailable` so gateway/Flutter mapping
    issues can be detected independently from profile-missing responses.
  - Counters for intent/status/outcome distribution.

## Boundary Impact

| Boundary | Impact | Notes |
|---|---|---|
| Auth identity/JWT | none | no raw auth metadata is logged as metrics |
| Survey ownership | none | no change |
| Recommendation ranking | none | no ranking/filtering changes |
| Map/place data | none | no change |
| Chatbot storage | none | no schema change |
| LLM prompt behavior | none | no prompt change |
| Deployment/secrets | low | metrics snapshot config already exists |

## Files To Add/Change

- `src/chatbot_service/pipeline/chatbot_pipeline.py` - emit safe counters on
  intent, context, guardrail, LLM, verifier, and final response paths.
- `tests/test_chatbot_pipeline.py` - assert metric counters for success,
  recommendation unavailable, and LLM fallback paths.
- `docs/chatbot/scaling-and-cache-plan.md` - document the new operational
  counters.
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
- Data retention: no change

## RAG / LLM Impact

- Prompt changes: none
- Context changes: none
- No-answer behavior: unchanged
- Output schema changes: none

## Test Plan

- Unit tests:
  - `tests/test_chatbot_pipeline.py`
- Full regression:
  - `pytest`

## Rollback Plan

- Revert metrics additions if labels need to be renamed for Cloud Monitoring
  export. No data cleanup is needed.
