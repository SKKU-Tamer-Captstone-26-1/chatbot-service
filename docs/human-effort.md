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

Run a staging load test with 500 concurrent users covering:

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
