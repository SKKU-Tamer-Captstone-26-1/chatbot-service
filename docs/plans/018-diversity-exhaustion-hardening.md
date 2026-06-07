# 018 Diversity Exhaustion Hardening

## Task

Prevent repetitive follow-up answers when the user asks for alternative
recommendations (e.g., "다른 술 추천해줘" / "다른 장소 추천해줘") but
`recommendation-service` returns no additional candidates.

## Current State Summary

- Existing files:
  - `src/chatbot_service/pipeline/context_builder.py`
  - `src/chatbot_service/pipeline/guardrails.py`
  - `tests/test_chatbot_pipeline.py`
- Existing behavior:
  - Follow-up diversity flags are passed to `recommendation-service`.
  - Chatbot still trusts returned list even if it completely overlaps the prior
    result set.
  - User gets repeated recommendation cards.
- Missing pieces:
  - Diversity fallback when returned set provides no fresh results.
  - Dedicated insufficient-data wording for exhausted diversity flows.

## Boundary Impact

| Boundary | Impact | Notes |
|---|---|---|
| Auth identity/JWT | none | no change |
| Survey ownership | none | no change |
| Recommendation ranking | none | ranking still from recommendation-service |
| Map/place data | none | no change |
| Chatbot storage | low | no schema change |
| LLM prompt behavior | low | avoids unnecessary LLM calls |
| Deployment/secrets | none | no change |

## Files To Add/Change

- `src/chatbot_service/pipeline/context_builder.py` - detect no-new-results after
  diversity requests and return a grounded missing-facts context.
- `src/chatbot_service/pipeline/guardrails.py` - add explicit insufficient-data
  response for exhausted diversity candidates.
- `tests/test_chatbot_pipeline.py` - regression tests for repeated-beverage and
  repeated-venue diversity fallback.

## API Impact

- New RPCs: none
- Changed RPCs: none
- Backward compatibility: none
- Auth metadata requirements: no change

## Storage Impact

- New tables: none
- Changed tables: none
- Migration needed: no
- Data retention: no change

## RAG / LLM Impact

- Prompt changes: none
- Context changes: preserve recommendation order, but add no-new-result check
  for follow-ups.
- No-answer behavior: return `INSUFFICIENT_DATA` if no fresh result appears.
- Output schema changes: none

## Test Plan

- Unit tests:
  - `tests/test_chatbot_pipeline.py`
- Contract checks:
  - recommendation service still called once for diverse follow-up.
  - LLM not invoked when no fresh candidates exist.

## Rollback Plan

- Revert this plan file and three-file patch if recommendation-service starts
  returning partial duplicate sets too often.
