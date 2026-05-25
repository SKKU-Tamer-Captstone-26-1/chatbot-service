# AI Chatbot gRPC API Contract

## Purpose

This document drafts the `ai-chatbot-service` gRPC API. It records the current intended API shape while implementation is still in progress.

## Identity Rules

The client must not send `user_id` in the request body. Caller identity is resolved from authenticated context.

```text
Authorization: Bearer <access_token>
```

## Service Draft

```proto
syntax = "proto3";

package ontheblock.chatbot.v1;

option java_package = "com.ontheblock.chatbot.v1";
option java_multiple_files = true;
option go_package = "github.com/ontheblock/infra/proto/chatbot/v1;chatbotv1";

import "google/protobuf/struct.proto";
import "google/protobuf/timestamp.proto";

service ChatbotService {
  rpc AskChatbot(AskChatbotRequest) returns (AskChatbotResponse);
  rpc GetConversation(GetConversationRequest) returns (GetConversationResponse);
  rpc RecordChatbotFeedback(RecordChatbotFeedbackRequest) returns (RecordChatbotFeedbackResponse);
}
```

## `AskChatbot`

Purpose:

- Process one user message.
- Classify intent.
- Fetch grounded recommendation/map/profile facts.
- Generate a polite Korean response.
- Return card data for Flutter rendering.
- Store conversation if configured.
- Avoid loading full conversation history by default.
- Use cached grounded service responses only when freshness and source identity
  are valid.

Request draft:

```json
{
  "conversation_id": "optional-conv-id",
  "message": "내 취향에 맞는 술을 추천해줘",
  "lat": 37.123,
  "lng": 127.123,
  "radius_m": 1500,
  "budget_hint_krw": 30000,
  "screen_context": "HOME",
  "selected_beverage_id": "optional-bev-id",
  "category": "whiskey",
  "beverage_limit": 5,
  "venue_limit": 3,
  "budget_mode": "BUDGET_MODE_SOFT",
  "client_context": {}
}
```

Response draft:

```json
{
  "conversation_id": "conv_123",
  "message_id": "msg_456",
  "intent": "RECOMMEND_BEVERAGE",
  "status": "CHATBOT_RESPONSE_STATUS_ANSWERED",
  "profile_status": "PROFILE_STATUS_ACTIVE",
  "answer": "현재 취향 데이터 기준으로는 ...",
  "confidence": 0.82,
  "refused": false,
  "refusal_reason": "",
  "cards": [],
  "used_sources": {},
  "missing_facts": [],
  "follow_up_questions": []
}
```

## Card Types

| Card Type | Use |
|---|---|
| `CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION` | Ranked beverage recommendation returned by recommendation-service |
| `CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION` | Ranked venue recommendation returned by recommendation-service |
| `CHATBOT_CARD_TYPE_PURCHASE_OPTION` | Price/distance/availability option derived from returned venue results |
| `CHATBOT_CARD_TYPE_COMPARISON` | Compare nearest/best price/balanced returned options |
| `CHATBOT_CARD_TYPE_PROFILE_STATUS` | Profile missing/pending/stale/failed |

Cards expose common display fields plus one typed detail payload:

```text
ChatbotCard
  title
  subtitle
  display_reason
  reason_codes
  metadata
  oneof detail:
    BeverageRecommendationCard
    VenueRecommendationCard
    PurchaseOptionCard
    ComparisonCard
    ProfileStatusCard
```

`BeverageRecommendationCard` mirrors the recommendation-service beverage result
fields: `rank`, `result_id`, `beverage_id`, `name_ko`, `name_en`, `category`,
`score`, `reason_codes`, `explanation`, and `metadata`.

`VenueRecommendationCard` mirrors the recommendation-service venue result
fields: `rank`, `result_id`, `place_id`, `name`, `place_type`, `address`,
`option_type`, `distance_m`, `price_krw`, `availability_status`,
`freshness_status`, `score`, `reason_codes`, `explanation`, and `metadata`.

The chatbot contract repeats recommendation-facing enums in the chatbot package
for client rendering, but recommendation-service remains the owner of ranking
and score semantics.

## Dependency Calls

The chatbot may call:

```text
RecommendationService.GetProfileStatus
RecommendationService.GetBeverageRecommendations
RecommendationService.GetVenueRecommendations
RecommendationService.RecordRecommendationEvent
```

It may call auth/map services only through approved service APIs.

## Cost and Concurrency Notes

For production traffic, `AskChatbot` should be optimized around upstream
service calls, not PostgreSQL conversation reads. The service should not read
full history on every request.

Recommendation-service should own the primary cache for deterministic ranking.
ai-chatbot-service may keep a thin Redis/Memorystore cache for profile status,
recommendation responses, and compact prompt context. Cache keys must include
profile revision, filters, and a location bucket for venue queries.

Client apps should send a request only when the user submits a message, not on
typing events. Feedback requests already include `idempotency_key` for safe
retries.

## Feedback

`RecordChatbotFeedback` uses typed feedback events and
`google.protobuf.Struct metadata`, matching the recommendation-service metadata
shape. The request also carries an `idempotency_key` so clients can retry safely.

## Error Behavior

The chatbot should return typed chatbot responses instead of pretending to know.

| Case | Response |
|---|---|
| Missing profile | `INSUFFICIENT_DATA`, explain profile is not ready |
| Pending profile | `PROFILE_STATUS`, explain generation is pending |
| Missing location | Ask for location or use coarse location only |
| No candidate | Say current app data has no reliable match |
| Out of scope | Refuse politely |
