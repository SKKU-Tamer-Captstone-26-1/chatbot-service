# Codex Bootstrap Prompt for AI Assistant Service

Use this prompt when starting the first agent task in the AI assistant repository.

```text
We are building the ONTHEBLOCK AI assistant/chatbot service.

Context:
- The chatbot is a separate Python/gRPC service, not chat-service.
- It appears as a modal from Home and Board screens.
- It answers only ONTHEBLOCK-domain questions about alcohol recommendations, user taste/preferences, nearby venues, prices, inventory, distance, and recommendation explanations.
- It must answer in polite Korean.
- It should return card-friendly structured responses.
- Assistant conversations should be stored for future evaluation/training, but do not implement model training yet.

Before editing, read:
- AGENT.md
- .agent/HARNESS.md
- .agent/DOMAIN_BOUNDARIES.md
- .agent/ACCEPTANCE_CHECKLIST.md

Existing platform rules:
- auth-service owns authentication, Google OAuth, JWT issuing, and user identity.
- survey-service owns raw survey answers and survey schema.
- recommendation-service owns derived taste profiles, vectors, scoring metadata, and recommendation logs.
- map-service/place-service owns canonical place, menu, inventory, price, and location data.
- recommendation-service consumes map/place data as snapshots/read models only.
- RAG must not be used as the recommendation ranking engine.
- LLM must not invent alcohols, places, prices, inventory, distances, or user preferences.

First task:
1. Inspect the repository structure.
2. Confirm whether docs/assistant exists.
3. Confirm whether proto/assistant/v1/assistant.proto exists.
4. Confirm whether src/assistant_service exists.
5. Summarize what is present and missing.
6. Propose the next small implementation step.
7. Do not implement code until the plan is clear.

Expected output:
- Current state summary
- Missing files/folders
- Proposed next step
- Risks
```
