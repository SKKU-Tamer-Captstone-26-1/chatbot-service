# Chatbot Scaling and Cache Plan

## Purpose

This document records the production scaling concern for `AskChatbot`: if many
users ask questions at the same time, the service must not repeatedly perform
expensive upstream reads or database work for facts that can be reused safely.

The goal is to reduce read amplification while preserving service boundaries:
recommendation-service owns ranking, map/place services own canonical venue
facts, and ai-chatbot-service owns only chatbot orchestration and logs.

## Current Behavior

The current implementation does not load full chatbot conversation history for
every `AskChatbot` call. The normal request path is:

```text
AskChatbot
  -> resolve authenticated metadata
  -> get profile status from recommendation-service
  -> get beverage or venue recommendations from recommendation-service
  -> build grounded prompt context
  -> call LLM
  -> write chatbot conversation/message/trace when storage is enabled
```

This avoids conversation-read cost on the hot path, but it still has production
cost risks:

- repeated profile-status reads for the same active user
- repeated beverage recommendation reads for the same profile/filter set
- repeated venue recommendation reads for nearby users or repeated asks
- synchronous chatbot log writes adding latency
- future multi-turn context accidentally loading too much history

## Cache Ownership Rules

Recommendation-service should be the primary cache owner for recommendation
ranking results because it owns profile revisions, scoring, freshness, and
ranking semantics.

ai-chatbot-service may add a thin cache for orchestration efficiency, but cached
data must obey these rules:

- Cache only service API responses or derived prompt context.
- Do not cache raw survey answers.
- Do not cache canonical map/place data as chatbot-owned truth.
- Do not let cached LLM text become ranking truth.
- Include source IDs, profile revision, freshness, and request IDs in cached
  values when available.
- If freshness or confidence is unknown, answer with uncertainty or no-answer
  behavior.

## Recommended Cache Layers

| Layer | Owner | Purpose | Example TTL |
|---|---|---|---|
| Profile status | recommendation-service first, chatbot thin cache optional | Avoid repeated profile readiness checks | 1-5 min |
| Beverage recommendations | recommendation-service first, chatbot thin cache optional | Reuse deterministic ranking for same user profile/filter set | 1-10 min |
| Venue recommendations | recommendation-service first, chatbot thin cache optional | Reuse nearby place candidates with freshness limits | 30 sec-3 min |
| Prompt context | ai-chatbot-service | Avoid rebuilding identical grounded context | Same or shorter than source facts |
| LLM response text | ai-chatbot-service optional and conservative | Reuse exact deterministic response only for exact same context hash | 30 sec-2 min |
| Conversation writes | ai-chatbot-service | Move audit/evaluation logs off the response latency path | Queue based |

TTL values must be finalized with recommendation/map freshness rules. Venue
cache TTL should be shorter than beverage cache TTL because distance, inventory,
and price facts become stale faster.

## Cache Key Design

Profile-status cache key:

```text
profile_status:{user_id}
```

Beverage recommendation cache key:

```text
beverage_recs:{user_id}:{profile_revision}:{category}:{budget_mode}:{limit}
```

Venue recommendation cache key:

```text
venue_recs:{user_id}:{profile_revision}:{selected_beverage_id}:{location_bucket}:{radius_m}:{budget_mode}:{limit}
```

Prompt context cache key:

```text
prompt_context:{intent}:{source_context_hash}
```

Location must not use exact raw latitude/longitude for reuse. Use a stable
location bucket such as a short geohash or rounded grid cell. The bucket size
must be chosen so it does not produce misleading distance claims.

## Invalidation Strategy

Invalidate or bypass cached values when:

- profile revision changes
- recommendation-service reports stale or failed profile status
- recommendation response freshness is expired
- selected beverage ID changes
- budget mode, radius, category, or limits change
- location bucket changes
- user requests a precise current price, inventory, or availability fact and
  the cached venue freshness is not strong enough

If invalidation is uncertain, prefer a fresh upstream call or an
insufficient-data response over using stale facts.

## Async Persistence Plan

Conversation storage is required for evaluation and future learning, but the
user should not wait unnecessarily on log persistence once a valid response is
ready.

Plan:

1. Keep synchronous writes for the first production slice because they are
   simpler and easier to verify.
2. Add a bounded background queue for chatbot message and retrieval-trace writes.
3. Add retry with dead-letter logging for failed storage writes.
4. Preserve `message_id` semantics. If the UI needs a stable `message_id`
   immediately, generate it before enqueueing the write.
5. Keep feedback writes synchronous or idempotent because the client directly
   observes feedback state.

