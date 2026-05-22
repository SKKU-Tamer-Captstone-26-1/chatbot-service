# Scripts

This directory is reserved for local development and deployment helper scripts.

Do not commit real secrets or service-account JSON keys.

## gRPC Generation

Install development dependencies first:

```bash
python -m pip install -e ".[dev]"
```

Generate Python modules from the chatbot proto:

```bash
python -m grpc_tools.protoc -I proto --python_out=src/chatbot_service/generated --grpc_python_out=src/chatbot_service/generated proto/chatbot/v1/chatbot.proto
```

The generated modules are expected at:

```text
src/chatbot_service/generated/chatbot/v1/chatbot_pb2.py
src/chatbot_service/generated/chatbot/v1/chatbot_pb2_grpc.py
```
