# 007 Frontend Chatbot Integration

## Goal

Connect the Flutter app to the staged `ai-chatbot-service` through the existing
`ChatbotService` gRPC contract.

## Prerequisite

Complete `006-gcp-staging.md` first so the app has a stable non-production
backend endpoint for real integration testing.

## Integration Rules

- The Flutter app calls only `ai-chatbot-service` for chatbot behavior.
- The frontend must not call PostgreSQL, Redis, recommendation-service, or the
  LLM endpoint directly.
- User identity must travel through the existing authenticated metadata or
  gateway path, not through trusted request-body user fields.
- `proto/chatbot/v1/chatbot.proto` remains the source of truth. Do not change
  the proto unless Flutter integration proves a real contract gap.
- Recommendation facts, ranking, source IDs, and profile status come from the
  backend response. The frontend renders them but does not invent or reorder
  recommendation facts.

## Deliverables

- Dart gRPC client is generated from `ChatbotService`.
- Chatbot data layer maps:
  - `AskChatbot`
  - `GetConversation`
  - `RecordChatbotFeedback`
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
- Local app can call local `ai-chatbot-service`.
- Staging app can call the GCP staging chatbot endpoint.
- Auth metadata reaches the backend and request bodies do not contain trusted
  user identity.
- Chat history reload works through `GetConversation`.
- Feedback writes work through `RecordChatbotFeedback`.
- Frontend has no direct network path to chatbot storage, Redis,
  recommendation-service, or the LLM endpoint.

## Current Status

Not started. Requires Flutter client repository work after staging endpoint and
auth metadata path are available.

## Next Step

Continue with `008-server-llm-deployment.md`.
