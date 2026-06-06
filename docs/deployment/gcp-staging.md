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

Copy `deploy/gcp/staging.substitutions.env.example` to the ignored
`deploy/gcp/staging.substitutions.env` file, then fill it from Terraform outputs
and pinned Secret Manager version numbers. This file also carries non-secret
runtime values that must not remain as placeholders, such as
`RECOMMENDATION_SERVICE_GRPC_ADDR`,
`RECOMMENDATION_SERVICE_SERVERLESS_AUTH_MODE`,
`RECOMMENDATION_SERVICE_SERVERLESS_AUDIENCE`,
`CHATBOT_LLM_ENDPOINT_URL`, and `CHATBOT_LLM_MODEL`:

```bash
chatbot-gcp-staging-readiness --phase predeploy
chatbot-gcp-staging-deploy --dry-run
chatbot-gcp-staging-deploy
```

Override every `REPLACE_WITH_*` value before submitting. The deploy helper
rejects placeholders and `latest` secret versions. The pipeline uses pinned
secret versions, injects non-secret runtime values from substitutions, and runs
`chatbot-migrate` before deploying the serving revision.

## Base Infrastructure

Use `infra/gcp/staging` to provision non-secret base resources before the first
Cloud Build deployment:

```bash
cd infra/gcp/staging
terraform init
terraform plan
terraform apply
```

Keep `terraform.tfvars`, state files, and filled secret values outside git. The
Terraform scaffold creates Secret Manager secret containers but does not create
secret versions, so operator-supplied DB passwords, Redis URLs, LLM tokens, and
validation tokens do not enter Terraform state.

Set `cloud_build_deployer_service_account_email` in `terraform.tfvars` when
Cloud Build runs under a dedicated deployer identity. The scaffold grants that
identity the staging roles needed to push images, deploy Cloud Run, and attach
the chatbot runtime service account.

## Secrets

Create these Secret Manager entries in staging:

```text
chatbot-staging-db-dsn:<pinned-version>
chatbot-staging-redis-url:<pinned-version>
chatbot-staging-hf-token:<pinned-version>
chatbot-staging-validation-authorization:<pinned-version>
```

Use `HF_TOKEN` only when `CHATBOT_LLM_AUTH_MODE=bearer_env`. For a private
Cloud Run LLM endpoint that does not need model-level bearer auth, set
`CHATBOT_LLM_AUTH_MODE=none`,
`CHATBOT_LLM_SERVERLESS_AUTH_MODE=google_id_token`, and
`CHATBOT_LLM_SERVERLESS_AUDIENCE=https://<llm-cloud-run-host>`.
The tracked Cloud Build template keeps the `HF_TOKEN` secret wiring available
for protected endpoints, but the runtime does not read it when auth mode is
`none`.

For Cloud SQL through the Cloud Run connector, store a PostgreSQL DSN that uses
the Cloud SQL Unix socket host, for example:

```text
postgres://USER:PASSWORD@/DB_NAME?host=/cloudsql/PROJECT:REGION:INSTANCE
```

After Terraform creates the secret containers, copy
`deploy/gcp/staging.secrets.env.example` to the ignored
`deploy/gcp/staging.secrets.env` file and fill it with operator-local values.
Then load pinned Secret Manager versions:

```bash
chatbot-gcp-staging-secrets --dry-run
chatbot-gcp-staging-secrets
gcloud secrets versions list chatbot-staging-db-dsn --project "$PROJECT_ID"
gcloud secrets versions list chatbot-staging-redis-url --project "$PROJECT_ID"
gcloud secrets versions list chatbot-staging-hf-token --project "$PROJECT_ID"
```

The loader uses `gcloud secrets versions add --data-file=-` and sends each
secret through stdin, so values do not appear in command-line arguments.
Copy the enabled numeric versions into `deploy/gcp/staging.substitutions.env`.
Do not use `latest`.

## Deploy Cloud Run

Prefer `chatbot-gcp-staging-deploy`, which submits
`deploy/gcp/cloudbuild.staging.yaml`. The Cloud Build pipeline injects
non-secret runtime values from `deploy/gcp/staging.substitutions.env` and secret
env vars from Secret Manager.

For a manual deploy, use the same pinned values and avoid checked-in
placeholders:

```bash
gcloud run deploy ai-chatbot-service-staging \
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/ai-chatbot-service:$GIT_SHA" \
  --region "$REGION" \
  --service-account "$CHATBOT_STAGING_SERVICE_ACCOUNT" \
  --set-env-vars "AUTH_SERVICE_URL=$AUTH_SERVICE_URL,RECOMMENDATION_SERVICE_GRPC_ADDR=$RECOMMENDATION_SERVICE_GRPC_ADDR,RECOMMENDATION_SERVICE_GRPC_TLS=true,RECOMMENDATION_SERVICE_SERVERLESS_AUTH_MODE=$RECOMMENDATION_SERVICE_SERVERLESS_AUTH_MODE,RECOMMENDATION_SERVICE_SERVERLESS_AUDIENCE=$RECOMMENDATION_SERVICE_SERVERLESS_AUDIENCE,RECOMMENDATION_SERVICE_SERVERLESS_TOKEN_ENV=GOOGLE_ID_TOKEN,CHATBOT_LLM_PROVIDER=huggingface_tgi,CHATBOT_LLM_MODEL=$CHATBOT_LLM_MODEL,CHATBOT_LLM_ENDPOINT_URL=$CHATBOT_LLM_ENDPOINT_URL,CHATBOT_LLM_AUTH_MODE=$CHATBOT_LLM_AUTH_MODE,CHATBOT_LLM_API_KEY_ENV=HF_TOKEN,CHATBOT_LLM_SERVERLESS_AUTH_MODE=$CHATBOT_LLM_SERVERLESS_AUTH_MODE,CHATBOT_LLM_SERVERLESS_AUDIENCE=$CHATBOT_LLM_SERVERLESS_AUDIENCE,CHATBOT_LLM_SERVERLESS_TOKEN_ENV=GOOGLE_ID_TOKEN,CHATBOT_CACHE_BACKEND=redis,CHATBOT_STORE_CONVERSATIONS=true" \
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

When recommendation-service is private Cloud Run, keep the user token and
server-to-server token separate. The client/gateway forwards only
`authorization: Bearer <user_access_token>` to chatbot-service. Chatbot-service
then forwards that user authorization to recommendation-service and adds its own
`x-serverless-authorization: Bearer <google_id_token>` using the configured
Cloud Run audience. Do not accept `x-serverless-authorization` from clients as
trusted input.

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
`deploy/gcp/staging.validation.env` file is ignored by git. Validation output
under `deploy/gcp/validation-output/` is also ignored:

```bash
chatbot-gcp-staging-validate preflight --dry-run
chatbot-gcp-staging-validate preflight \
  --output-file deploy/gcp/validation-output/preflight.json
chatbot-gcp-staging-validate smoke \
  --output-file deploy/gcp/validation-output/smoke.json
chatbot-gcp-staging-validate load \
  --output-file deploy/gcp/validation-output/load.json
chatbot-gcp-staging-readiness --phase postdeploy
chatbot-gcp-staging-acceptance
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
- `chatbot-gcp-staging-readiness --phase postdeploy` passes live GCP checks.
- `chatbot-gcp-staging-acceptance` passes against saved validation output.
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
