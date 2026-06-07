# 007 Frontend Chatbot Integration

## Goal

Connect the Flutter app to the chatbot v1 backend experience through the staged
gateway path.

The production/staging direction is:

```text
Flutter -> app-gateway-service -> ai-chatbot-service
```

Known staging gateway:

```text
GATEWAY_SERVICE_GRPC_ADDR=gateway-service-44649239380.asia-northeast3.run.app:443
GATEWAY_SERVICE_TLS=true
GATEWAY_SERVICE_BASE_URL=https://gateway-service-44649239380.asia-northeast3.run.app
```

Temporary local development may call `ai-chatbot-service` directly only through
configuration. The hardcoded production path should be gateway-first.

## Prerequisite

Complete `006-gcp-staging.md` first so the app has a stable non-production
backend endpoint for real integration testing.

## Integration Rules

- The Flutter app calls the app gateway for production/staging chatbot behavior
  once gateway staging is ready.
- A direct `ai-chatbot-service` target may exist only as a local or operator
  smoke-test configuration.
- The frontend must not call PostgreSQL, Redis, recommendation-service, or the
  LLM endpoint directly.
- User identity must travel through the existing authenticated metadata or
  gateway path, not through trusted request-body user fields.
- The Flutter-facing production/staging API should come from
  `app-gateway-service`. `proto/chatbot/v1/chatbot.proto` remains the
  chatbot-service backend contract reference and may be used for temporary local
  direct integration only.
- Do not change chatbot proto unless Flutter integration proves a real contract
  gap.
- Recommendation facts, ranking, source IDs, and profile status come from the
  backend response. The frontend renders them but does not invent or reorder
  recommendation facts.
- Flutter must not send `x-serverless-authorization`; Cloud Run IAM metadata is
  a server-to-server concern for gateway/backend services.

## Deliverables

- Dart gRPC client is generated from the app gateway proto when available.
- A temporary local direct client may be generated from `ChatbotService`.
- Chatbot data layer maps the gateway chatbot methods to:
  - send chatbot message
  - get chatbot conversation
  - record chatbot feedback
- Endpoint/flavor configuration supports local and staging targets without
  committed secrets.
- The integration branch is `chatbot-v1`.
- Chat modal is available from Home and Board screens.
- Chat UI supports:
  - empty state
  - user input
  - loading state
  - assistant answer
  - refused response
  - insufficient-data response
  - backend error and retry
  - conversation reload
  - helpful, not-helpful, dismiss, copy, and report feedback events
- UI renders `ChatbotCard` results for beverage, venue, purchase option,
  comparison, and profile status.
- Local and staging chatbot endpoints are configurable without committed
  secrets or real tokens.

## Acceptance Gate

- Flutter build and tests pass after generated chatbot client integration.
- Local app can call local `ai-chatbot-service` or a local gateway according to
  configuration.
- Staging app can call the GCP staging gateway endpoint once gateway staging is
  ready.
- Auth metadata reaches the backend and request bodies do not contain trusted
  user identity.
- Chat history reload works through `GetConversation`.
- Feedback writes work through `RecordChatbotFeedback`.
- Frontend has no direct network path to chatbot storage, Redis,
  recommendation-service, or the LLM endpoint.

## Current Status

Not started in the Flutter repo. Staging gateway URL has been received.

Use `docs/chatbot/flutter-integration-prompt.md` as the implementation prompt
for the Flutter `chatbot-v1` branch.

## Next Step

Continue with `008-server-llm-deployment.md`.
