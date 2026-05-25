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

Run cold/warm load validation:

```bash
chatbot-validate load
```

Equivalent script form:

```bash
python3 scripts/validate_staging.py smoke
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
CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT
CHATBOT_VALIDATION_SERVICE_METRICS_PATH
CHATBOT_VALIDATION_SELECTED_BEVERAGE_ID
CHATBOT_VALIDATION_LAT
CHATBOT_VALIDATION_LNG
```

When `CHATBOT_CACHE_BACKEND=redis`, validation runs a Redis preflight ping before
smoke or load checks. Set `CHATBOT_VALIDATION_REQUIRE_REDIS_PREFLIGHT=false` only
when validating a local process intentionally using process-local cache.

To include service-side counters/timers in validation output, start the chatbot
service with `CHATBOT_METRICS_SNAPSHOT_PATH` and point
`CHATBOT_VALIDATION_SERVICE_METRICS_PATH` at the same JSON file.
