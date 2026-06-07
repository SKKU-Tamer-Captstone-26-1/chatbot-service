# 015 Production Routing Hardening (MVP Stability)

## Goal

Reduce repetitive / incorrect responses for venue and follow-up beverage flows by
improving chatbot-side intent shaping and request construction while keeping
recommendation-service as the ranking authority.

## Current State Summary

- Recommendation-service is still the only source of ranking and candidate data.
- `recommend-beverage` and `venue` intents are supported.
- Conversation context can be reused when `conversation_id` is provided.

## Hardening Items

1. Improve intent routing robustness with clearer venue-first phrase matching for
   Korean UI phrasing (`근처`, `주변`, `바`, `술집`, `구매처`, `가볼만`, etc.).
2. Pass venue context filters (`exclude_*`, `diversity_mode`, `session_context_id`)
   to `GetVenueRecommendations` so alternative place questions can change behavior.
3. Resolve `selected_beverage_id` from request body or `client_context` fallback
   before venue recommendation calls.
4. Add dedicated intent-classifier and context-builder tests for:
   - venue phrase coverage
   - fallback venue selection via client context
   - venue request forwarding of diversity/exclusion filters

## Validation

- Unit tests:
  - `tests/test_intent_classifier.py` (new)
  - `tests/test_chatbot_pipeline.py` (existing + focused additions)
- Acceptance checks:
  - Different follow-up phrases for venue/drink queries no longer collapse to the
    same call shape
  - Venue follow-up path forwards context keys to recommendation-service
  - No code path assigns recommendation candidates without `recommendation-service` call
