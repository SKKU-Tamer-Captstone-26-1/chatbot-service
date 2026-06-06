# Chatbot Response Schema

## Purpose

This document defines the chatbot response structure for Flutter rendering,
logging, evaluation, and future training after policy approval.

## Top-Level Response

```json
{
  "conversation_id": "conv_123",
  "message_id": "msg_456",
  "intent": "FIND_NEARBY_VENUE",
  "status": "CHATBOT_RESPONSE_STATUS_ANSWERED",
  "profile_status": "PROFILE_STATUS_ACTIVE",
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

All cards include common rendering fields plus one typed detail payload:

```json
{
  "card_type": "CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION",
  "title": "Example Bourbon",
  "subtitle": "스모키하고 바디감 있는 위스키",
  "display_reason": "스모키한 향과 바디감 선호에 잘 맞아요.",
  "reason_codes": ["MATCHES_SMOKY_PROFILE", "BEGINNER_FRIENDLY"],
  "metadata": {},
  "beverage_recommendation": {}
}
```

### Beverage Card

```json
{
  "card_type": "CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION",
  "title": "Example Bourbon",
  "subtitle": "스모키하고 바디감 있는 위스키",
  "reason_codes": ["MATCHES_SMOKY_PROFILE", "BEGINNER_FRIENDLY"],
  "display_reason": "스모키한 향과 바디감 선호에 잘 맞아요.",
  "beverage_recommendation": {
    "rank": 1,
    "result_id": "bev_result_123",
    "beverage_id": "bev_123",
    "name_ko": "Example Bourbon",
    "name_en": "Example Bourbon",
    "category": "whiskey",
    "score": 0.91,
    "reason_codes": ["MATCHES_SMOKY_PROFILE", "BEGINNER_FRIENDLY"],
    "explanation": "스모키한 향과 바디감 선호에 잘 맞아요.",
    "metadata": {}
  }
}
```

### Venue Card

```json
{
  "card_type": "CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION",
  "title": "Example Bottle Shop",
  "subtitle": "근처 보틀샵",
  "display_reason": "조금 비싸지만 가장 가까운 선택지예요.",
  "venue_recommendation": {
    "rank": 1,
    "result_id": "venue_result_123",
    "place_id": "place_123",
    "name": "Example Bottle Shop",
    "place_type": "bottle_shop",
    "address": "서울시 예시로 1",
    "option_type": "VENUE_OPTION_TYPE_NEAREST_REASONABLE",
    "distance_m": 180.0,
    "estimated_travel_time_sec": 240,
    "availability_status": "VENUE_AVAILABILITY_STATUS_AVAILABLE",
    "freshness_status": "VENUE_FRESHNESS_STATUS_FRESH",
    "price_krw": 8500,
    "score": 0.76,
    "reason_codes": ["NEARBY_VENUE"],
    "explanation": "조금 비싸지만 가장 가까운 선택지예요.",
    "metadata": {}
  }
}
```

### Purchase Option Card

```json
{
  "card_type": "CHATBOT_CARD_TYPE_PURCHASE_OPTION",
  "title": "Example Store",
  "subtitle": "Example Bourbon",
  "display_reason": "500원 비싸지만 바로 앞에 가까운 선택지예요.",
  "purchase_option": {
    "option_type": "VENUE_OPTION_TYPE_NEAREST_REASONABLE",
    "result_id": "venue_result_456",
    "beverage_id": "bev_123",
    "beverage_name": "Example Bourbon",
    "place_id": "place_456",
    "place_name": "Example Store",
    "place_type": "store",
    "address": "서울시 예시로 2",
    "price_krw": 8500,
    "distance_m": 120.0,
    "availability_status": "VENUE_AVAILABILITY_STATUS_LIKELY_AVAILABLE",
    "freshness_status": "VENUE_FRESHNESS_STATUS_FRESH",
    "score": 0.74,
    "reason_codes": ["NEARBY_VENUE", "WITHIN_BUDGET"],
    "explanation": "500원 비싸지만 바로 앞에 가까운 선택지예요.",
    "metadata": {}
  }
}
```

## Internal Source Metadata

```json
{
  "used_sources": {
    "profile_revision": 4,
    "recommendation_request_id": "rec_req_123",
    "beverage_recommendation_request_id": "bev_req_123",
    "venue_recommendation_request_id": "venue_req_123",
    "beverage_result_ids": ["bev_result_123"],
    "venue_result_ids": ["venue_result_123"],
    "place_ids": ["place_123"],
    "beverage_ids": ["bev_123"],
    "reason_codes": ["NEARBY_VENUE", "WITHIN_BUDGET"],
    "profile_status": "PROFILE_STATUS_ACTIVE",
    "metadata": {}
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
