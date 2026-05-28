# 010 Production Launch

## Goal

Release the chatbot to real Play Store users with safe fallback behavior,
observability, and rollback.

## Deliverables

- Production Cloud Run service.
- Production Cloud SQL PostgreSQL.
- Production Memorystore Redis.
- Production LLM endpoint.
- Secret Manager backed config.
- Dashboards and alerts for:
  - request rate and latency
  - recommendation-service errors
  - cache hit/miss/error rate
  - LLM timeout/error/latency
  - storage queue depth/retry/dead-letter count
  - insufficient-data/refusal rate
- Rollback plan for chatbot-service and LLM model version.

## Acceptance Gate

- Staging smoke and 500-user load pass.
- Production config passes preflight.
- No direct external service DB reads.
- No LLM ranking or invented facts.
- Auth identity comes only from trusted metadata.
- Storage, retention, and training-data policy are approved.
- Support owner knows how to disable LLM endpoint or switch to safe fallback.

## Current Status

Not started. Requires GCP production project, approved policies, staging pass,
and human production approval.

## Next Step

Continue with `011-on-device-llm.md` only after server production is stable.
