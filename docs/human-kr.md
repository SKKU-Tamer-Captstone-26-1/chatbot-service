# 챗봇 시스템 배포를 위해 사람이 해야 하는 일

이 문서는 현재 `ai-chatbot-service` 상태를 기준으로, 사람이 직접 결정하거나
입력해야 하는 작업을 정리한다. 비밀번호, 토큰, 서비스 계정 키, 실제 사용자
토큰은 이 문서나 git에 넣지 않는다.

## 현재 구현 상태

챗봇 서비스는 이제 추천 엔진이 아니라 orchestration layer로 동작한다.
현재 MVP 방향은 **RAG + rule-based recommendation**이다. 데이터가 부족한
상태에서 ML 추천 모델을 억지로 학습하지 않고, recommendation-service의
규칙/휴리스틱 기반 ranked result와 reason code를 챗봇이 grounded context로
사용한다.

```text
사용자 질문
  -> chatbot-service intent check
  -> authenticated metadata에서 user context 확인
  -> recommendation-service GetProfileStatus 호출
  -> profile active이면 beverage/venue recommendation 호출
  -> recommendation-service 결과로 grounded context 생성
  -> OpenAI-compatible LLM endpoint를 Korean response writer로만 사용
  -> verifier / deterministic fallback
  -> answer + recommendation-service 기반 cards 반환
```

구현된 핵심 정책은 다음과 같다.

- chatbot-service는 recommendation scoring, ranking, canonical data ownership을 하지 않는다.
- recommendation-service는 현재 rule-based/heuristic ranking owner다.
- recommendation DB, survey DB, auth DB, map DB를 직접 읽지 않는다.
- client가 보낸 `user_id`는 신뢰하지 않는다.
- 사용자 identity는 trusted gRPC metadata/JWT/gateway context에서 온다.
- recommendation-service 호출 시 `authorization: Bearer <accessToken>` metadata를 전달한다.
- profile missing, empty recommendations, out-of-scope, LLM unavailable, ungrounded LLM output은 LLM 추측 없이 deterministic Korean fallback을 반환한다.
- LLM은 추천 후보, 가격, 장소, 재고, 거리, 이유를 만들면 안 된다.
- cards와 source IDs는 recommendation-service 결과에서 code가 만든다.

검증된 테스트 상태:

```text
python3 -m ruff check .
python3 -m pytest
```

마지막 확인 기준으로 전체 테스트는 `143 passed`였다.

## 현재 GCP Staging 상태

프로젝트와 리전:

```text
PROJECT_ID=on-the-block-2026
REGION=asia-northeast3
```

이미 준비된 staging 리소스:

- Artifact Registry: `ontheblock-chatbot`
- Cloud Run runtime service account:
  `ai-chatbot-staging@on-the-block-2026.iam.gserviceaccount.com`
- Serverless VPC connector: `chatbot-staging`
- Cloud SQL PostgreSQL:
  `on-the-block-2026:asia-northeast3:chatbot-staging-postgres`
- Chatbot DB: `chatbot_service`
- Redis: `redis://10.27.0.3:6379/0`
- Secret Manager containers:
  - `chatbot-staging-db-dsn`
  - `chatbot-staging-redis-url`
  - `chatbot-staging-hf-token`
  - `chatbot-staging-validation-authorization`

아직 사람이 해야 하는 것은 Cloud SQL 앱 유저 생성, secret version 업로드,
LLM endpoint 확정, Cloud Run staging deploy, gateway/frontend 연결, staging
검증이다.

## 사람이 결정해야 하는 것

### 1. LLM endpoint

서비스는 OpenAI-compatible `/v1/chat/completions` endpoint를 호출한다.
MVP에서는 fine-tuning하지 않는다. LLM은 추천을 만드는 모델이 아니라
recommendation-service 결과를 자연스러운 한국어로 바꾸는 writer다.

필요한 값:

```text
CHATBOT_LLM_ENDPOINT_URL=https://<llm-endpoint>/v1/chat/completions
CHATBOT_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
CHATBOT_LLM_AUTH_MODE=none
```

protected Hugging Face/TGI endpoint를 쓰면 다음처럼 바꾼다.

```text
CHATBOT_LLM_AUTH_MODE=bearer_env
CHATBOT_LLM_API_KEY_ENV=HF_TOKEN
HF_TOKEN=<endpoint-token>
```

현재 Cloud Build template은 `HF_TOKEN` secret wiring을 유지한다. 그래서
`CHATBOT_LLM_AUTH_MODE=none`이어도 `HF_TOKEN_SECRET_VERSION` 값은 필요하다.
runtime은 auth mode가 `none`이면 `HF_TOKEN`을 읽지 않는다.

### 2. Recommendation-service endpoint

현재 staging target은 다음 값으로 맞춘다.

```text
RECOMMENDATION_SERVICE_GRPC_ADDR=recommendation-service-44649239380.asia-northeast3.run.app:443
RECOMMENDATION_SERVICE_GRPC_TLS=true
RECOMMENDATION_SERVICE_SERVERLESS_AUTH_MODE=google_id_token
RECOMMENDATION_SERVICE_SERVERLESS_AUDIENCE=https://recommendation-service-44649239380.asia-northeast3.run.app
```

