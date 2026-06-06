# Chatbot Evaluation Policy

## Purpose

This document defines how chatbot behavior is evaluated before implementation and before production release.

## MVP Evaluation Sets

Create these sets:

1. `golden_cases.yaml`
   - normal in-domain questions
   - expected intents
   - expected card types

2. `no_answer_cases.yaml`
   - missing profile
   - missing location
   - no venue candidates
   - stale/low-confidence facts

3. `out_of_scope_cases.yaml`
   - unrelated general questions
   - questions about non-app knowledge
   - requests to invent data

4. `ranking_integrity_cases.yaml`
   - LLM answer must preserve recommendation-service order
   - LLM answer must not add place, drink, price, flavor, or scent candidates

5. `korean_tone_cases.yaml`
   - concise polite Korean
   - modal-chatbot-friendly length
   - no unnecessary technical internals shown to the user

6. `load_and_cache_cases.yaml`
   - repeated identical profile/filter asks reuse approved cached facts
   - venue cache uses location buckets and freshness limits
   - 500 concurrent users do not cause full conversation-history reads
   - cache failures fall back to safe upstream calls or no-answer behavior

7. `price_inventory_uncertainty_cases.yaml`
   - verified KRW price observations are not described as live store prices
   - unknown or stale inventory/price facts disclose uncertainty
   - answers do not claim guaranteed stock, sale status, or current offers

## Model Evaluation Direction

Open LLM leaderboards can help choose candidate base models, but production
selection must be based on ONTHEBLOCK-specific evals. Broad coding, math,
reasoning, and long-context scores are secondary because this chatbot only
generates short grounded Korean responses from recommendation facts.

Compare candidate Hugging Face checkpoints with:

- grounding violation rate
- ranking preservation
- no-answer correctness
- Korean tone quality
- average output length
- latency
- endpoint cost

## Warm-Up / Overconfidence Mitigation

The project may later use continued pretraining or fine-tuning on app-specific
chatbot data. For MVP service implementation, do not train inside
`ai-chatbot-service`; train externally, upload the model to Hugging Face, and
connect through the configured endpoint.

Until training consent and retention policy is finalized, implement practical
equivalents:

- negative examples
- no-answer examples
- out-of-scope examples
- retrieval confidence thresholds
- response verifier
- refusal templates

Future model training may use stored chatbot conversations only after privacy,
consent, retention, deletion, and data filtering policies are finalized.

## Required Checks

| Check | Requirement |
|---|---|
| Grounding | Every recommendation answer must have retrieved facts |
| Ranking | LLM must not reorder recommendation-service results |
| Korean tone | Response must be polite Korean |
| Unknown handling | Missing data returns insufficient-data response |
| Price/inventory uncertainty | Price and inventory facts are framed as observations or uncertain when required |
| Cards | Recommendation answers include card-ready structured data |
| Logging | Conversation and used_sources are stored when configured |
| Scaling | Cache does not alter ranking and hot path avoids full history reads |

Local fixture validation:

```bash
chatbot-validate fixtures
```

Runtime smoke/load validation also applies response policy checks for grounding,
refusal shape, recommendation rank order, Korean tone, and uncertainty wording.
