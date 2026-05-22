# AI Agent Harness — ONTHEBLOCK AI Chatbot Service

## Purpose

This harness defines how an AI agent must work in this repository.

It prevents boundary violations, accidental production changes, hallucination-
prone chatbot behavior, and undocumented API/storage changes.

---

## Required Working Loop

For every non-trivial task, follow this loop.

### 1. Read

Read:

1. `AGENTS.md`
2. `.agent/DOMAIN_BOUNDARIES.md`
3. Relevant `docs/chatbot/*` files
4. Relevant API/proto/storage files
5. Existing implementation files that will be changed

Do not rely on memory when files are available.

### 2. Inspect

Before changing code, inspect:

- Existing file layout.
- Existing service/API contracts.
- Existing environment variables.
- Existing tests.
- Existing migrations.
- Existing generated code patterns.

### 3. Summarize

Return a short summary:

```text
Current state:
Relevant files:
Missing contracts:
Risk areas:
```

### 4. Plan

Write a small plan using `.agent/EXEC_PLAN_TEMPLATE.md`.

The plan must mention:

- Boundary impact.
- API impact.
- Storage/migration impact.
- Test plan.
- Rollback/safety notes.

### 5. Implement Small Steps

Implement in the smallest safe unit.

Prefer:

- One contract change at a time.
- One migration at a time.
- One adapter at a time.
- One guardrail at a time.

Avoid large rewrites.

### 6. Verify

Run all relevant checks available in the repo.

Examples:

```bash
python -m pytest
python -m ruff check .
python -m mypy .
python -m grpc_tools.protoc ...
```

If checks are not configured, state that clearly and propose the missing check.

### 7. Report

Finish with:

```text
Summary:
Files changed:
Boundary impact:
API impact:
Storage impact:
Tests/checks run:
Remaining risks:
Next recommended step:
```

---

## Change Approval Triggers

Ask for confirmation before:

- Adding or changing gRPC API shape.
- Adding chatbot storage tables.
- Adding migrations.
- Adding an LLM provider dependency.
- Changing auth behavior.
- Changing map/recommendation service ownership assumptions.
- Storing conversation logs for future learning.
- Touching production deployment config.

---

## Safety Rules

- Never commit secrets.
- Never add service-account JSON keys.
- Never hardcode LLM credentials.
- Never read another service's database directly.
- Never allow request body `user_id` for authenticated chatbot actions.
- Never make LLM output the source of truth for ranking.
- Never invent app data.

---

## Chatbot-Specific Guardrail Checks

Before completing chatbot work, verify:

- Out-of-scope questions are refused.
- Insufficient-data responses say that data is missing.
- Recommendations only use returned candidates.
- Response cards preserve source IDs internally.
- LLM prompt says not to invent facts.
- Prompt includes Korean polite response style.
- Used sources and missing facts are tracked.
