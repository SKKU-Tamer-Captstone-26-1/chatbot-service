# Domain Boundaries — ONTHEBLOCK AI Chatbot

## Purpose

This file defines the cross-service ownership boundaries the chatbot must obey.

The chatbot is an orchestration and explanation layer. It is not the owner of
identity, survey truth, recommendation ranking, or canonical map/place data.

---

## Ownership Table

| Domain | Owner | Chatbot May Do | Chatbot Must Not Do |
|---|---|---|---|
| Identity/JWT | `auth-service` | Use authenticated context and caller profile when approved | Issue JWTs, accept client-supplied user_id |
| Raw survey | `survey-service` | Use recommendation profile status/results | Read survey DB, edit answers, own raw answers |
| Derived taste profile | `recommendation-service` | Request profile status and recommendation results | Own profile truth, regenerate profiles directly unless through API |
| Recommendation ranking | `recommendation-service` | Explain returned score/reason codes | Let the LLM rank, rerank, or invent candidates |
| Canonical place/menu/inventory/price | `map-service` / `place-service` | Use approved read-model snapshots or recommendation venue results | Read canonical map DB directly |
| Human chat | `chat-service` | Be displayed as a separate modal UI | Mix chatbot logs with human room messages by default |
| Chatbot conversation logs | `ai-chatbot-service` | Store chatbot messages, traces, feedback | Treat logs as raw survey truth |

---

## Identity Rules

- User identity must come from Authorization metadata or gateway-authenticated
  context.
- Public requests must not include trusted `user_id` fields.
- Internal traces may store resolved user identity for audit.

---

## Recommendation Rules

The chatbot may call recommendation APIs such as:

```text
GetProfileStatus
GetBeverageRecommendations
GetVenueRecommendations
RecordRecommendationEvent
```

The chatbot must treat these outputs as authoritative for ranking and reason
codes.

The chatbot must not call Qdrant directly unless explicitly approved as part of
a chatbot-owned retrieval experiment. Even then, Qdrant output must not become
final ranking.

---

## Map/Place Rules

For nearby place questions, the chatbot should use recommendation-service venue
recommendations or approved map read models.

Facts may include:

- Place name.
- Place type.
- Distance.
- Estimated travel time.
- Price.
- Availability status.
- Inventory confidence.
- Price confidence.
- Snapshot revision.

If location is missing:

- Use auth-provided coarse neighborhood only for coarse explanations.
- Require/request detailed lat/lng for precise nearby recommendations.

---

## Storage Rules

Chatbot-owned storage may include:

```text
chatbot_conversations
chatbot_messages
chatbot_retrieval_traces
chatbot_feedback_events
```

Chatbot storage must preserve traceability without becoming the canonical owner
of survey, recommendation, or map data.

---

## LLM Rules

The LLM may:

- Classify intent when guarded.
- Generate Korean natural-language responses.
- Summarize retrieved facts.
- Produce refusal/no-answer text.

The LLM must not:

- Create recommendation candidates.
- Invent source facts.
- Override deterministic scores.
- Claim unknown inventory, price, or place data as confirmed.
