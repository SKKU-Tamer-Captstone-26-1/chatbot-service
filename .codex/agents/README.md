# Chatbot Codex Agents

Repo-local Codex subagent definitions for ONTHEBLOCK `ai-chatbot-service`.

Codex discovers project subagents from `.codex/agents/*.toml`. Each agent file
uses the real Codex custom-agent schema: `name`, `description`, and
`developer_instructions`, with optional settings such as `sandbox_mode`,
`model_reasoning_effort`, and `nickname_candidates`.

These agents are intentionally concise. Their instructions reference the
source-of-truth repo files instead of copying them:

- `AGENT.md`
- `.agent/HARNESS.md`
- `.agent/DOMAIN_BOUNDARIES.md`
- `.agent/ACCEPTANCE_CHECKLIST.md`

## Agents

| Agent | Use when |
|---|---|
| `chatbot-harness-planner.toml` | A chatbot task is broad enough to need a harness plan before edits. |
| `chatbot-implementer.toml` | Implementing chatbot pipeline, clients, guardrails, storage, or docs end to end. |
| `chatbot-proto-contract.toml` | Changing or reviewing chatbot gRPC/proto/API contracts. |
| `chatbot-safety-reviewer.toml` | Reviewing changes for service boundaries, hallucination risk, and missing checks. |

## Config

`.codex/config.toml` sets a small project-local multi-agent limit:

```toml
[agents]
max_threads = 6
max_depth = 1
```

## Shared Defaults

- Keep responses concise, but include the concrete files, checks, and risks.
- Read local context before making claims.
- Use recommendation-service outputs as authoritative ranking.
- Do not accept trusted `user_id` from public chatbot request bodies.
- Do not read survey-service, map-service, or place-service databases directly.
- Do not hardcode secrets or provider credentials.
- Update docs when API, storage, prompt, RAG, or response behavior changes.
