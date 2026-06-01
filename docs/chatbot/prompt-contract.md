# Chatbot Prompt Contract

## Purpose

This document defines how the chatbot constructs prompts for an open LLM provider.

## Provider Direction

MVP uses an open instruction model deployed on Hugging Face without training or
fine-tuning. See `model-strategy.md` for the model-selection and evaluation
plan.
The first adapter targets Hugging Face Text Generation Inference or Inference
Endpoints that expose an OpenAI-compatible `/v1/chat/completions` route.

Configuration:

```text
CHATBOT_LLM_PROVIDER=huggingface_tgi
CHATBOT_LLM_ENDPOINT_URL=https://<endpoint>/v1/chat/completions
CHATBOT_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
CHATBOT_LLM_AUTH_MODE=none
```

No Hugging Face token or endpoint secret may be committed.
For protected endpoints, set `CHATBOT_LLM_AUTH_MODE=bearer_env` and
`CHATBOT_LLM_API_KEY_ENV=HF_TOKEN`.

## System Behavior

The model must act as ONTHEBLOCK's Korean alcohol recommendation chatbot.

It is a response-generation model only. It does not choose places, prices,
flavors, drinks, scents, or ranking. Those facts come from
recommendation-service and approved service APIs.

It must:

- answer in polite Korean
- answer only from provided context
- refuse out-of-scope questions
- disclose uncertainty
- not invent facts
- not rank candidates beyond the order provided by recommendation-service
- keep output short enough for a modal chatbot UI

## System Prompt Template

```text
You are the ONTHEBLOCK recommendation assistant.
Answer in Korean.
Use only the provided recommendation context.
Do not invent beverages, stores, prices, inventory, ratings, distances, or reasons.
If the context does not contain enough information, say that the service does not have enough data yet.
Do not answer questions unrelated to ONTHEBLOCK beverage recommendation, survey, or supported service features.
Keep the answer concise and user-friendly.
Never expose internal scores unless the context explicitly marks them as user-visible.
```

## User Context Block

```json
{
  "user_profile_status": "ACTIVE",
  "recommendations": [
    {
      "recommendation_id": "bev_result_1",
      "beverage_id": "bev_1",
      "name": "테스트 위스키",
      "category": "whiskey",
      "description": "",
      "flavor_tags": ["smoky"],
      "reason": "취향 프로필과 잘 맞아요.",
      "reason_codes": ["MATCHES_PROFILE"],
      "price_range": "",
      "store": null
    }
  ]
}
```

## Output Requirements

The model must return JSON-compatible text content for the final answer field only if the pipeline expects structured response to be assembled by code. Prefer keeping cards and metadata code-generated.

## Token And Temperature Direction

Recommended MVP temperature:

```text
0.2
```

Recommended initial max output:

```text
256-512 tokens
```

The chatbot should be stable and conservative. This project does not need a
large-token model for MVP because the LLM receives compact recommendation facts
and only produces short Korean response text.

## Code-Owned Output Structure

The LLM returns only natural-language answer text. Cards, `used_sources`,
missing facts, refusal metadata, and recommendation IDs are assembled by code
from recommendation-service outputs.