챗봇은 이 service의 API만 호출한다.

```text
ontheblock.recommendation.v1.RecommendationService.GetProfileStatus
ontheblock.recommendation.v1.RecommendationService.GetBeverageRecommendations
ontheblock.recommendation.v1.RecommendationService.GetVenueRecommendations
```

Flutter/client는 `user_id`를 보내면 안 된다. gateway/auth layer가 검증한
metadata를 챗봇에 전달해야 한다.

### 3. Auth metadata contract

현재 기본 metadata key는 다음과 같다.

```text
x-user-id
authorization
```

gateway는 `authorization` 값을 챗봇에 전달해야 하고, 챗봇은 같은 값을
recommendation-service로 forward한다. recommendation-service가 private
Cloud Run이면 챗봇 서버가 자기 service account로 Google ID token을 받아
`x-serverless-authorization: Bearer <google_id_token>`도 같이 보낸다.
Flutter/client가 이 값을 직접 보내면 안 된다. raw JWT나 secret은 로그에
남기면 안 된다.

## 사람이 직접 준비해야 하는 Secret 값

실제 값은 `deploy/gcp/staging.secrets.env`에만 넣는다. 이 파일은 gitignore
대상이다.

```text
PROJECT_ID=on-the-block-2026
CHATBOT_DB_DSN=postgres://chatbot_app:<DB_PASSWORD>@/chatbot_service?host=/cloudsql/on-the-block-2026:asia-northeast3:chatbot-staging-postgres
CHATBOT_CACHE_REDIS_URL=redis://10.27.0.3:6379/0
HF_TOKEN=<OPTIONAL_LLM_BEARER_TOKEN_OR_PLACEHOLDER_IF_AUTH_NONE>
CHATBOT_VALIDATION_AUTHORIZATION="Bearer <STAGING_VALIDATION_TOKEN>"
```

`CHATBOT_DB_DSN`을 만들려면 Cloud SQL 안에 챗봇 앱 유저가 필요하다.
권장 유저 이름은 `chatbot_app`이다. 비밀번호는 사람이 직접 안전하게 생성하고,
터미널 히스토리에 남지 않는 방식으로 관리한다.

## 배포 전 준비 순서

1. Cloud SQL 앱 유저를 만든다.

   ```text
   instance: chatbot-staging-postgres
   database: chatbot_service
   user: chatbot_app
   ```

2. `deploy/gcp/staging.secrets.env`를 채운다.

   실제 비밀번호와 토큰을 넣는다. commit하지 않는다.

3. Secret Manager version을 업로드한다.

   ```bash
   chatbot-gcp-staging-secrets --dry-run
   chatbot-gcp-staging-secrets
   ```

4. 숫자 version을 확인한다.

   `latest`를 쓰지 않는다.

   ```bash
   gcloud secrets versions list chatbot-staging-db-dsn --project on-the-block-2026
   gcloud secrets versions list chatbot-staging-redis-url --project on-the-block-2026
   gcloud secrets versions list chatbot-staging-hf-token --project on-the-block-2026
   ```

5. `deploy/gcp/staging.substitutions.env`를 채운다.

   예시:

   ```text
   PROJECT_ID=on-the-block-2026
   REGION=asia-northeast3
   REPOSITORY=ontheblock-chatbot
   SERVICE_NAME=ai-chatbot-service-staging
   MIGRATION_JOB_NAME=ai-chatbot-service-migrate-staging
   CHATBOT_STAGING_SERVICE_ACCOUNT=ai-chatbot-staging@on-the-block-2026.iam.gserviceaccount.com
   CLOUD_SQL_CONNECTION_NAME=on-the-block-2026:asia-northeast3:chatbot-staging-postgres
   SERVERLESS_VPC_CONNECTOR=chatbot-staging
   AUTH_SERVICE_URL=https://authorization-service-44649239380.asia-northeast3.run.app
   RECOMMENDATION_SERVICE_GRPC_ADDR=recommendation-service-44649239380.asia-northeast3.run.app:443
   RECOMMENDATION_SERVICE_GRPC_TLS=true
   RECOMMENDATION_SERVICE_SERVERLESS_AUTH_MODE=google_id_token
   RECOMMENDATION_SERVICE_SERVERLESS_AUDIENCE=https://recommendation-service-44649239380.asia-northeast3.run.app
   CHATBOT_LLM_ENDPOINT_URL=https://<llm-endpoint>/v1/chat/completions
   CHATBOT_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
   CHATBOT_LLM_AUTH_MODE=none
   DB_DSN_SECRET_VERSION=<PINNED_VERSION>
   REDIS_URL_SECRET_VERSION=<PINNED_VERSION>
   HF_TOKEN_SECRET_VERSION=<PINNED_VERSION>
   ```

