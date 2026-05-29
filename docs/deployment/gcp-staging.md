# GCP Staging Runbook

This runbook starts implementation of `docs/plans/006-gcp-staging.md`.
It defines a repeatable non-production path for Cloud Run, Cloud SQL
PostgreSQL, Memorystore Redis, Secret Manager, and staging validation.

Do not paste real secrets into tracked files. Secret values belong in Secret
Manager or an operator-local shell only.

## Required Inputs

- GCP project ID and region.
- Artifact Registry Docker repository.
- Cloud Run service account.
- Cloud SQL PostgreSQL instance and database for chatbot-owned storage.
- Memorystore Redis endpoint reachable from Cloud Run.
- Recommendation-service gRPC target.
- OpenAI-compatible LLM endpoint, model name, and auth mode.
- Staging validation user ID and authorization token.

## Container

Build the service image from the repository root when doing a manual staging
deploy:

```bash
gcloud builds submit \
  --tag "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/ai-chatbot-service:$GIT_SHA"
```

The container listens on the Cloud Run `PORT` environment variable by default.
For local Docker runs, override runtime dependencies through environment
variables and keep secrets outside git.

## Build And Deploy Pipeline

Use `deploy/gcp/cloudbuild.staging.yaml` for the repeatable staging path. It
builds the image, pushes it, deploys and runs the migration job, then deploys
the Cloud Run service.

Before submitting, check the tracked deployment artifacts:

```bash
chatbot-gcp-staging-check
```

```bash
gcloud builds submit \
  --config deploy/gcp/cloudbuild.staging.yaml \
  --substitutions "_REGION=$REGION,_REPOSITORY=$REPOSITORY,_SERVICE_ACCOUNT=$CHATBOT_STAGING_SERVICE_ACCOUNT,_CLOUD_SQL_CONNECTION_NAME=$CLOUD_SQL_CONNECTION_NAME,_SERVERLESS_VPC_CONNECTOR=$SERVERLESS_VPC_CONNECTOR,_DB_DSN_SECRET_VERSION=$DB_DSN_SECRET_VERSION,_REDIS_URL_SECRET_VERSION=$REDIS_URL_SECRET_VERSION,_HF_TOKEN_SECRET_VERSION=$HF_TOKEN_SECRET_VERSION"
```

Override every `REPLACE_WITH_*` substitution before submitting. The pipeline
uses pinned secret versions and runs `chatbot-migrate` before deploying the
serving revision.

## Secrets

Create these Secret Manager entries in staging:

```text
chatbot-staging-db-dsn:<pinned-version>
chatbot-staging-redis-url:<pinned-version>
chatbot-staging-hf-token:<pinned-version>
chatbot-staging-validation-authorization:<pinned-version>
```

Use `HF_TOKEN` only when `CHATBOT_LLM_AUTH_MODE=bearer_env`. For a private
endpoint that does not need bearer auth, set `CHATBOT_LLM_AUTH_MODE=none` and
omit the `HF_TOKEN` secret from the service.

For Cloud SQL through the Cloud Run connector, store a PostgreSQL DSN that uses
the Cloud SQL Unix socket host, for example:

```text
postgres://USER:PASSWORD@/DB_NAME?host=/cloudsql/PROJECT:REGION:INSTANCE
```

## Deploy Cloud Run

Deploy the staged service with non-secret env vars from
`deploy/gcp/staging.env.yaml` and secret env vars from Secret Manager:

```bash
gcloud run deploy ai-chatbot-service-staging \
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/ai-chatbot-service:$GIT_SHA" \
  --region "$REGION" \
  --service-account "$CHATBOT_STAGING_SERVICE_ACCOUNT" \
  --env-vars-file deploy/gcp/staging.env.yaml \
  --set-secrets "CHATBOT_DB_DSN=chatbot-staging-db-dsn:$DB_DSN_SECRET_VERSION,CHATBOT_CACHE_REDIS_URL=chatbot-staging-redis-url:$REDIS_URL_SECRET_VERSION,HF_TOKEN=chatbot-staging-hf-token:$HF_TOKEN_SECRET_VERSION" \
  --set-cloudsql-instances "$CLOUD_SQL_CONNECTION_NAME" \
  --vpc-connector "$SERVERLESS_VPC_CONNECTOR" \
  --vpc-egress private-ranges-only \
  --port 8080 \
  --use-http2 \
  --startup-probe grpc.port=8080,grpc.service=ontheblock.chatbot.v1.ChatbotService,initialDelaySeconds=5,failureThreshold=6,timeoutSeconds=3,periodSeconds=10 \
  --no-allow-unauthenticated
```

