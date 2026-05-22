# Execution Plan Template

Use this template before non-trivial code or documentation work.

## Task

```text
<one-sentence task summary>
```

## Current State Summary

- Existing files:
- Existing behavior:
- Missing pieces:
- Relevant docs:

## Boundary Impact

| Boundary | Impact | Notes |
|---|---|---|
| Auth identity/JWT | none/low/medium/high | |
| Survey ownership | none/low/medium/high | |
| Recommendation ranking | none/low/medium/high | |
| Map/place data | none/low/medium/high | |
| Chatbot storage | none/low/medium/high | |
| LLM prompt behavior | none/low/medium/high | |
| Deployment/secrets | none/low/medium/high | |

## Files To Add/Change

```text
<file path> - <why>
```

## API Impact

- New RPCs:
- Changed RPCs:
- Backward compatibility:
- Auth metadata requirements:

## Storage Impact

- New tables:
- Changed tables:
- Migration needed:
- Data retention:

## RAG / LLM Impact

- Prompt changes:
- Context changes:
- No-answer behavior:
- Output schema changes:

## Test Plan

- Unit tests:
- Integration tests:
- Contract tests:
- Evaluation cases:
- Manual test:

## Rollback Plan

- How to revert safely:
- Data cleanup if needed:

## Open Questions

1.
2.
3.
