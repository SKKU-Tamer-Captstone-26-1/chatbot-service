# 010 Training Data Pipeline

## Goal

Convert approved chatbot logs into high-quality evaluation and future model
improvement data without violating privacy or service boundaries.

Current direction is not immediate fine-tuning. The service should first collect
traceable examples for evaluation, rule improvement, prompt regression tests,
and feedback analysis. ML training starts only after enough approved data
exists.

## Required Policy Decisions

- User consent wording and UX.
- Retention period.
- User deletion/export process.
- PII filtering rules.
- Evaluation split rules first; train/eval split rules only for future ML work.
- Human review requirements for generated training examples.

## Recommended Pipeline

```text
chatbot PostgreSQL logs
  -> approved export job
  -> PII filtering/redaction
  -> evaluation dataset and feedback analysis
  -> rule/reason-code and prompt improvement loop
  -> optional future train/eval split after policy and data volume are ready
  -> GCS or BigQuery dataset
  -> optional offline fine-tuning job
  -> evaluation gate
  -> model registry/version
  -> staged endpoint rollout
```

## Deliverables

- Export only chatbot-owned fields needed for response generation.
- Keep recommendation source IDs and compact candidate summaries for grounding.
- Exclude secrets, auth tokens, raw survey answers, and canonical map/place DB
  rows.
- Store model version, prompt version, eval result, and rollout status.

## Acceptance Gate

- Training data cannot include unapproved private data.
- Every training example can be traced to source policy and consent state.
- New rule, prompt, verifier, or future checkpoint version passes
  `009-evaluation-release-gates.md` before serving production traffic.

## Current Status

Use for evaluation and feedback analysis only. Do not implement export for
training until policy, data volume, labels, and deletion handling are approved.

## Next Step

Continue with `011-production-launch.md`.
