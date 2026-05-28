# GCP Server-First Zero-To-Hero Plan

## Summary

This plan describes how to build the ONTHEBLOCK AI chatbot system from local
MVP to production. The default architecture is GCP server-first: Android clients
call backend services, recommendation-service owns ranking and facts, and
ai-chatbot-service orchestrates grounded chatbot responses. On-device LLM is a
later optimization after the server path is stable.

The chatbot LLM is not the recommendation engine. It only generates concise,
polite Korean wording from retrieved recommendation facts.

Target production shape:

```text
Android app
  -> Firebase Auth / App Check
  -> API gateway or gRPC bridge
  -> Cloud Run ai-chatbot-service
      -> recommendation-service
      -> Cloud SQL PostgreSQL
      -> Memorystore Redis
      -> server LLM endpoint
  -> offline training/evaluation pipeline
```

## Non-Negotiable Rules

- Do not deploy production from this repository without explicit human approval.
- Do not commit secrets, service-account files, DB passwords, or real user
  tokens.
- Do not accept trusted user identity from chatbot request bodies.
- Do not read survey-service, map-service, or place-service databases directly.
- Do not use the LLM to rank, rerank, or create recommendation candidates.
- Do not invent place, price, flavor, drink, scent, inventory, availability, or
  distance facts.
- Do not use stored chatbot logs for training until consent, retention,
  deletion, and PII filtering policy is finalized.

Reference docs:

- `docs/chatbot/chatbot-architecture.md`
- `docs/chatbot/model-strategy.md`
- `docs/chatbot/storage-and-learning.md`
- `docs/chatbot/scaling-and-cache-plan.md`
- `docs/human-effort.md`

## Phase 0: Repository And Contract Baseline

Goal: make the chatbot-service repository safe for iterative implementation.

Deliverables:

- Root agent and harness docs exist.
- Chatbot gRPC proto is the public service contract.
- Service boundary docs clearly separate chatbot, recommendation, auth, survey,
  map/place, and human chat responsibilities.
- Local test/lint/proto commands are documented.

Acceptance gate:

- `AGENT.md` and `.agent/HARNESS.md` are present.
- `proto/chatbot/v1/chatbot.proto` defines `AskChatbot`,
  `GetConversation`, and `RecordChatbotFeedback`.
- Proto comments state that recommendation-service owns ranking and facts.
- `protoc -I proto --descriptor_set_out=/private/tmp/chatbot.desc proto/chatbot/v1/chatbot.proto`
  succeeds.

Current status: mostly complete.

## Phase 1: Local Chatbot Runtime

Goal: run chatbot-service locally with deterministic behavior and no production
dependencies.

Deliverables:

- Python gRPC server starts from `chatbot-service`.
- Health check is registered.
- Config loader reads all runtime environment variables.
- Pipeline supports intent classification, grounded context assembly, prompt
  building, LLM adapter, response verification, and response card generation.
- Fake/local adapters support tests without real external services.

Acceptance gate:

- `python3 -m ruff check .` succeeds.
- `python3 -m pytest` succeeds.
- A local `AskChatbot` request returns either a grounded answer, an
  insufficient-data response, or a refusal.
- The service never requires trusted `user_id` in the public request body.

Current status: implemented.

## Phase 2: Recommendation Integration And Grounding

Goal: use recommendation-service as the only source for ranked recommendation
facts.

Deliverables:

- Chatbot calls recommendation-service for profile status, beverage
  recommendations, and venue recommendations.
- Chatbot preserves recommendation request IDs, result IDs, rank, reason codes,
  profile revision, freshness, and availability metadata.
- Chatbot converts recommendation outputs into structured cards.
- Response verifier rejects answers when evidence is missing or unsupported.

Acceptance gate:

- Beverage, venue, and purchase option cards include source result IDs.
- Answered recommendation responses expose `used_sources`.
- Tests prove card order follows recommendation-service order.
- Missing profile, missing location, no candidates, or stale facts return
  insufficient-data behavior instead of invented facts.

Current status: implemented for the current service shape.

## Phase 3: Storage, Feedback, And Future Learning

Goal: store chatbot-owned conversation data for audit, evaluation, feedback, and
future model improvement without becoming a source of truth for external
domains.

Deliverables:

