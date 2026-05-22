# ONTHEBLOCK AI Assistant Service Agent Guide

## Purpose

This file is the root instruction document for AI agents working on the
`ai-assistant-service` repository.

The service is a standalone Python gRPC service. It powers the ONTHEBLOCK
assistant shown as a modal on Home and Board screens. It answers only app-domain
questions about alcohol recommendations, user taste, nearby venues, price,
distance, and availability.

## Non-Negotiable Rules

1. Do not deploy production.
2. Do not commit secrets, API keys, service-account JSON files, DB passwords, or
   real user tokens.
3. Do not bypass service ownership boundaries.
4. Do not use the LLM as the recommendation ranking engine.
5. Do not invent alcohols, venues, prices, distances, inventory, or user
   preferences.
6. If retrieved app data is missing or low-confidence, the assistant must say it
   cannot answer reliably.
7. Default user-facing language is polite Korean.
8. Keep changes small, reviewable, and documented.

## Service Boundaries

The assistant is a consumer/orchestrator service, not a data owner for external
domains.

| Service | Owns | Assistant May Do | Assistant Must Not Do |
|---|---|---|---|
| `auth-service` | Identity, OAuth, JWT, user profile, coarse neighborhood | Validate caller context through authenticated metadata or gateway context | Accept `user_id` from client body as trusted identity |
| `survey-service` | Raw survey answers and survey schema | Use recommendation-service profile status derived from survey data | Read survey DB directly or store raw survey as canonical data |
| `recommendation-service` | Derived taste profiles, vectors, scoring metadata, recommendation logs | Call recommendation APIs for beverage/venue recommendations | Re-rank recommendations with LLM |
| `map-service/place-service` | Canonical place, menu, inventory, price, location data | Use map read-model facts exposed through recommendation-service or approved APIs | Read canonical map DB directly |
| `chat-service` | Human-to-human chat rooms, messages, unread, attachments | Remain separate from assistant conversations | Store assistant conversations as human chat messages unless explicitly designed |
| `ai-assistant-service` | Assistant conversations, assistant messages, retrieval traces, prompt traces, feedback | Store assistant-owned logs for future evaluation/learning | Become source of truth for survey, map, auth, or recommendation data |

## Assistant Responsibilities

The assistant should support these intents:

- `recommend_beverage`
- `find_nearby_venue`
- `compare_purchase_options`
- `explain_preference`
- `explain_recommendation`
- `profile_status`
- `out_of_scope`
- `insufficient_data`

The assistant should return:

- polite Korean natural-language answer
- structured cards for UI rendering
- intent
- confidence
- refusal or insufficient-data reason when applicable
- internal `used_sources` metadata for traceability
- missing facts when relevant

## Correct High-Level Flow

```text
Client modal
  -> ai-assistant-service.AskAssistant
      -> resolve authenticated user context
      -> classify intent
      -> call recommendation-service
      -> build grounded RAG context from returned facts
      -> call LLM only for natural-language generation
      -> verify response against retrieved facts
      -> persist conversation/message/retrieval trace
      -> return answer + cards
```

## LLM Rules

The LLM may:

- rewrite retrieved recommendation facts into polite Korean
- summarize score reasons and tradeoffs
- ask follow-up questions when required data is missing
- explain that data is unavailable or uncertain

The LLM must not:

- create new recommendations not returned by recommendation-service
- invent price, distance, inventory, venue hours, or availability
- decide final ranking
- answer unrelated general knowledge questions
- provide medical, legal, or unsafe drinking advice

## RAG Rules

RAG is used as a grounded context builder, not as a ranking engine.

Allowed context:

- derived taste profile summary
- beverage recommendation candidates
- venue recommendation candidates
- score breakdowns
- reason codes
- price/distance/availability facts
- confidence, freshness, and revision metadata

No retrieved evidence means no answer.

## API Direction

Use gRPC-first design.

Draft service:

```proto
service AssistantService {
  rpc AskAssistant(AskAssistantRequest) returns (AskAssistantResponse);
  rpc GetConversation(GetConversationRequest) returns (GetConversationResponse);
  rpc RecordAssistantFeedback(RecordAssistantFeedbackRequest) returns (RecordAssistantFeedbackResponse);
}
```

Identity must come from authenticated metadata/JWT context. The public request
must not accept trusted `user_id`.

## Location Handling

Auth currently provides coarse neighborhood-level information. Detailed location
for nearby venue recommendations should come from Map context or request fields
such as `lat`, `lng`, and `radius_m`.

If detailed location is unavailable, the assistant should ask for location
permission/context or return an insufficient-data response.

## Storage Direction

Assistant-owned storage may include:

- `assistant_conversations`
- `assistant_messages`
- `assistant_retrieval_traces`
- `assistant_feedback_events`

These records are for audit, evaluation, and future learning. They are not source
of truth for survey, map, recommendation, or auth data.

## Python Engineering Defaults

Until the repository defines stricter tooling, prefer:

- Python 3.11+
- type hints
- dataclasses or Pydantic models for contracts
- pytest for tests
- ruff for linting/formatting
- explicit dependency injection for external clients
- no hidden global LLM clients
- no hardcoded credentials

Suggested structure:

```text
src/assistant_service/
- main.py
- config.py
- server.py
- clients/
  - auth_client.py
  - recommendation_client.py
  - llm_client.py
- domain/
  - intents.py
  - response_schema.py
  - cards.py
- pipeline/
  - intent_classifier.py
  - retrieval_context_builder.py
  - prompt_builder.py
  - response_verifier.py
  - assistant_pipeline.py
- storage/
  - repositories.py
  - models.py
```

## Required Working Loop

For non-trivial work, follow `.agent/HARNESS.md`.

Before changing code:

1. Read this file.
2. Read `.agent/DOMAIN_BOUNDARIES.md`.
3. Inspect relevant docs and code.
4. Produce a short execution plan.
5. Confirm service boundaries.

After changing code:

1. Run available tests/lint commands.
2. Update relevant docs.
3. Report changed files and unresolved risks.
4. Do not claim completion if tests were not run.

## Documentation Update Rules

Update docs when changing:

- service boundaries
- assistant API contract
- response schema
- prompt contract
- RAG/no-answer policy
- storage schema
- evaluation policy
- LLM provider behavior

## Final Response Format for Agents

When completing a task, report:

```text
Summary:
Files changed:
Commands run:
Validation result:
Boundary check:
Remaining risks:
Next recommended step:
```
