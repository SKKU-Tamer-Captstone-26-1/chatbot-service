# ONTHEBLOCK AI Assistant Service Starter

## Purpose

This starter defines the initial documentation and skeleton structure for a separate `ai-assistant-service`.

The assistant appears as a modal-style chatbot on Home and Board screens. It answers only ONTHEBLOCK app-domain questions about alcohol recommendations, user taste preferences, nearby venues, price/distance/availability comparisons, and recommendation explanations.

## Core Rule

The assistant does **not** rank recommendations with the LLM.

```text
recommendation-service = deterministic ranking, scoring, reason codes
ai-assistant-service  = intent handling, RAG context assembly, guardrails, Korean natural-language response
LLM                   = grounded response generation only
```

## Initial Structure

```text
assistant-service/
- README.md
- .env.example
- proto/assistant/v1/assistant.proto
- docs/assistant/
  - assistant-architecture.md
  - api-contract.md
  - rag-policy.md
  - prompt-contract.md
  - response-schema.md
  - evaluation-policy.md
  - storage-and-learning.md
  - implementation-roadmap.md
- src/assistant_service/
  - main.py
  - config.py
  - domain/
  - clients/
  - pipeline/
  - storage/
- evaluation/
  - no_answer_cases.yaml
  - golden_cases.yaml
- scripts/
  - README.md
```

## MVP Dependencies

- `auth-service`: authenticated user context and coarse user location such as dong-level location.
- `recommendation-service`: profile status, beverage recommendations, venue recommendations, reason codes, score breakdowns.
- `map-service` / map read model: detailed location, venue, inventory, price, distance, and freshness facts.
- Open LLM provider: undecided. Keep provider-neutral adapter interface.

## MVP Non-Goals

- No model fine-tuning.
- No random-noise warm-up training implementation.
- No LLM-based ranking.
- No direct reads from survey-service DB or map-service DB.
- No service-account keys or provider secrets committed.
