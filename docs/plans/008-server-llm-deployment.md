# 008 Server LLM Deployment

## Goal

Run the fine-tuned response-generation model behind a backend endpoint.

## Default Approach

- Train or fine-tune outside chatbot-service.
- Serve the selected checkpoint through an OpenAI-compatible
  `/v1/chat/completions` API.
- Use Cloud Run GPU with vLLM/TGI, Vertex AI endpoint, or a private managed
  Hugging Face/TGI endpoint depending on cost and operational constraints.

## Runtime Contract

```text
CHATBOT_LLM_PROVIDER=huggingface_tgi
CHATBOT_LLM_ENDPOINT_URL=<openai-compatible-chat-completions-url>
CHATBOT_LLM_MODEL=<model-or-endpoint-name>
CHATBOT_LLM_AUTH_MODE=none|bearer_env
CHATBOT_LLM_API_KEY_ENV=<required only when bearer_env>
```

## Deliverables

- Local/private LLM endpoint support does not require API key env when
  `CHATBOT_LLM_AUTH_MODE=none`.
- Remote secured endpoint support requires bearer token from env.
- LLM timeout and max-token settings are configurable.
- Prompt remains compact and fact-only.

## Acceptance Gate

- LLM adapter returns a concise Korean response from provided facts.
- LLM timeout produces safe fallback behavior.
- Endpoint auth failure fails fast in staging preflight.
- LLM output cannot add cards, sources, or ranked candidates.

## Current Status

Provider abstraction exists. Auth-mode config and deployment target still need
implementation and human choice.

## Next Step

Continue with `009-evaluation-release-gates.md`.
