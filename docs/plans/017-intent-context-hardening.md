# 017 Production Intent Context Hardening

## Task

Improve routing determinism for follow-up chat messages by using lightweight
conversation intent context, so a venue-focused follow-up does not incorrectly
fall back to beverage recommendations.

## Current State Summary

- Existing files:
  - `src/chatbot_service/pipeline/intent_classifier.py`
  - `src/chatbot_service/pipeline/chatbot_pipeline.py`
  - `src/chatbot_service/storage/...` conversation retrieval logic
  - `src/chatbot_service/pipeline/context_builder.py`
  - `tests/test_intent_classifier.py`
  - `tests/test_chatbot_pipeline.py`
- Existing behavior:
  - `IntentClassifier` is rule-only and uses only raw message text.
  - Conversation context is applied after initial intent classification.
  - Venue follow-ups can be ambiguous and may be classified as beverage intent
    when the message is short (e.g., “다른 곳 추천해줘”).
- Missing pieces:
  - Context-based reclassification for ambiguous short follow-ups.
  - Explicit extraction of last assistant intent from conversation metadata.
  - Regression tests for venue follow-up misrouting.

## Boundary Impact

| Boundary | Impact | Notes |
|---|---|---|
| Auth identity/JWT | none | unchanged |
| Survey ownership | none | unchanged |
| Recommendation ranking | none | unchanged |
| Map/place data | none | unchanged |
| Chatbot storage | low | reads message metadata for intent context |
| LLM prompt behavior | none | unchanged |
| Deployment/secrets | none | no config/secrets change |

## Files To Add/Change

- `src/chatbot_service/pipeline/intent_classifier.py` - add optional `previous_intent`
  reclassification rules for short follow-up venue prompts.
- `src/chatbot_service/pipeline/chatbot_pipeline.py` - load lightweight
  conversation context once, then classify with prior intent before building
  request context.
- `src/chatbot_service/pipeline/chatbot_pipeline.py` - keep conversation hint
  extraction independent of request intent and store last assistant intent from
  history.
- `tests/test_intent_classifier.py` - add follow-up intent reclassification tests.
- `tests/test_chatbot_pipeline.py` - add regression test for venue follow-up routing.
- `docs/plans/README.md` - append plan index entry for 017.

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
- Context changes: uses conversation-intent metadata only for routing; grounded
  retrieval remains unchanged.
- No-answer behavior: unchanged
- Output schema changes: none

## Test Plan

- Unit tests:
  - `tests/test_intent_classifier.py` (venue follow-up + explicit beverage follow-up
    should stay beverage)
- Integration-style unit tests:
  - `tests/test_chatbot_pipeline.py` (ambiguous follow-up with venue history)
- Contract/behavior checks:
  - No added calls to recommendation-service beverage path for venue follow-up.
- Manual test:
  - In real flow, after venue question history, user asks “다른 곳 추천해줘”.
    system should still call venue flow and request selected beverage from history.

## Rollback Plan

- Safe rollback:
  - Revert classifier heuristic change and context-hint reordering.
- Data cleanup if needed:
  - none
