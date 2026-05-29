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

- Cloud Run-ready `Dockerfile`.
- Non-secret staging environment template at `deploy/gcp/staging.env.yaml`.
- Cloud Build staging pipeline at `deploy/gcp/cloudbuild.staging.yaml`.
- Operator-local Cloud Build substitutions template at
  `deploy/gcp/staging.substitutions.env.example`.
- Operator-local Secret Manager values template at
  `deploy/gcp/staging.secrets.env.example`.
- Operator-local validation env template at
  `deploy/gcp/staging.validation.env.example`.
- Terraform staging scaffold at `infra/gcp/staging`.
- Optional Terraform IAM for a Cloud Build deployer service account.
- Local staging artifact preflight command: `chatbot-gcp-staging-check`.
- Local Cloud Build deploy helper: `chatbot-gcp-staging-deploy`.
- Local Secret Manager version loader: `chatbot-gcp-staging-secrets`.
- GCP staging runbook at `docs/deployment/gcp-staging.md`.
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

In progress. Container, non-secret env template, Cloud Build staging pipeline,
Cloud Build substitutions example, Secret Manager values example, validation env
example, Terraform staging scaffold, staging artifact preflight, secret version
loader, Cloud Build deploy helper, and runbook are in the repo. Actual GCP
resources, staging URLs, and test credentials still require human provisioning
before acceptance validation can run.

## Next Step

Continue with `007-frontend-chatbot-integration.md`.
