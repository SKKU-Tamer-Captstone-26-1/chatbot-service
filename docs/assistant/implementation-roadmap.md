# AI Assistant Implementation Roadmap

## Phase 0: Documentation and Contracts

- Add assistant docs.
- Add draft `assistant.proto`.
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
- Convert results into assistant cards.

## Phase 3: Guardrails and RAG Context

- Implement intent classifier.
- Implement context builder.
- Implement no-evidence no-answer policy.
- Implement out-of-scope refusal.
- Implement prompt contract.

## Phase 4: Conversation Storage

- Store conversations.
- Store assistant messages.
- Store retrieval traces and used_sources.
- Store feedback events.

## Phase 5: Flutter Integration

- Home modal chatbot.
- Board modal chatbot.
- Card rendering.
- Location handling.

## Phase 6: Evaluation

- Add golden cases.
- Add no-answer cases.
- Add out-of-scope cases.
- Add regression tests for hallucination prevention.
