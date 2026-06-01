# Scripts

This directory is reserved for local development and deployment helper scripts.

Do not commit real secrets or service-account JSON keys.

## gRPC Generation

Install development dependencies first:

```bash
python3 -m pip install -e ".[dev]"
```

Generate Python modules from the chatbot proto:

```bash
sh scripts/generate_proto.sh
```

If the recommendation proto is available outside this repository, point the
script to it without copying or editing the recommendation contract here:

```bash
RECOMMENDATION_PROTO_PATH=/path/to/recommendation.proto sh scripts/generate_proto.sh
```

The generated modules are expected at:

```text
src/chatbot_service/generated/chatbot/v1/chatbot_pb2.py
src/chatbot_service/generated/chatbot/v1/chatbot_pb2_grpc.py
src/chatbot_service/generated/chatbot/v1/recommendation_pb2.py
src/chatbot_service/generated/chatbot/v1/recommendation_pb2_grpc.py
```

## PostgreSQL Migrations

List chatbot storage migrations without connecting to PostgreSQL:

```bash
chatbot-migrate --list
```

Apply migrations using `CHATBOT_DB_DSN`:

```bash
chatbot-migrate
```

Apply migrations with an explicit DSN:

```bash
python3 scripts/run_migrations.py --dsn "$CHATBOT_DB_DSN"
```

The migration runner records checksums in `chatbot_schema_migrations` and
rejects modified migrations that were already applied.

## Staging Validation

The validation script does not deploy anything. It talks to an already-running
chatbot gRPC service using environment variables.

Run smoke validation:

```bash
chatbot-validate smoke
```

Run preflight only:

```bash
chatbot-validate preflight
```

Run cold/warm load validation:

```bash
chatbot-validate load
```

Equivalent script form:

```bash
python3 scripts/validate_staging.py smoke
python3 scripts/validate_staging.py preflight
python3 scripts/validate_staging.py load
```

Required staging variables:

```text
CHATBOT_VALIDATION_TARGET
CHATBOT_VALIDATION_USER_ID
CHATBOT_VALIDATION_AUTHORIZATION
```

Useful load variables:

```text
CHATBOT_VALIDATION_CONCURRENCY
CHATBOT_VALIDATION_REQUESTS
CHATBOT_VALIDATION_P95_THRESHOLD_MS
CHATBOT_VALIDATION_REQUIRE_RUNTIME_PREFLIGHT
CHATBOT_VALIDATION_REQUIRE_AUTHORIZATION
CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT
CHATBOT_VALIDATION_SERVICE_METRICS_PATH
CHATBOT_VALIDATION_SELECTED_BEVERAGE_ID
CHATBOT_VALIDATION_LAT
CHATBOT_VALIDATION_LNG
```

When `CHATBOT_CACHE_BACKEND=redis`, validation runs a Redis preflight ping before
smoke or load checks. Set `CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT=false` only
when validating a local process intentionally using process-local cache.

Runtime preflight is enabled by default. It fails before traffic when required
staging settings are missing: recommendation-service gRPC address, Postgres DSN when
conversation storage is enabled, LLM provider/model/endpoint, validation
metadata, and the LLM API key when `CHATBOT_LLM_AUTH_MODE=bearer_env`. Use
`CHATBOT_LLM_AUTH_MODE=none` for local or private LLM endpoints that do not need
bearer auth.

To include service-side counters/timers in validation output, start the chatbot
service with `CHATBOT_METRICS_SNAPSHOT_PATH` and point
`CHATBOT_VALIDATION_SERVICE_METRICS_PATH` at the same JSON file.

## GCP Staging Artifact Check

Check the local staging deployment templates before submitting a Cloud Build:

```bash
chatbot-gcp-staging-check
```

Equivalent script form:

```bash
python3 scripts/check_gcp_staging.py
```

The check verifies that required GCP staging files exist, migrations run before
service deployment, secret values are excluded from the non-secret env template,
secret versions are pinned instead of `latest`, and validation env files are
ignored when filled locally.

## GCP Staging Deploy

Submit the repeatable Cloud Build staging pipeline from an ignored substitutions
file:

```bash
cp deploy/gcp/staging.substitutions.env.example deploy/gcp/staging.substitutions.env
```

Fill `deploy/gcp/staging.substitutions.env`, then dry-run:

```bash
chatbot-gcp-staging-deploy --dry-run
```

Submit:

```bash
chatbot-gcp-staging-deploy
```

Equivalent script form:

```bash
python3 scripts/deploy_gcp_staging.py --dry-run
```

The deploy helper rejects placeholders and `latest` secret versions before
calling `gcloud builds submit`.

## GCP Staging Readiness

Check live GCP staging resources and pinned Secret Manager versions from the
ignored substitutions file before submitting Cloud Build:

```bash
chatbot-gcp-staging-readiness --phase predeploy
```

After Cloud Run deploys, require the service to be Ready too:

```bash
chatbot-gcp-staging-readiness --phase postdeploy
```

Equivalent script form:

```bash
python3 scripts/check_gcp_staging_readiness.py --phase predeploy
```

## GCP Staging Secrets

Load operator-local staging secret values into Secret Manager after Terraform
has created the secret containers:

```bash
cp deploy/gcp/staging.secrets.env.example deploy/gcp/staging.secrets.env
```

Fill `deploy/gcp/staging.secrets.env`, then dry-run:

```bash
chatbot-gcp-staging-secrets --dry-run
```

Upload new versions:

```bash
chatbot-gcp-staging-secrets
```

Equivalent script form:

```bash
python3 scripts/load_gcp_staging_secrets.py --dry-run
```

The loader passes each secret to `gcloud secrets versions add --data-file=-`
through stdin, so secret values do not appear in command arguments.

## GCP Staging Validation

Run staging validation from an ignored operator-local env file:

```bash
cp deploy/gcp/staging.validation.env.example deploy/gcp/staging.validation.env
```

Fill `deploy/gcp/staging.validation.env`, then dry-run:

```bash
chatbot-gcp-staging-validate preflight --dry-run
```

Run and store validation JSON:

```bash
chatbot-gcp-staging-validate preflight \
  --output-file deploy/gcp/validation-output/preflight.json
chatbot-gcp-staging-validate smoke \
  --output-file deploy/gcp/validation-output/smoke.json
chatbot-gcp-staging-validate load \
  --output-file deploy/gcp/validation-output/load.json
```

Equivalent script form:

```bash
python3 scripts/validate_gcp_staging.py preflight --dry-run
```

After all validation files are saved, check whether the acceptance evidence is
complete:

```bash
chatbot-gcp-staging-acceptance
```

Equivalent script form:

```bash
python3 scripts/check_gcp_staging_acceptance.py
```
