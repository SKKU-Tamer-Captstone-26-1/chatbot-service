# Human Effort Needed

The scaling/cache implementation is wired in code, but these production items
need human decisions or external infrastructure access.

## Required Before Production

- Provide the production Redis/Memorystore URL for `CHATBOT_CACHE_REDIS_URL`.
- Confirm whether `CHATBOT_CACHE_BACKEND=redis` should be mandatory outside
  local development.
- Confirm TTLs with recommendation/map owners:
  - `CHATBOT_CACHE_PROFILE_STATUS_TTL_SEC`
  - `CHATBOT_CACHE_BEVERAGE_RECOMMENDATIONS_TTL_SEC`
  - `CHATBOT_CACHE_VENUE_RECOMMENDATIONS_TTL_SEC`
  - `CHATBOT_CACHE_PROMPT_CONTEXT_TTL_SEC`
- Confirm the venue location bucket precision. Current default is 3 decimal
  places, which is roughly neighborhood-block scale and must be checked against
  distance/price accuracy expectations.
- Provide staging `RECOMMENDATION_SERVICE_URL`, auth metadata contract, and test
  tokens for deployed integration/load testing.
- Provide staging PostgreSQL DSN and Redis/Memorystore endpoint for 500-user
  load testing.
- Decide whether async conversation persistence is acceptable for production
  read-after-write behavior. `GetConversation` and feedback drain pending writes,
  but `AskChatbot` itself returns before log persistence completes.
- Confirm retention, consent, deletion, and PII filtering policy before using
  stored user input/model output for training.

## Load Test To Run With Human-Provided Infrastructure

Run smoke validation against a staging chatbot gRPC service:

```bash
chatbot-validate smoke
```

Run a staging load test with 500 concurrent users:

```bash
CHATBOT_VALIDATION_CONCURRENCY=500 CHATBOT_VALIDATION_REQUESTS=500 chatbot-validate load
```

If staging uses Redis/Memorystore, keep
`CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT=true` so validation fails before
traffic if the cache endpoint is unavailable.

Keep `CHATBOT_VALIDATION_REQUIRE_RUNTIME_PREFLIGHT=true` for staging. The
preflight checks validation metadata, recommendation-service URL, Postgres DSN
when storage is enabled, LLM provider/model/endpoint, Redis configuration, and
the LLM API key only when `CHATBOT_LLM_AUTH_MODE=bearer_env`. Use
`CHATBOT_LLM_AUTH_MODE=none` for a local/private fine-tuned LLM endpoint that
does not require bearer auth.

To include service-side metrics in validation output, run the chatbot service
with:

```bash
CHATBOT_METRICS_SNAPSHOT_PATH=/tmp/chatbot-service-metrics.json
```

and run validation with:

```bash
CHATBOT_VALIDATION_SERVICE_METRICS_PATH=/tmp/chatbot-service-metrics.json
```

The validation harness covers:

- repeated beverage recommendation asks
- nearby venue asks across multiple location buckets
- cache warm and cold starts
- Redis unavailable fallback
- recommendation-service slow/error fallback
- Postgres slow/error behavior with async persistence queue
- LLM timeout behavior

Success metrics to review:

- recommendation-service QPS reduction from cache
- cache hit/miss/bypass/error rates
- `AskChatbot` p50/p95/p99 latency
- LLM p50/p95/p99 latency
- storage queue depth, retries, dead letters
- no ranking reorder or invented candidate regressions

The harness reports Redis preflight status, cold/warm p50, p95, p99, max
latency, request failures, and optional service-side metrics snapshots. It also
validates that answered recommendation cards carry source result IDs and rank
order.
