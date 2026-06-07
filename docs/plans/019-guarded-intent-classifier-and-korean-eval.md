# 019 Guarded Intent Classifier And Korean Eval

## Task

Move intent routing beyond first-match keyword rules by adding a small guarded
intent scorer and expanding Korean evaluation cases for unavailable, venue, and
follow-up behavior.

## Current State Summary

- Existing files:
  - `src/chatbot_service/pipeline/intent_classifier.py`
  - `tests/test_intent_classifier.py`
  - `evaluation/korean_tone_cases.yaml`
  - `evaluation/no_answer_cases.yaml`
- Existing behavior:
  - Routing uses ordered keyword checks.
  - Venue terms are checked before beverage terms, but comparison terms such as
    `가격` can still over-capture recommendation questions.
  - Evaluation fixtures cover basic Korean tone but not gateway-problem fallback
    language or repeated follow-up exhaustion.
- Missing pieces:
  - A score-based classifier that handles mixed Korean utterances by purpose.
  - Fixture coverage for service-unavailable, missing venue context, and repeated
    alternative recommendation fallback.

## Boundary Impact

| Boundary | Impact | Notes |
|---|---|---|
| Auth identity/JWT | none | no change |
| Survey ownership | none | no change |
| Recommendation ranking | none | no local ranking/filtering |
| Map/place data | none | no direct map DB reads |
| Chatbot storage | none | no schema change |
| LLM prompt behavior | none | LLM is not used for routing |
| Deployment/secrets | none | no config/secrets change |

## Files To Add/Change

- `src/chatbot_service/pipeline/intent_classifier.py` - replace first-match route
  selection with guarded score-based intent selection.
- `tests/test_intent_classifier.py` - add mixed-intent Korean regression cases.
- `evaluation/korean_tone_cases.yaml` - add venue and exhausted-follow-up tone
  cases.
- `evaluation/no_answer_cases.yaml` - add recommendation-service-unavailable
  no-answer case.

## API Impact

- New RPCs: none
- Changed RPCs: none
- Backward compatibility: no API change
- Auth metadata requirements: no change

## Storage Impact

- New tables: none
- Changed tables: none
- Migration needed: no
- Data retention: no change

## RAG / LLM Impact

- Prompt changes: none
- Context changes: none
- No-answer behavior: fixture coverage expanded only
- Output schema changes: none

## Test Plan

- Unit tests:
  - `tests/test_intent_classifier.py`
  - `tests/test_evaluation_fixtures.py`
- Regression tests:
  - full `pytest`

## Rollback Plan

- Revert classifier scoring change and new fixture cases if production routing
  shows worse precision.
