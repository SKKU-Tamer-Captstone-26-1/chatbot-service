# 008 Server LLM Deployment

## Goal

Run the MVP response-generation model behind a backend endpoint.

## Default Approach

- Do not train or fine-tune the open LLM for MVP.
- Serve the selected base instruction model through an OpenAI-compatible
  `/v1/chat/completions` API.
- Use Hugging Face Inference Endpoint + TGI for the first deployment.
- Keep recommendation-service as ranking, score, reason-code, and candidate
  owner. The LLM only rewrites provided grounded facts into Korean prose.

## Runtime Contract

```text
CHATBOT_LLM_PROVIDER=huggingface_tgi
CHATBOT_LLM_ENDPOINT_URL=<openai-compatible-chat-completions-url>
CHATBOT_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
CHATBOT_LLM_AUTH_MODE=none|bearer_env
CHATBOT_LLM_API_KEY_ENV=<required only when bearer_env>
```

## Deliverables

- Local/private LLM endpoint support does not require API key env when
  `CHATBOT_LLM_AUTH_MODE=none`.
- Remote secured endpoint support requires bearer token from env.
- LLM timeout and max-token settings are configurable.
- Prompt remains compact and fact-only.
- Out-of-scope, no-evidence, and context-missing cases are blocked by policy
  and verifier behavior, not by model fine-tuning.

## Acceptance Gate

- LLM adapter returns a concise Korean response from provided facts.
- LLM timeout produces safe fallback behavior.
- Endpoint auth failure fails fast in staging preflight.
- LLM output cannot add cards, sources, or ranked candidates.

## Current Status

Provider abstraction exists. MVP model choice is
`Qwen/Qwen2.5-7B-Instruct` served through Hugging Face Inference Endpoint/TGI.
The actual endpoint URL and `HF_TOKEN` remain human-provided secrets.

## Next Step

Continue with `009-evaluation-release-gates.md`.
