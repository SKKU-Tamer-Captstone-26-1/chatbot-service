# RAG and No-Hallucination Policy

## Purpose

This document defines how RAG is allowed to work in `ai-chatbot-service`.

## Core Rule

RAG is a grounded context builder. It is not a ranking engine.

```text
MUST: use recommendation-service ranking and reason codes
MUST NOT: ask the LLM to choose best alcohol/venue from raw candidates
```

## Allowed Context

The RAG context may include:

- user derived taste profile summary
- recommendation-service beverage results
- recommendation-service venue results
- reason codes
- score breakdowns
- profile status
- venue snapshot facts
- inventory/price facts
- distance and travel-time facts
- confidence/freshness metadata

## Forbidden Context

The RAG context must not include:

- raw survey answers from survey DB
- unapproved direct map DB reads
- secrets
- private user data unnecessary for the answer
- stale or invalid price/stock facts without marking uncertainty

## No Evidence, No Answer

If the chatbot has no retrieved evidence, it must not answer with invented knowledge.

Approved Korean refusal examples:

```text
현재 ONTHEBLOCK 데이터에서 신뢰할 수 있는 추천 근거를 찾지 못했어요.
```

```text
이 질문은 ONTHEBLOCK의 술 추천, 취향, 주변 장소 정보 범위를 벗어나서 정확히 답변하기 어려워요.
```

## Confidence Handling

| Condition | Behavior |
|---|---|
| high confidence | recommend directly |
| low inventory confidence | disclose uncertainty |
| stale price | do not state price as current |
| missing location | ask for location or use dong-level fallback |
| missing profile | return profile status, not recommendation |

## Source Traceability

Each chatbot response should internally store:

```json
{
  "used_sources": {
    "profile_revision": 4,
    "recommendation_request_id": "rec_req_123",
    "beverage_ids": ["bev_123"],
    "place_ids": ["place_123"],
    "menu_item_ids": ["menu_123"],
    "inventory_revision": "optional",
    "price_revision": "optional"
  }
}
```

Do not expose raw internal IDs to the user unless needed for debugging.
