# Chatbot Response Schema

## Purpose

This document defines the chatbot response structure for Flutter rendering and later training/logging.

## Top-Level Response

```json
{
  "conversation_id": "conv_123",
  "message_id": "msg_456",
  "intent": "FIND_NEARBY_VENUE",
  "answer": "현재 확인 가능한 데이터 기준으로는 아래 선택지가 좋아 보여요.",
  "confidence": 0.82,
  "refused": false,
  "refusal_reason": "",
  "cards": [],
  "used_sources": {},
  "missing_facts": [],
  "follow_up_questions": []
}
```

## Card Schema

### Beverage Card

```json
{
  "card_type": "BEVERAGE_CARD",
  "title": "Example Bourbon",
  "subtitle": "스모키하고 바디감 있는 위스키",
  "score": 0.91,
  "reason_codes": ["MATCHES_SMOKY_PROFILE", "BEGINNER_FRIENDLY"],
  "display_reason": "스모키한 향과 바디감 선호에 잘 맞아요."
}
```

### Venue Card

```json
{
  "card_type": "VENUE_CARD",
  "title": "Example Bottle Shop",
  "subtitle": "근처 보틀샵",
  "distance_m": 180,
  "estimated_travel_time_sec": 240,
  "availability_status": "IN_STOCK",
  "price_krw": 8500,
  "confidence": 0.76,
  "display_reason": "조금 비싸지만 가장 가까운 선택지예요."
}
```

### Purchase Option Card

```json
{
  "card_type": "PURCHASE_OPTION_CARD",
  "option_type": "nearest_reasonable",
  "place_name": "Example Store",
  "beverage_name": "Example Bourbon",
  "price_krw": 8500,
  "distance_m": 120,
  "availability_status": "LOW_STOCK",
  "display_reason": "500원 비싸지만 바로 앞에 가까운 선택지예요."
}
```

## Internal Source Metadata

```json
{
  "used_sources": {
    "profile_revision": 4,
    "recommendation_request_id": "rec_req_123",
    "place_ids": ["place_123"],
    "beverage_ids": ["bev_123"],
    "reason_codes": ["NEARBY_VENUE", "WITHIN_BUDGET"]
  }
}
```

## Refusal Response

```json
{
  "intent": "OUT_OF_SCOPE",
  "answer": "저는 ONTHEBLOCK의 술 추천, 취향, 주변 장소 정보에 대해서만 도와드릴 수 있어요.",
  "confidence": 1.0,
  "refused": true,
  "refusal_reason": "OUT_OF_SCOPE",
  "cards": []
}
```
