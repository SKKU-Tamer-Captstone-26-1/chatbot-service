# 005 Cache And Load Readiness

## Goal

Prevent expensive repeated reads when many users ask similar questions.

## Deliverables

- Redis/Memorystore cache backend for production.
- Thin chatbot cache for profile status, recommendation responses, and compact
  prompt context.
- Per-key locking prevents cold-cache stampedes.
- Cache keys include user ID, profile revision, filters, limits, budget mode,
  selected beverage, and venue location bucket.
- Conversation writes use a bounded async persistence queue.
- Validation harness covers smoke and cold/warm load checks.

## Acceptance Gate

- `chatbot-validate smoke` passes against staging.
- `CHATBOT_VALIDATION_CONCURRENCY=500 CHATBOT_VALIDATION_REQUESTS=500 chatbot-validate load`
  passes against staging.
- Redis preflight passes when Redis is required.
- Warm load shows acceptable p95 latency and lower upstream pressure.
- Cache never changes ranking order or source IDs.
- Service metrics show cache hit/miss/error, recommendation call, LLM call, and
  storage queue behavior.

## Current Status

Implemented locally, including cache, async persistence with queue-depth metrics,
validation harness, and fail-fast staging preflight. Real staging endpoints and
credentials are still needed to run the external smoke/load acceptance gates.

## Immediate Implementation Slice

Staging fail-fast preflight is implemented:

- Validate required staging env before `chatbot-validate smoke/load` sends
  traffic.
- Require Redis URL when Redis cache is enabled.
- Require Postgres DSN when storage is enabled.
- Require recommendation-service URL.
- Require LLM endpoint/model.
- Require LLM API key only when auth mode is bearer-env.
- Update `.env.example`, validation docs, and tests.

Verification:

```bash
python3 -m ruff check .
python3 -m pytest
python3 scripts/validate_staging.py --help
```

## Next Step

Continue with `006-gcp-staging.md`.
