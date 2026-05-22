# AI Assistant gRPC API Contract

## Purpose

This document drafts the `ai-assistant-service` gRPC API. It records the current intended API shape while implementation is still in progress.

## Identity Rules

The client must not send `user_id` in the request body. Caller identity is resolved from authenticated context.

```text
Authorization: Bearer <access_token>
```

## Service Draft

```proto
syntax = "proto3";

package ontheblock.assistant.v1;

import "google/protobuf/timestamp.proto";

service AssistantService {
  rpc AskAssistant(AskAssistantRequest) returns (AskAssistantResponse);
  rpc GetConversation(GetConversationRequest) returns (GetConversationResponse);
  rpc RecordAssistantFeedback(RecordAssistantFeedbackRequest) returns (RecordAssistantFeedbackResponse);
}
```

## `AskAssistant`

Purpose:

- Process one user message.
- Classify intent.
- Fetch grounded recommendation/map/profile facts.
- Generate a polite Korean response.
- Return card data for Flutter rendering.
- Store conversation if configured.

Request draft:

```json
{
  "conversation_id": "optional-conv-id",
  "message": "내 취향에 맞는 술을 추천해줘",
  "lat": 37.123,
  "lng": 127.123,
  "radius_m": 1500,
  "budget_hint_krw": 30000,
  "screen_context": "HOME"
}
```

Response draft:

```json
{
  "conversation_id": "conv_123",
  "message_id": "msg_456",
  "intent": "RECOMMEND_BEVERAGE",
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
| `BEVERAGE_CARD` | Alcohol recommendation |
| `VENUE_CARD` | Nearby venue/store/bar |
| `PURCHASE_OPTION_CARD` | Price/distance/stock option |
| `COMPARISON_CARD` | Compare nearest/best price/balanced |
| `PROFILE_STATUS_CARD` | Profile missing/pending/stale/failed |

## Dependency Calls

The assistant may call:

```text
RecommendationService.GetProfileStatus
RecommendationService.GetBeverageRecommendations
RecommendationService.GetVenueRecommendations
RecommendationService.RecordRecommendationEvent
```

It may call auth/map services only through approved service APIs.

## Error Behavior

The assistant should return typed assistant responses instead of pretending to know.

| Case | Response |
|---|---|
| Missing profile | `INSUFFICIENT_DATA`, explain profile is not ready |
| Pending profile | `PROFILE_STATUS`, explain generation is pending |
| Missing location | Ask for location or use coarse location only |
| No candidate | Say current app data has no reliable match |
| Out of scope | Refuse politely |