The async path must never drop safety-critical source metadata silently. If
trace writes fail repeatedly, emit metrics and structured logs.

## Multi-Turn Context Plan

Do not load full conversation history on every question.

Allowed strategy:

- Use the current request message as the main query.
- Fetch only the recent N messages when multi-turn context is explicitly needed.
- Store and reuse a rolling conversation summary for older context.
- Never include large raw history in the LLM prompt by default.
- Keep source facts and recommendation IDs separate from conversational summary.

Initial default:

```text
recent_message_limit = 6
max_summary_tokens = small, model-specific budget
```

## Implementation Plan

### Phase A: Metrics Before Cache

- Add counters/timers for recommendation calls, LLM calls, DB writes, cache hit
  rate, cache miss rate, and end-to-end latency.
- Record p50, p95, and p99 latency for `AskChatbot`.
- Track cache bypass reasons such as missing profile revision, stale venue
  facts, or no location bucket.

Implementation status:

- `src/chatbot_service/metrics.py` provides in-process counters and latency
  summaries with p50, p95, p99, and max.
- `ChatbotPipeline` records `chatbot.ask` and `llm.call`.
- Recommendation and storage wrappers record cache and write metrics.

### Phase B: Recommendation Response Cache

- Introduce a cache interface with Redis/Memorystore implementation and in-memory
  test implementation.
- Cache profile status, beverage recommendation responses, and venue
  recommendation responses.
- Include profile revision and filters in cache keys.
- Add tests proving recommendation-service results are not re-ranked or changed.

Implementation status:

- `src/chatbot_service/cache.py` provides `InMemoryCache`, `RedisCache`, and
  `NullCache`.
- `src/chatbot_service/clients/cached_recommendation_client.py` caches profile,
  beverage, and venue recommendation-service responses.
- Cache keys include user ID, profile revision, filters, and venue location
  bucket.
- Per-key locking prevents cold-cache stampedes from concurrent identical asks.
- Tests cover repeated and 500-concurrent identical recommendation requests.

### Phase C: Prompt Context Cache

- Hash grounded source context after recommendation responses are selected.
- Cache compact prompt context JSON by context hash.
- Do not cache if source facts are missing, stale, or low-confidence.

Implementation status:

- `ChatbotPipeline` hashes the selected grounded context and caches prompt
  context JSON with `prompt_context:{intent}:{source_context_hash}`.
- Prompt context caching is bypassed when evidence is missing, missing facts are
  present, confidence is zero, or profile status is not active.

### Phase D: Async Conversation Logging

- Add a bounded persistence queue for conversation messages and retrieval traces.
- Keep idempotent feedback writes.
- Add retry/dead-letter handling and operational metrics.

Implementation status:

- `src/chatbot_service/storage/async_repository.py` wraps chatbot-owned storage
  with a bounded queue, retry, dead-letter logging, and stable generated IDs.
- `GetConversation` and `RecordChatbotFeedback` drain pending writes before
  reading or writing user-observed state.

### Phase E: Load and Failure Testing

- Add load tests for 500 concurrent users with mixed beverage and venue intents.
- Verify recommendation-service QPS, Postgres write latency, LLM latency, cache
  hit rate, and error budget.
- Test Redis unavailable, recommendation-service slow, Postgres slow, and LLM
  timeout scenarios.

Implementation status:

- Unit-level 500-concurrent identical recommendation cache coverage exists.
- `chatbot-validate load` runs cold and warm staging load passes against an
  already-running chatbot gRPC endpoint.
- `chatbot-validate` runs Redis preflight when Redis/Memorystore cache is
  configured and validates recommendation card source IDs and rank order.
- `CHATBOT_METRICS_SNAPSHOT_PATH` plus
  `CHATBOT_VALIDATION_SERVICE_METRICS_PATH` lets validation output include
  service-side cache, LLM, recommendation, and storage queue metrics without a
  public metrics endpoint.
- Full deployed load tests still require human-provided staging service URLs and
  credentials. See `docs/human-effort.md`.

## Acceptance Criteria

- `AskChatbot` does not read full conversation history by default.
- Repeated identical profile/filter asks reuse cached service responses within
  approved TTL.
- Venue cache uses a location bucket, not exact lat/lng.
- Cache never changes ranking order or invents candidates.
- Stale price, inventory, distance, or availability facts do not produce
  confident answers.
- Postgres logging does not dominate response latency under 500 concurrent users.
- Metrics show cache hit/miss and upstream QPS clearly enough for production
  tuning.
