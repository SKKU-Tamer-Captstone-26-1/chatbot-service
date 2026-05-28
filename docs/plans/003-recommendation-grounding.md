# 003 Recommendation Grounding

## Goal

Use recommendation-service as the only source for ranked recommendation facts.

## Deliverables

- Chatbot calls recommendation-service for profile status, beverage
  recommendations, and venue recommendations.
- Chatbot preserves recommendation request IDs, result IDs, rank, reason codes,
  profile revision, freshness, and availability metadata.
- Chatbot converts recommendation outputs into structured cards.
- Response verifier rejects answers when evidence is missing or unsupported.

## Acceptance Gate

- Beverage, venue, and purchase option cards include source result IDs.
- Answered recommendation responses expose `used_sources`.
- Tests prove card order follows recommendation-service order.
- Missing profile, missing location, no candidates, or stale facts return
  insufficient-data behavior instead of invented facts.

## Current Status

Implemented.

## Next Step

Continue with `004-storage-feedback-learning-readiness.md`.
