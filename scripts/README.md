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