- PostgreSQL migrations create chatbot-owned tables.
- Conversation, message, retrieval trace, and feedback repositories exist.
- `GetConversation` is scoped to authenticated caller identity.
- Feedback writes are idempotent.
- Async persistence can move chatbot logs off the hot path.

Acceptance gate:

- `chatbot-migrate --list` shows migration versions and checksums.
- Storage tests pass.
- `AskChatbot` does not load full conversation history by default.
- Stored `used_sources` can trace a response back to recommendation-service
  request/result IDs.
- Training use remains blocked until policy is approved.

Current status: implemented locally; production policy still requires human
approval.

## Phase 4: Cache, Cost, And 500-User Load Readiness

Goal: prevent expensive repeated reads when many users ask similar questions.

Deliverables:

- Redis/Memorystore cache backend for production.
- Thin chatbot cache for profile status, recommendation responses, and compact
  prompt context.
- Per-key locking prevents cold-cache stampedes.
- Cache keys include user ID, profile revision, filters, limits, budget mode,
  selected beverage, and venue location bucket.
- Conversation writes use a bounded async persistence queue.
- Validation harness covers smoke and cold/warm load checks.

Acceptance gate:

- `chatbot-validate smoke` passes against staging.
- `CHATBOT_VALIDATION_CONCURRENCY=500 CHATBOT_VALIDATION_REQUESTS=500 chatbot-validate load`
  passes against staging.
- Redis preflight passes when Redis is required.
- Warm load shows acceptable p95 latency and lower upstream pressure.
- Cache never changes ranking order or source IDs.
- Service metrics show cache hit/miss/error, recommendation call, LLM call, and
  storage queue behavior.

Current status: local implementation exists; real staging endpoints and
credentials are still needed.

## Phase 5: Staging On GCP

Goal: deploy a non-production GCP environment that looks like production enough
to validate behavior and load.

Recommended GCP services:

- Cloud Run for `ai-chatbot-service`.
- Cloud SQL PostgreSQL for chatbot-owned storage.
- Memorystore Redis for shared cache.
- Secret Manager for tokens, DSNs, and provider credentials.
- Cloud Logging and Cloud Monitoring for runtime visibility.
- Firebase Auth and App Check for app identity and abuse reduction.

Required staging inputs:

- `RECOMMENDATION_SERVICE_URL`
- `CHATBOT_DB_DSN`
- `CHATBOT_CACHE_BACKEND=redis`
- `CHATBOT_CACHE_REDIS_URL`
- `CHATBOT_LLM_PROVIDER`
- `CHATBOT_LLM_ENDPOINT_URL`
- `CHATBOT_LLM_MODEL`
- LLM auth settings when the endpoint requires them
- validation target, user ID metadata key, and test authorization token

Deliverables:

- Staging environment variables are configured through Secret Manager or secure
  deployment config, not committed files.
- Migrations run against staging Cloud SQL.
- Chatbot service starts on Cloud Run and can reach recommendation-service,
  Redis, PostgreSQL, and LLM endpoint.
- `chatbot-validate smoke` is part of the staging verification routine.

Acceptance gate:

- Staging service health check is serving.
- Smoke validation passes with real auth metadata.
- `GetConversation` and feedback work for the authenticated staging user.
- No secrets are added to git.

## Phase 6: Server LLM Deployment

Goal: run the fine-tuned response-generation model behind a backend endpoint.

Default approach:

- Train or fine-tune outside chatbot-service.
- Serve the selected checkpoint through an OpenAI-compatible
  `/v1/chat/completions` API.
- Use Cloud Run GPU with vLLM/TGI, Vertex AI endpoint, or a private managed
  Hugging Face/TGI endpoint depending on cost and operational constraints.

Runtime contract:

```text
CHATBOT_LLM_PROVIDER=huggingface_tgi
CHATBOT_LLM_ENDPOINT_URL=<openai-compatible-chat-completions-url>
CHATBOT_LLM_MODEL=<model-or-endpoint-name>
CHATBOT_LLM_AUTH_MODE=none|bearer_env
CHATBOT_LLM_API_KEY_ENV=<required only when bearer_env>
```

Deliverables:

- Local/private LLM endpoint support does not require API key env when
  `CHATBOT_LLM_AUTH_MODE=none`.
- Remote secured endpoint support requires bearer token from env.
- LLM timeout and max-token settings are configurable.
- Prompt remains compact and fact-only.

Acceptance gate:

