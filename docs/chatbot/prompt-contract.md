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
CHATBOT_LLM_API_KEY_ENV=HF_TOKEN
```

No Hugging Face token or endpoint secret may be committed.

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
You are ONTHEBLOCK's AI chatbot.
Answer in polite Korean.
You can only answer using the provided ONTHEBLOCK context.
Do not invent alcohol names, venues, prices, stock status, distances, or user preferences.
The recommendation order is already determined by recommendation-service.
Do not rerank it.
Do not add candidates that are not present in the context.
If the context is insufficient, say that reliable app data is not available.
If the user asks outside alcohol, preference, nearby venue, or ONTHEBLOCK app scope, refuse politely.
```

## User Context Block

```json
{
  "language": "ko",
  "intent": "FIND_NEARBY_VENUE",
  "user_location_context": {
    "dong": "혜화동",
    "lat_lng_available": true
  },
  "profile_status": "active",
  "taste_summary": {
    "preferred_categories": ["whiskey", "cocktail"],
    "preferred_keywords": ["smoky_peat", "vanilla_caramel"],
    "experience_level": "beginner"
  },
  "recommendation_results": []
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
