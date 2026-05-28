# 009 Training Data Pipeline

## Goal

Convert approved chatbot logs into high-quality model improvement data without
violating privacy or service boundaries.

## Required Policy Decisions

- User consent wording and UX.
- Retention period.
- User deletion/export process.
- PII filtering rules.
- Train/eval split rules.
- Human review requirements for generated training examples.

## Recommended Pipeline

```text
chatbot PostgreSQL logs
  -> approved export job
  -> PII filtering/redaction
  -> evaluation/train split
  -> GCS or BigQuery dataset
  -> offline fine-tuning job
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
- New checkpoint passes `008-evaluation-release-gates.md` before serving
  production traffic.

## Current Status

Blocked on product/privacy policy. Do not implement export for training until
policy is approved.

## Next Step

Continue with `010-production-launch.md`.
