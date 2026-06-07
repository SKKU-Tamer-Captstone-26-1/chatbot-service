# Flutter Chatbot Integration Prompt

Use this prompt in the ONTHEBLOCK Flutter client repository to implement the
chatbot v1 integration.

```text
You are Codex working in the ONTHEBLOCK Flutter client repository.

Branch:
- Work on branch `chatbot-v1`.
- If the branch does not exist locally, create it from the current main
  integration branch after checking the working tree.
- Do not overwrite unrelated local changes.

Context:
The backend chatbot-service has already been implemented as a grounded
recommendation chatbot service.

The chatbot-service is not the recommendation engine. It calls
recommendation-service first, uses the returned ranked recommendation facts as
the source of truth, and uses the LLM only to generate concise Korean
natural-language explanations.

Production/staging backend path:
Flutter -> app-gateway-service -> ai-chatbot-service

Staging gateway:
- HTTPS base URL:
  https://gateway-service-44649239380.asia-northeast3.run.app
- Flutter gRPC target:
  gateway-service-44649239380.asia-northeast3.run.app:443
- TLS:
  true

Do not configure Flutter to call these services directly in production/staging:
- ai-chatbot-service
- recommendation-service
- llm-serving-service
- PostgreSQL
- Redis
- survey DB
- map DB
- recommendation DB
- any model endpoint

Temporary local development may call ai-chatbot-service directly only behind a
local configuration flag or local flavor. Do not hardcode direct chatbot-service
Cloud Run URLs in production Flutter code.

Flutter-facing API:
Prefer app-gateway-service gRPC.

Expected gateway service:
package ontheblock.appgateway.v1;
service AppGatewayService

Expected gateway chatbot methods:
- SendChatbotMessage
- GetChatbotConversation
- RecordChatbotFeedback

If app-gateway-service uses different method names, inspect the gateway proto
and map the same product behavior without changing chatbot-service semantics.

Backend chatbot contract reference:
package ontheblock.chatbot.v1;
service ChatbotService

Reference RPCs:
- AskChatbot
- GetConversation
- RecordChatbotFeedback

Proto reference:
/Users/jeonghun/chatbot-service/proto/chatbot/v1/chatbot.proto

Use the chatbot proto as the backend response/request shape reference. If the
gateway proto wraps or renames these methods, keep the Flutter data model
compatible with the gateway contract and document any mapping differences.

Authentication:
- Flutter must attach the signed-in user's access token as lowercase gRPC
  metadata:
  authorization: Bearer <access_token>
- Flutter must not send trusted user_id, external_user_id, profile_id, or
  account_id fields in chatbot request bodies.
- Flutter must not create or send x-serverless-authorization.
- x-serverless-authorization is only for server-to-server Cloud Run IAM and must
  be handled by app-gateway-service/backend services.
- Do not log raw JWTs, access tokens, refresh tokens, service tokens, or
  secrets.

Core rules:
- Flutter must not rank, rerank, score, filter, or invent recommendations.
- Flutter must preserve backend card order exactly.
- Flutter must not invent beverage names, venue names, prices, inventory,
  distance, stock, flavor, or user preferences.
- Flutter renders backend facts and user-facing text.
- Backend refusal and insufficient-data responses must be shown clearly, not
  replaced with generic UI errors.

Implement:
1. Add or update chatbot feature structure using the existing Flutter
   architecture.
2. Add a gRPC data source for app-gateway-service.
3. Add a repository/use case layer so widgets do not depend directly on
   generated gRPC classes.
4. Add configurable endpoint/flavor settings for local and staging.
5. Generate or wire gRPC clients through the repo's established proto
   generation process.
6. Add chatbot entry points from Home and Board.
7. Implement message input, sending, loading, error, retry, and conversation
   states.
8. Render assistant Korean answer text.
9. Render structured recommendation cards.
10. Implement conversation reload.
11. Implement chatbot feedback events.

Request mapping:
- message: required user input.
- conversation_id: set after the first response when continuing a conversation.
- screen_context: HOME, BOARD, MAP, or CHAT based on where the chatbot opened.
- lat/lng/radius_m: include only when location permission exists and the app has
  reliable current location.
- budget_hint_krw/category/selected_beverage_id: include only from explicit UI
  state or selected recommendation context.
- beverage_limit and venue_limit: use small defaults such as 3 to 5.
- budget_mode: set only when UI state clearly defines it.
- client_context: non-sensitive UI context only. Do not include tokens or user
  identity.

Response handling:
- Use backend answer as the assistant message.
- Preserve backend conversation_id and message_id.
- Use status, refused, refusal_reason, profile_status, missing_facts, and
  follow_up_questions to drive UI states.
- Preserve card order exactly as returned by the backend.
- Do not add recommendation cards that were not returned by the backend.

Required UI states:
- closed state
- empty chatbot state
- text input
- sending/loading state
- assistant answer state
- structured recommendation cards
- refused response
- insufficient-data/profile-not-ready response
- backend unavailable/error response with retry
- conversation reload state
- feedback controls

Required card rendering:
- beverage recommendation
- venue recommendation
- purchase option
- comparison
- profile status

For beverage cards, render:
- rank
- name_ko, fallback name_en
- category
- explanation/display_reason
- reason_codes only when useful and not too noisy
- price metadata only if returned by the backend

For venue and purchase cards, render:
- place name
- address
- distance when returned
- estimated travel time when returned
- price only when returned
- availability/freshness status using cautious copy

Price and availability wording:
- Never present backend price observations as guaranteed live store prices.
- Use cautious Korean copy such as "확인된 관측 가격", "참고 가격", or
  "실제 매장 가격과 재고는 달라질 수 있어요."
- If the backend answer already includes a warning, render it as normal
  assistant text.

Feedback:
- Implement feedback for:
  helpful
  not helpful
  dismiss
  copy
  report
- Include message_id.
- Include idempotency_key for retryable feedback events.
- Do not block normal chat UX on non-critical feedback failures.

Testing:
Run:
- flutter analyze
- relevant Flutter unit/widget tests

Add or update tests for:
- authorization metadata injection
- no trusted user_id in request body
- successful chatbot answer with cards
- refused response
- insufficient-data/profile-not-ready response
- backend unavailable retry state
- feedback idempotency_key
- preserving backend card order
- staging endpoint configuration points to the gateway, not LLM or
  recommendation-service

Acceptance criteria:
- Branch `chatbot-v1` contains the Flutter chatbot integration.
- Home and Board can open chatbot UI.
- Sending a message calls the configured gateway gRPC backend with
  authorization metadata.
- Flutter does not directly call recommendation-service, llm-serving-service, or
  databases.
- Request bodies do not contain trusted user identity.
- Backend card order is preserved.
- Assistant answers and structured cards render from backend responses.
- Refusal and insufficient-data responses render clearly in Korean.
- Feedback events are sent with idempotency keys.
- Analyze/tests pass, or failures are documented with exact reasons.

Before finishing, report:
- Files changed
- Generated files changed
- Endpoint/config keys added
- Tests run
- Any app-gateway-service or chatbot.proto contract gaps found
```

## Staging Values

```text
GATEWAY_SERVICE_GRPC_ADDR=gateway-service-44649239380.asia-northeast3.run.app:443
GATEWAY_SERVICE_TLS=true
GATEWAY_SERVICE_BASE_URL=https://gateway-service-44649239380.asia-northeast3.run.app
```

The Flutter app should use the gateway for staging. The LLM Cloud Run URL is an
internal backend dependency and must not be configured as a Flutter endpoint.
