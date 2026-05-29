# 006 GCP Staging

## Goal

Deploy a non-production GCP environment that looks like production enough to
validate behavior and load.

## Recommended GCP Services

- Cloud Run for `ai-chatbot-service`.
- Cloud SQL PostgreSQL for chatbot-owned storage.
- Memorystore Redis for shared cache.
- Secret Manager for tokens, DSNs, and provider credentials.
- Cloud Logging and Cloud Monitoring for runtime visibility.
- Firebase Auth and App Check for app identity and abuse reduction.

## Required Staging Inputs

- `RECOMMENDATION_SERVICE_URL`
- `CHATBOT_DB_DSN`
- `CHATBOT_CACHE_BACKEND=redis`
- `CHATBOT_CACHE_REDIS_URL`
- `CHATBOT_LLM_PROVIDER`
- `CHATBOT_LLM_ENDPOINT_URL`
- `CHATBOT_LLM_MODEL`
- LLM auth settings when the endpoint requires them
- validation target, user ID metadata key, and test authorization token

## Deliverables

- Staging environment variables are configured through Secret Manager or secure
  deployment config, not committed files.
- Migrations run against staging Cloud SQL.
- Chatbot service starts on Cloud Run and can reach recommendation-service,
  Redis, PostgreSQL, and LLM endpoint.
- `chatbot-validate smoke` is part of the staging verification routine.

## Acceptance Gate

- Staging service health check is serving.
- Smoke validation passes with real auth metadata.
- `GetConversation` and feedback work for the authenticated staging user.
- No secrets are added to git.

## Current Status

Not started. Requires human-provided GCP project, staging URLs, and test
credentials.

## Next Step

Continue with `007-frontend-chatbot-integration.md`.
