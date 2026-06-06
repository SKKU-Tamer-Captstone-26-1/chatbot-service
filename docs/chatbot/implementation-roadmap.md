# AI Chatbot Implementation Roadmap

## Phase 0: Documentation and Contracts

- Add chatbot docs.
- Add draft `chatbot.proto`.
- Define response schema and card types.
- Define no-answer and out-of-scope policy.

## Phase 1: Skeleton Service

- Create gRPC server skeleton.
- Add config loader.
- Add dependency clients as interfaces.
- Add health check.
- Add fake LLM adapter for local tests.

## Phase 2: Recommendation Integration

- Call `GetProfileStatus`.
- Call `GetBeverageRecommendations`.
- Call `GetVenueRecommendations`.
- Convert results into chatbot cards.
- Preserve recommendation request IDs, result IDs, ranks, reason codes, profile status, freshness, and availability.
- Keep ranking as recommendation-service-owned rule-based/heuristic logic until
  enough approved usage data exists for an ML ranking experiment.

## Phase 3: Guardrails and RAG Context

- Implement intent classifier.
- Implement context builder.
- Implement no-evidence no-answer policy.
- Implement out-of-scope refusal.
- Implement prompt contract.
- Use the Hugging Face/TGI-compatible adapter for a base OpenLLM response writer.
- Keep prompt context compact because the model is a narrow response generator,
  not a large reasoning model.

## Phase 3.5: Model Strategy And Evaluation

- Use open LLM leaderboards only to shortlist candidate base models.
- Select the final base model using ONTHEBLOCK-specific evals.
- Do not fine-tune for the current MVP; the data is not sufficient yet.
- Evaluate rule/reason-code quality, prompt quality, verifier behavior, and
  Korean answer quality together.
- Configure `CHATBOT_LLM_PROVIDER=huggingface_tgi`.
- Run golden/no-answer/out-of-scope/ranking/tone evals against the endpoint.
- Gate release on no invented place, price, flavor, drink, scent, inventory, or distance facts.
- Revisit fine-tuning only after enough consented chatbot logs and feedback
  labels exist.

## Phase 4: Conversation Storage

- Store conversations.
- Store chatbot messages.
- Store retrieval traces and used_sources.
- Store feedback events.
- Require PostgreSQL storage in production.
- Keep training use blocked until consent, retention, and deletion policy is finalized.

## Phase 4.25: Scaling, Cache, and Cost Control

- Add request-path metrics before adding cache.
- Keep recommendation-service as the primary cache owner for ranking results.
- Add a thin chatbot cache for profile status, recommendation responses, and
  compact prompt context only after source freshness rules are defined.
- Use profile revision, filters, and location buckets in cache keys.
- Do not cache raw survey answers or canonical map/place truth in chatbot-service.
- Move conversation and retrieval-trace writes to bounded async persistence after
  the synchronous storage path is verified.
- Do not load full conversation history on every `AskChatbot` request.
- Validate the path with 500-concurrent-user load tests.
- Detailed plan: `docs/chatbot/scaling-and-cache-plan.md`.

## Phase 4.5: Auth Adapter Finalization

- Keep metadata-only caller resolution in chatbot-service.
- Replace temporary metadata header names after auth/gateway contract is finalized by the auth team.
- Continue to reject trusted user identity from chatbot request bodies.

## Phase 5: Flutter Integration

- Home modal chatbot.
- Board modal chatbot.
- Card rendering.
- Location handling.

## Phase 6: Evaluation

- Add golden cases.
- Add no-answer cases.
- Add out-of-scope cases.
- Add ranking integrity cases.
- Add Korean tone cases.
- Add regression tests for hallucination prevention.
