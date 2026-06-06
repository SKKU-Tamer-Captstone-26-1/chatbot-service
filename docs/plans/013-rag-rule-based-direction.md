# 013 RAG + Rule-Based Direction

## Goal

Ship the chatbot as a production-credible MVP without pretending there is
enough data for an ML recommendation model.

## Decision

Use a rule-based/heuristic recommendation engine plus RAG-grounded chatbot
explanation.

```text
survey/map/catalog facts
  -> recommendation-service rule-based scoring and reason codes
  -> ai-chatbot-service RAG context from recommendation-service results
  -> base OpenLLM or deterministic fallback as Korean response writer
  -> verifier, cards, storage, feedback
```

## Why

- Current real user data is not enough for a reliable ML ranking model.
- Rule-based scoring is explainable and easier to defend in evaluation.
- RAG keeps chatbot answers grounded in service-provided facts.
- The LLM can still improve UX by turning structured results into concise
  Korean explanations.
- Stored chatbot logs and feedback can later become evaluation and ML training
  data after consent and policy are approved.

## Service Boundaries

- `recommendation-service` owns ranking, score, reason codes, and candidate
  order.
- `ai-chatbot-service` owns intent routing, grounding, prompt construction,
  fallback behavior, verifier behavior, cards, storage, and feedback.
- The LLM must not rank, rerank, filter, or invent recommendations.
- The chatbot must not read recommendation, survey, auth, map, or place
  databases directly.
- Client-supplied `user_id` remains untrusted.

## Implementation Steps

1. Keep recommendation-service as the only recommendation source.
2. Represent every recommendation with rank, IDs, source facts, reason codes,
   explanation, and uncertainty metadata.
3. Build compact RAG context only from recommendation-service responses.
4. Use deterministic fallbacks for missing profile, empty candidates,
   unavailable recommendation-service, out-of-scope questions, and ungrounded
   LLM output.
5. Add evaluation cases for normal recommendations, no-answer, refusal,
   ranking integrity, Korean tone, and price/inventory uncertainty.
6. Store chatbot messages, retrieval traces, source IDs, and feedback for
   audit and future improvement.
7. Use logs first for evaluation and rule/prompt improvement, not training.
8. Revisit ML ranking or LLM fine-tuning only after enough approved labeled data
   exists.

## Human Work

- Confirm rule/reason-code definitions in recommendation-service.
- Confirm catalog, survey-derived profile, price observation, venue atmosphere,
  and menu metadata fields exposed by recommendation-service.
- Fill staging endpoint and secret values.
- Run staging smoke/load/evaluation checks.
- Review failed examples and improve rules, prompts, or verifier behavior.
- Decide consent, retention, deletion, and PII policy before any training data
  export.

## Acceptance Gate

- Chatbot never recommends candidates that recommendation-service did not
  return.
- Recommendation order matches recommendation-service order.
- Missing data produces deterministic Korean fallback.
- LLM output cannot claim live price, stock, distance, venue, or preference facts
  that are not in context.
- Evaluation fixtures pass for grounding, refusal, ranking integrity, Korean
  tone, and load/cache behavior.

## Next Step

Run staging end-to-end with the current recommendation-service endpoint, then
use validation failures to improve recommendation-service rules and chatbot
grounding/verifier behavior.
