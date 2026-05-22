# ONTHEBLOCK AI Chatbot Service Starter

## Purpose

This starter defines the initial documentation and skeleton structure for a separate `ai-chatbot-service`.

The chatbot appears as a modal on Home and Board screens. It answers only ONTHEBLOCK app-domain questions about alcohol recommendations, user taste preferences, nearby venues, price/distance/availability comparisons, and recommendation explanations.

## Core Rule

The chatbot does **not** rank recommendations with the LLM.

```text
recommendation-service = deterministic ranking, scoring, reason codes
ai-chatbot-service  = intent handling, RAG context assembly, guardrails, Korean natural-language response
LLM                   = grounded response generation only
```

## Initial Structure

```text
chatbot-service/
- README.md
- .env.example
- pyproject.toml
- proto/chatbot/v1/chatbot.proto
- docs/chatbot/
  - chatbot-architecture.md
  - api-contract.md
  - rag-policy.md
  - prompt-contract.md
  - response-schema.md
  - evaluation-policy.md
  - storage-and-learning.md
  - implementation-roadmap.md
- src/chatbot_service/
  - main.py
  - config.py
  - server.py
  - grpc_service.py
  - generated/
  - domain/
  - clients/
  - pipeline/
  - storage/
- tests/
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

## Phase 1 Local Setup

Install local development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Generate Python gRPC modules after dependencies are installed:

```bash
python -m grpc_tools.protoc -I proto --python_out=src/chatbot_service/generated --grpc_python_out=src/chatbot_service/generated proto/chatbot/v1/chatbot.proto
```

Check configuration without starting gRPC:

```bash
chatbot-service --check-config
```

Start the skeleton server:

```bash
chatbot-service
```

`AskChatbot`, `GetConversation`, and `RecordChatbotFeedback` currently return
`UNIMPLEMENTED`. Integration with auth-service, recommendation-service, and
map-service is intentionally left as Phase 2+ work.
