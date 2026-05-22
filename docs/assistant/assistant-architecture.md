# AI Assistant Architecture

## Purpose

This document defines the initial architecture for ONTHEBLOCK `ai-assistant-service`.

The assistant is a separate service. It is shown as a modal chatbot on the Home and Board screens. It answers only app-domain questions about alcohol, taste preferences, nearby venues, price/distance/availability comparison, and explanation of recommendations.

## Ownership

| Service | Owns | Assistant May Use | Assistant Must Not Do |
|---|---|---|---|
| `auth-service` | identity, JWT, user profile, coarse location such as dong | authenticated caller, profile, coarse location | issue tokens, mutate identity |
| `survey-service` | raw survey answers and survey schema | indirectly through recommendation profile status | read survey DB or treat raw survey as assistant-owned |
| `recommendation-service` | derived taste profiles, vectors, scoring metadata, recommendation logs | beverage recommendations, venue recommendations, reason codes, score breakdowns | bypass scoring or ranking |
| `map-service` / map read model | canonical place, menu, inventory, price, detailed location | venue facts through APIs, snapshots, or read models | own canonical place/inventory data |
| `ai-assistant-service` | conversation orchestration, assistant logs, prompt/RAG policy, response formatting | all grounded facts through service APIs | hallucinate alcohols, venues, prices, inventory, or distances |

## High-Level Flow

```text
Flutter modal chatbot
  -> gateway or ai-assistant-service gRPC
      -> auth-service for caller context
      -> recommendation-service for profile/recommendations
      -> map-service/read-model facts when needed
      -> RAG context builder
      -> LLM grounded response generator
      -> Korean polite answer + cards
```

## User Location Rule

`auth-service` may provide coarse location, such as dong-level location. Detailed location for nearby venue recommendations should come from Map context or a request-provided lat/lng. If detailed location is unavailable, the assistant should ask for location context or answer only with non-location recommendations.

## LLM Role

The LLM is not a ranking engine. It may only turn retrieved facts and recommendation-service outputs into a polite Korean response.

```text
Allowed:
- summarize recommendation results
- explain reason codes in Korean
- compare returned options
- ask follow-up questions when facts are missing

Forbidden:
- invent place names
- invent alcohol names
- invent prices
- invent stock status
- produce ungrounded venue distances
- override recommendation-service ranking
```

## MVP Assistant Intents

| Intent | Meaning |
|---|---|
| `RECOMMEND_BEVERAGE` | User asks for alcohol matching their taste |
| `FIND_NEARBY_VENUE` | User asks where nearby they can buy/drink matching alcohol |
| `COMPARE_PURCHASE_OPTIONS` | User asks to compare price/distance/availability options |
| `EXPLAIN_PREFERENCE` | User asks what their taste profile means |
| `EXPLAIN_RECOMMENDATION` | User asks why a recommendation was made |
| `PROFILE_STATUS` | User asks whether their profile/recommendation data is ready |
| `OUT_OF_SCOPE` | User asks outside ONTHEBLOCK domain |
| `INSUFFICIENT_DATA` | User asks in-domain but service lacks enough data |

## Korean Tone

Default response language is Korean. Tone should be polite, concise, and helpful.

Example:

```text
좋아요. 현재 확인 가능한 추천 데이터 기준으로는 아래 선택지가 가장 잘 맞아 보여요.
```

## Deployment Shape

MVP may run as one gRPC process. Conversation storage may use PostgreSQL. LLM provider is configurable and provider-neutral.