Use ingress and IAM settings that match the app gateway. Do not expose staging
publicly unless the auth and gateway path are intentionally configured.
With `--no-allow-unauthenticated`, direct validation should target the staging
gateway or another approved caller that can satisfy Cloud Run IAM and forward
trusted chatbot metadata.

## Run Migrations

Run chatbot-owned PostgreSQL migrations before enabling traffic:

```bash
gcloud run jobs create ai-chatbot-service-migrate-staging \
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/ai-chatbot-service:$GIT_SHA" \
  --region "$REGION" \
  --service-account "$CHATBOT_STAGING_SERVICE_ACCOUNT" \
  --set-secrets "CHATBOT_DB_DSN=chatbot-staging-db-dsn:$DB_DSN_SECRET_VERSION" \
  --set-cloudsql-instances "$CLOUD_SQL_CONNECTION_NAME" \
  --command chatbot-migrate

gcloud run jobs execute ai-chatbot-service-migrate-staging \
  --region "$REGION" \
  --wait
```

If the job already exists, update it with the new image, pinned secret versions,
and Cloud SQL connection before executing it. Migrations are idempotent and
checksum-checked.

## Validate Staging

Run preflight first from an operator machine that can reach the staging gateway
or approved gRPC endpoint. Use `deploy/gcp/staging.validation.env.example` as
the operator-local template and do not commit filled values. A filled
`deploy/gcp/staging.validation.env` file is ignored by git:

```bash
export CHATBOT_VALIDATION_TARGET="$CHATBOT_STAGING_GATEWAY_HOST:443"
export CHATBOT_VALIDATION_SECURE=true
export CHATBOT_VALIDATION_USER_ID="validation-user"
export CHATBOT_VALIDATION_AUTHORIZATION="Bearer REPLACE_WITH_STAGING_TOKEN"
export RECOMMENDATION_SERVICE_URL="REPLACE_WITH_RECOMMENDATION_GRPC_TARGET"
export CHATBOT_CACHE_BACKEND=redis
export CHATBOT_CACHE_REDIS_URL="redis://REPLACE_WITH_REDIS_HOST:6379/0"
export CHATBOT_STORE_CONVERSATIONS=true
export CHATBOT_DB_DSN="postgres://REPLACE_WITH_STAGING_DSN"
export CHATBOT_LLM_PROVIDER=huggingface_tgi
export CHATBOT_LLM_ENDPOINT_URL="REPLACE_WITH_OPENAI_COMPATIBLE_CHAT_COMPLETIONS_URL"
export CHATBOT_LLM_MODEL="REPLACE_WITH_STAGING_MODEL"
export CHATBOT_LLM_AUTH_MODE=bearer_env
export CHATBOT_LLM_API_KEY_ENV=HF_TOKEN
export HF_TOKEN="REPLACE_WITH_OPERATOR_LOCAL_TOKEN"

chatbot-validate preflight
chatbot-validate smoke
chatbot-validate load
```

Store validation output with the staging release record. Do not commit the
operator-local env file or tokens.

## Acceptance Gate

- Cloud Run revision reaches serving state.
- gRPC startup probe passes for `ontheblock.chatbot.v1.ChatbotService`.
- `chatbot-migrate` succeeds against staging Cloud SQL.
- `chatbot-validate preflight` passes with runtime checks enabled.
- `chatbot-validate smoke` proves health, `AskChatbot`, `GetConversation`, and
  `RecordChatbotFeedback`.
- `chatbot-validate load` passes the configured 500-user/load threshold.
- No secrets or service-account keys are added to git.

## References

- [Cloud Run gRPC](https://docs.cloud.google.com/run/docs/triggering/grpc)
  requires the server to listen on the `PORT` environment variable and
  recommends HTTP/2 for gRPC metadata and streaming.
- [`gcloud run deploy`](https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy)
  supports `--env-vars-file`, `--set-secrets`, Cloud SQL attachments, VPC
  connectors, HTTP/2, and gRPC startup probes.
- [Cloud Run Secret Manager integration](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
  is the required path for service secrets.