- LLM adapter returns a concise Korean response from provided facts.
- LLM timeout produces safe fallback behavior.
- Endpoint auth failure fails fast in staging preflight.
- LLM output cannot add cards, sources, or ranked candidates.

## Phase 7: Evaluation And Release Gates

Goal: prevent regressions in grounding, ranking, refusal, tone, latency, and
cost before production release.

Deliverables:

- App-specific evaluation fixtures:
  - grounded recommendation cases
  - no-answer cases
  - out-of-scope cases
  - ranking integrity cases
  - Korean tone cases
  - load/cache cases
- Offline evaluator can call the configured LLM endpoint.
- Staging validation outputs latency and failure summaries.
- Release gate is documented and repeatable.

Acceptance gate:

- No invented facts in evaluation.
- No candidate reordering.
- No unrelated general-knowledge answers.
- Korean tone is concise and polite.
- 500-user load validation passes.
- Required dashboards or metric snapshots show acceptable latency and error
  rates.

## Phase 8: Training Data Pipeline

Goal: convert approved chatbot logs into high-quality model improvement data
without violating privacy or service boundaries.

Required policy decisions before implementation:

- User consent wording and UX.
- Retention period.
- User deletion/export process.
- PII filtering rules.
- Train/eval split rules.
- Human review requirements for generated training examples.

Recommended pipeline:

```text
chatbot PostgreSQL logs
  -> approved export job
  -> PII filtering/redaction
  -> evaluation/train split
  -> GCS or BigQuery dataset
  -> offline fine-tuning job
  -> evaluation gate
  -> model registry/version
  -> staged endpoint rollout
```

Deliverables:

- Export only chatbot-owned fields needed for response generation.
- Keep recommendation source IDs and compact candidate summaries for grounding.
- Exclude secrets, auth tokens, raw survey answers, and canonical map/place DB
  rows.
- Store model version, prompt version, eval result, and rollout status.

Acceptance gate:

- Training data cannot include unapproved private data.
- Every training example can be traced to source policy and consent state.
- New checkpoint passes Phase 7 before serving production traffic.

## Phase 9: Production Launch

Goal: release the chatbot to real Play Store users with safe fallback behavior,
observability, and rollback.

Deliverables:

- Production Cloud Run service.
- Production Cloud SQL PostgreSQL.
- Production Memorystore Redis.
- Production LLM endpoint.
- Secret Manager backed config.
- Dashboards and alerts for:
  - request rate and latency
  - recommendation-service errors
  - cache hit/miss/error rate
  - LLM timeout/error/latency
  - storage queue depth/retry/dead-letter count
  - insufficient-data/refusal rate
- Rollback plan for chatbot-service and LLM model version.

Production acceptance gate:

- Staging smoke and 500-user load pass.
- Production config passes preflight.
- No direct external service DB reads.
- No LLM ranking or invented facts.
- Auth identity comes only from trusted metadata.
- Storage, retention, and training-data policy are approved.
- Support owner knows how to disable LLM endpoint or switch to safe fallback.

## Phase 10: Optional On-Device LLM

Goal: reduce latency/cost for supported Android devices while keeping backend
truth, storage, and fallback.

Decision: on-device LLM is not MVP. Add it only after server production is
stable.

Allowed on-device responsibilities:

- Lightweight intent hints.
- Short Korean wording from already-downloaded grounded facts.
- Offline cached explanations where source facts are already present and fresh.

Server-side responsibilities remain:

- Auth.
- Recommendation ranking.
- Place, price, inventory, freshness, and distance facts.
- Conversation storage and feedback.
- Training data export.
- Abuse control and rate limiting.
- Fallback LLM response.

Acceptance gate:

- Unsupported devices automatically use server LLM.
- On-device output uses the same grounding rules.
- Model package size, battery, latency, and thermal behavior are acceptable.
- Server can disable on-device path through remote config.

## Immediate Next Implementation Slice

Implement staging fail-fast preflight.

Deliverables:

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

## Open Human Decisions

- Final staging and production GCP project IDs.
- Final auth/gateway metadata contract.
- Whether Redis is mandatory outside local development.
- Final cache TTLs and venue location bucket precision.
- LLM serving target: Cloud Run GPU, Vertex AI endpoint, or private TGI/vLLM.
- Consent, retention, deletion, and PII policy for model improvement.
- On-device LLM timing and supported Android device policy.
