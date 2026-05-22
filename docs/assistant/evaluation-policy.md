# Assistant Evaluation Policy

## Purpose

This document defines how assistant behavior is evaluated before implementation and before production release.

## MVP Evaluation Sets

Create three sets:

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

## Warm-Up / Overconfidence Mitigation

We discussed a research-inspired warm-up idea for reducing overconfidence. For MVP, do not implement model pretraining or fine-tuning.

Instead document and implement practical equivalents:

- negative examples
- no-answer examples
- out-of-scope examples
- retrieval confidence thresholds
- response verifier
- refusal templates

Future model training may use stored assistant conversations only after privacy, consent, and data filtering policies are finalized.

## Required Checks

| Check | Requirement |
|---|---|
| Grounding | Every recommendation answer must have retrieved facts |
| Ranking | LLM must not reorder recommendation-service results |
| Korean tone | Response must be polite Korean |
| Unknown handling | Missing data returns insufficient-data response |
| Cards | Recommendation answers include card-ready structured data |
| Logging | Conversation and used_sources are stored when configured |
