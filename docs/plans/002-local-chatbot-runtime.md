# 002 Local Chatbot Runtime

## Goal

Run chatbot-service locally with deterministic behavior and no production
dependencies.

## Deliverables

- Python gRPC server starts from `chatbot-service`.
- Health check is registered.
- Config loader reads runtime environment variables.
- Pipeline supports intent classification, grounded context assembly, prompt
  building, LLM adapter, response verification, and response card generation.
- Fake/local adapters support tests without real external services.

## Acceptance Gate

- `python3 -m ruff check .` succeeds.
- `python3 -m pytest` succeeds.
- A local `AskChatbot` request returns either a grounded answer, an
  insufficient-data response, or a refusal.
- The service never requires trusted `user_id` in the public request body.

## Current Status

Implemented.

## Next Step

Continue with `003-recommendation-grounding.md`.
