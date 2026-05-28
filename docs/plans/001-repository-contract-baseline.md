# 001 Repository And Contract Baseline

## Goal

Make the chatbot-service repository safe for iterative implementation by locking
the service boundaries, agent harness, and public gRPC contract.

## Deliverables

- Root agent guide and harness docs exist.
- Chatbot gRPC proto is the public service contract.
- Service boundary docs separate chatbot, recommendation, auth, survey,
  map/place, and human chat responsibilities.
- Local verification commands are documented.

## Acceptance Gate

- `AGENT.md` and `.agent/HARNESS.md` are present.
- `proto/chatbot/v1/chatbot.proto` defines `AskChatbot`,
  `GetConversation`, and `RecordChatbotFeedback`.
- Proto comments state that recommendation-service owns ranking and facts.
- `protoc -I proto --descriptor_set_out=/private/tmp/chatbot.desc proto/chatbot/v1/chatbot.proto`
  succeeds.

## Current Status

Implemented.

## Next Step

Continue with `002-local-chatbot-runtime.md`.