6. 배포 readiness를 확인한다.

   ```bash
   chatbot-gcp-staging-readiness --phase predeploy
   chatbot-gcp-staging-check
   chatbot-gcp-staging-deploy --dry-run
   ```

## 실제 배포

문제가 없으면 Cloud Build deploy를 실행한다.

```bash
chatbot-gcp-staging-deploy
```

이 명령은 다음 순서로 진행된다.

```text
build image
push image
deploy migration job
run chatbot-migrate
deploy Cloud Run service
```

Cloud Run service 이름:

```text
ai-chatbot-service-staging
```

## 배포 후 검증

`deploy/gcp/staging.validation.env`를 채운다. 이 파일도 gitignore 대상이다.

필수 값:

```text
CHATBOT_VALIDATION_TARGET=<gateway-or-chatbot-grpc-target>:443
CHATBOT_VALIDATION_SECURE=true
CHATBOT_VALIDATION_USER_ID=<VALIDATION_USER_ID>
CHATBOT_VALIDATION_AUTHORIZATION="Bearer <STAGING_TOKEN>"
CHATBOT_VALIDATION_SELECTED_BEVERAGE_ID=<STAGING_BEVERAGE_ID>
CHATBOT_VALIDATION_LAT=37.5665
CHATBOT_VALIDATION_LNG=126.9780
CHATBOT_VALIDATION_RADIUS_M=1500
RECOMMENDATION_SERVICE_GRPC_ADDR=recommendation-service-44649239380.asia-northeast3.run.app:443
RECOMMENDATION_SERVICE_GRPC_TLS=true
RECOMMENDATION_SERVICE_SERVERLESS_AUTH_MODE=google_id_token
RECOMMENDATION_SERVICE_SERVERLESS_AUDIENCE=https://recommendation-service-44649239380.asia-northeast3.run.app
CHATBOT_CACHE_BACKEND=redis
CHATBOT_CACHE_REDIS_URL=redis://10.27.0.3:6379/0
CHATBOT_STORE_CONVERSATIONS=true
CHATBOT_DB_DSN=<OPERATOR_LOCAL_OR_CLOUD_SQL_DSN>
CHATBOT_LLM_PROVIDER=huggingface_tgi
CHATBOT_LLM_ENDPOINT_URL=https://<llm-endpoint>/v1/chat/completions
CHATBOT_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
CHATBOT_LLM_AUTH_MODE=none
```

검증 순서:

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

통과해야 하는 기준:

- Cloud Run revision이 Ready 상태다.
- gRPC startup probe가 통과한다.
- migration job이 Cloud SQL에 성공한다.
- `AskChatbot`, `GetConversation`, `RecordChatbotFeedback` smoke test가 통과한다.
- 500-user load validation의 p95 latency와 failure 기준을 통과한다.
- 답변 cards의 순서와 source IDs가 recommendation-service 결과와 일치한다.
- profile missing, empty recommendations, out-of-scope는 LLM 없이 fallback된다.
- LLM이 새로운 술, 장소, 가격, 거리, 재고, 취향 정보를 지어내지 않는다.

## Gateway와 Frontend 작업

staging service가 Ready가 된 뒤 gateway/frontend를 연결한다.

- gateway가 `ai-chatbot-service-staging`를 호출할 수 있는 IAM 또는 네트워크 경로를 만든다.
- gateway는 auth-service에서 검증한 `x-user-id`, `authorization` metadata를 전달한다.
- frontend는 chatbot modal에서 gateway endpoint를 호출한다.
- Flutter/client request body에 trusted `user_id`를 넣지 않는다.
- recommendation cards는 chatbot response의 cards를 그대로 렌더링한다.
- 사용자 입력 중 typing event마다 호출하지 않고, submit 시점에만 호출한다.

## 운영과 비용 주의사항

Cloud SQL과 Redis는 staging에 이미 생성되어 있으므로 비용이 발생한다.
테스트를 멈추는 기간이 길다면 리소스를 유지할지 결정해야 한다.

운영 전에 사람이 추가로 결정해야 하는 것:

- LLM endpoint의 비용, cold start, concurrency, timeout.
- Cloud Logging에서 chatbot error, recommendation call latency, LLM latency 확인.
- Cloud Monitoring alert 기준.
- 사용자 입력과 모델 출력 저장에 대한 동의, 보관 기간, 삭제 정책.
- training data로 쓰기 전 PII filtering, opt-out, deletion policy.
- 추천/음주 관련 안전 문구와 서비스 정책.

## 지금 남은 핵심 Human Job

1. OpenAI-compatible LLM endpoint를 실제로 띄우고 URL/model/auth mode를 확정한다.
2. Cloud SQL `chatbot_app` 유저와 secret version을 만든다.
3. `staging.substitutions.env`와 `staging.validation.env`를 실제 값으로 채운다.
4. `chatbot-gcp-staging-deploy`를 실행한다.
5. preflight, smoke, load, acceptance 검증을 통과시킨다.
6. gateway/auth/frontend 연결 후 end-to-end로 검증한다.
