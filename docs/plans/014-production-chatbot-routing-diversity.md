# 014 Production Chatbot Routing And Diversity

## Goal

Move chatbot behavior from a simple recommendation explanation MVP toward a
production-level assistant that routes beverage, venue, comparison, profile, and
follow-up requests correctly without breaking service boundaries.

## Current Problem

Observed Flutter behavior:

- A user asks for place or venue recommendations, but the chatbot can still show
  beverage recommendations.
- A user asks for another drink recommendation, but receives the same ranked
  response again.

Root causes:

- Intent routing was too shallow and treated many Korean place phrases as a
  generic beverage recommendation because they contained "추천".
- Venue recommendation requires `selected_beverage_id` and detailed location.
  If Flutter does not pass those fields, chatbot-service must ask for missing
  information instead of falling back to beverage recommendations.
- Different or alternative recommendation requests need recommendation-service
  support. Chatbot-service must not filter or rerank recommendation results by
  itself.

## Immediate Backend Fix

Chatbot-service should:

- Classify venue phrases such as `장소`, `바`, `펍`, `술집`, `매장`, `가게`,
  `보틀샵`, `근처`, `주변`, `마실 곳`, and `구매처` as venue intent.
- Keep beverage recommendation intent for beverage, taste, and drink requests.
- Return a deterministic Korean missing-info response when venue intent lacks
  `lat/lng` or `selected_beverage_id`.
- Never substitute beverage cards for a venue request.

## Production Contract Needed

To support "다른 술 추천해줘" correctly, recommendation-service should own the
diversity behavior.

Additive recommendation-service contract options:

```text
GetBeverageRecommendationsRequest
- exclude_beverage_ids: repeated string
- exclude_result_ids: repeated string
- diversity_mode: enum
  - DIVERSITY_MODE_UNSPECIFIED
  - DIVERSITY_MODE_MORE_LIKE_THIS
  - DIVERSITY_MODE_DIFFERENT_STYLE
  - DIVERSITY_MODE_EXPLORE
- session_context_id: string
```

Chatbot-service may pass prior `beverage_ids` or `result_ids` from chatbot
conversation context, but recommendation-service must still decide the final
ranked order.

Chatbot-service must not:

- Drop top-ranked items by itself.
- Rotate cards locally.
- Reorder candidates.
- Pretend a repeated result is new.

## Conversation Context Direction

Production chatbot should use conversation history only for intent and request
construction, not as ranking truth.

Allowed:

- Detect follow-up phrases such as "다른 거", "말고", "비슷한 거", and
  "좀 더 달콤한 거".
- Read prior assistant `used_sources.beverage_ids` and `beverage_result_ids`.
- Pass those IDs to recommendation-service when the API supports exclusion or
  diversity.
- Preserve backend order in the final response.

Forbidden:

- Use chatbot logs as canonical taste profile.
- Generate hidden filters not supported by recommendation-service.
- Let the LLM pick the final recommendation list.

## Flutter Requirements

Flutter should pass:

- `conversation_id` for follow-up questions.
- `lat/lng/radius_m` when the user asks for nearby venue/place recommendations
  and location permission is available.
- `selected_beverage_id` when the user asks where to buy or drink a specific
  recommendation.

Flutter should not:

- Replace venue insufficient-data responses with beverage recommendation UI.
- Show `recommendation_service_unavailable` as "프로필 준비 필요".
- Call recommendation-service directly for chatbot messages.

## Acceptance Criteria

- "장소 추천해줘" does not return beverage cards.
- "근처 바 추천해줘" routes to venue intent.
- Venue intent without location asks for location.
- Venue intent without selected beverage asks the user to select or specify a
  beverage.
- Venue intent with location and selected beverage calls
  `GetVenueRecommendations`.
- "다른 술 추천해줘" does not claim diversity unless recommendation-service
  returns different ranked results.
- Once recommendation-service supports exclude/diversity fields, chatbot passes
  prior result IDs from conversation context and still preserves returned order.

## Next Implementation Steps

1. Deploy chatbot-service intent and venue-missing-info fix.
2. Verify Flutter sends `conversation_id`, location fields, and
   `selected_beverage_id`.
3. Fix gateway/Flutter response mapping for unavailable recommendation-service
   responses.
4. Add recommendation-service diversity/exclusion API fields.
5. Add chatbot conversation-context request builder for follow-up diversity
   requests.
6. Add end-to-end tests through gateway for beverage, venue, comparison, and
   alternative recommendation flows.
