# 챗봇 배포를 위해 사람이 해야 하는 일

이 문서는 `ai-chatbot-service`를 GCP staging에 실제로 배포하기 전에
사람이 결정하거나 직접 입력해야 하는 작업을 정리한다. 비밀번호, 토큰,
서비스 계정 키, 실제 사용자 토큰은 이 문서나 git에 넣지 않는다.

## 현재 완료된 상태

GCP 프로젝트 `on-the-block-2026`, 리전 `asia-northeast3` 기준으로
staging 인프라는 생성되어 있다.

- Artifact Registry: `ontheblock-chatbot`
- Cloud Run 런타임 서비스 계정:
  `ai-chatbot-staging@on-the-block-2026.iam.gserviceaccount.com`
- VPC / Private Service Access / Serverless VPC connector:
  `chatbot-staging`
- Cloud SQL PostgreSQL:
  `on-the-block-2026:asia-northeast3:chatbot-staging-postgres`
- 챗봇 DB: `chatbot_service`
- Redis: `redis://10.27.0.3:6379/0`
- Secret Manager 컨테이너:
  - `chatbot-staging-db-dsn`
  - `chatbot-staging-redis-url`
  - `chatbot-staging-hf-token`
  - `chatbot-staging-validation-authorization`

아직 완료되지 않은 것은 Cloud Run의 `ai-chatbot-service-staging` 배포,
Secret Manager 버전 업로드, Cloud SQL 앱 유저 생성, LLM endpoint 연결,
gateway/frontend 연결, staging 검증이다.

## 사람이 먼저 결정해야 하는 것

1. LLM을 어디에서 서빙할지 결정한다.

   현재 서비스는 OpenAI-compatible `/v1/chat/completions` endpoint를 기대한다.
   Hugging Face Inference Endpoint, TGI, vLLM, Vertex AI, Cloud Run GPU 중
   하나를 고르면 된다. MVP에서는 추천 엔진이 이미 ranking을 끝낸 상태라
   큰 모델보다 한국어 응답 품질, 짧은 latency, 비용이 더 중요하다.

2. 사용할 모델 이름을 확정한다.

   필요한 값은 다음 두 개다.

   ```text
   CHATBOT_LLM_ENDPOINT_URL=https://<endpoint>/v1/chat/completions
   CHATBOT_LLM_MODEL=<model-or-endpoint-model-name>
   ```

3. LLM 인증 방식을 확정한다.

   Hugging Face protected endpoint를 쓰면 현재 배포 파이프라인과 가장 잘 맞는다.

   ```text
   CHATBOT_LLM_AUTH_MODE=bearer_env
   CHATBOT_LLM_API_KEY_ENV=HF_TOKEN
   ```

   private endpoint라서 bearer token이 필요 없다면
   `CHATBOT_LLM_AUTH_MODE=none`으로 바꿀 수 있지만, 현재 Cloud Build 설정은
   `HF_TOKEN` secret version을 요구한다. 이 경우 배포 전에 파이프라인을
   조금 수정해야 한다.

4. recommendation-service의 gRPC endpoint를 확정한다.

   현재 GCP에는 `recommendation-service`가 존재한다. 챗봇에서는
   recommendation-service를 직접 호출해 ranking 결과와 reason code를 받아야 한다.
   예시는 다음 형태다.

   ```text
   RECOMMENDATION_SERVICE_URL=https://recommendation-service-vcuepibcwq-du.a.run.app:443
   ```

   이 값은 팀원이 관리하는 recommendation-service의 실제 staging gRPC endpoint와
   auth metadata 요구사항에 맞춰 확인해야 한다.

5. gateway가 챗봇을 어떻게 호출할지 결정한다.

   챗봇은 client body의 `user_id`를 신뢰하면 안 된다. gateway 또는 auth 계층이
   검증한 metadata를 전달해야 한다.

   현재 기본 metadata key는 다음과 같다.

   ```text
   authorization
   x-user-id
   ```

## 사람이 직접 준비해야 하는 비밀값

비밀값은 절대 chat, 문서, git commit에 넣지 않는다. 로컬의 ignored 파일
`deploy/gcp/staging.secrets.env`에만 넣고, 그 다음 Secret Manager로 올린다.

필요한 값은 다음과 같다.

```text
CHATBOT_DB_DSN=postgres://chatbot_app:<DB_PASSWORD>@/chatbot_service?host=/cloudsql/on-the-block-2026:asia-northeast3:chatbot-staging-postgres
CHATBOT_CACHE_REDIS_URL=redis://10.27.0.3:6379/0
HF_TOKEN=<HUGGING_FACE_OR_ENDPOINT_TOKEN>
CHATBOT_VALIDATION_AUTHORIZATION=Bearer <STAGING_VALIDATION_TOKEN>
```

`CHATBOT_DB_DSN`을 만들려면 Cloud SQL 안에 챗봇 앱 유저가 필요하다.
권장 이름은 `chatbot_app`이다. 비밀번호는 사람이 직접 안전하게 생성하고
보관한다. 터미널 히스토리에 남을 수 있으니 실제 비밀번호를 명령어에 그대로
입력하지 않는 편이 좋다. GCP Console에서 유저를 만들거나, 안전한 비밀번호
관리 도구를 통해 처리한다.

## 배포 순서

1. Cloud SQL 앱 유저를 만든다.

   - 인스턴스: `chatbot-staging-postgres`
   - DB: `chatbot_service`
   - 유저 예시: `chatbot_app`
   - 비밀번호는 Secret Manager로만 전달한다.

2. `deploy/gcp/staging.secrets.env`를 채운다.

   이 파일은 gitignore 대상이다. 실제 토큰과 비밀번호를 넣어도 commit되면 안 된다.

3. Secret Manager 버전을 업로드한다.

   ```bash
   chatbot-gcp-staging-secrets --dry-run
   chatbot-gcp-staging-secrets
   ```

4. 업로드된 secret version 번호를 확인한다.

   `latest`를 쓰지 말고 숫자 version을 사용한다. 예를 들어 `1`, `2` 같은 값이다.

   ```bash
   gcloud secrets versions list chatbot-staging-db-dsn --project on-the-block-2026
   gcloud secrets versions list chatbot-staging-redis-url --project on-the-block-2026
   gcloud secrets versions list chatbot-staging-hf-token --project on-the-block-2026
   ```

5. `deploy/gcp/staging.substitutions.env`를 채운다.

   필요한 값은 Terraform output과 secret version 번호다.

   ```text
   PROJECT_ID=on-the-block-2026
   REGION=asia-northeast3
   REPOSITORY=ontheblock-chatbot
   SERVICE_NAME=ai-chatbot-service-staging
   MIGRATION_JOB_NAME=ai-chatbot-service-migrate-staging
   CHATBOT_STAGING_SERVICE_ACCOUNT=ai-chatbot-staging@on-the-block-2026.iam.gserviceaccount.com
   CLOUD_SQL_CONNECTION_NAME=on-the-block-2026:asia-northeast3:chatbot-staging-postgres
   SERVERLESS_VPC_CONNECTOR=chatbot-staging
   DB_DSN_SECRET_VERSION=<PINNED_VERSION>
   REDIS_URL_SECRET_VERSION=<PINNED_VERSION>
   HF_TOKEN_SECRET_VERSION=<PINNED_VERSION>
   ```

6. `deploy/gcp/staging.env.yaml`의 non-secret placeholder를 실제 값으로 바꾼다.

   특히 아래 값은 배포 전에 반드시 바뀌어야 한다.

   ```text
   RECOMMENDATION_SERVICE_URL
   CHATBOT_LLM_ENDPOINT_URL
   CHATBOT_LLM_MODEL
   ```

7. 배포 artifact를 확인한다.

   ```bash
   chatbot-gcp-staging-check
   ```

8. Cloud Build deploy dry-run을 먼저 실행한다.

   ```bash
   chatbot-gcp-staging-deploy --dry-run
   ```

9. 문제가 없으면 실제 deploy를 실행한다.

   ```bash
   chatbot-gcp-staging-deploy
   ```

   이 단계에서 Cloud Build가 image를 만들고, migration job을 실행하고,
   Cloud Run 서비스 `ai-chatbot-service-staging`를 배포한다.

## 배포 후 검증

배포가 끝나면 `deploy/gcp/staging.validation.env`를 채운다. 이 파일도
gitignore 대상이다.

필수로 채워야 하는 값은 다음과 같다.

```text
CHATBOT_VALIDATION_TARGET=<gateway-or-chatbot-grpc-target>:443
CHATBOT_VALIDATION_AUTHORIZATION=Bearer <STAGING_TOKEN>
CHATBOT_VALIDATION_USER_ID=<VALIDATION_USER_ID>
CHATBOT_VALIDATION_SELECTED_BEVERAGE_ID=<STAGING_BEVERAGE_ID>
RECOMMENDATION_SERVICE_URL=<RECOMMENDATION_GRPC_TARGET>
CHATBOT_DB_DSN=<OPERATOR_LOCAL_OR_CLOUD_SQL_DSN>
CHATBOT_LLM_ENDPOINT_URL=<LLM_ENDPOINT>
CHATBOT_LLM_MODEL=<MODEL_NAME>
HF_TOKEN=<TOKEN_IF_NEEDED>
```

검증 순서는 다음과 같다.

```bash
chatbot-gcp-staging-validate preflight --dry-run
chatbot-gcp-staging-validate preflight \
  --output-file deploy/gcp/validation-output/preflight.json
chatbot-gcp-staging-validate smoke \
  --output-file deploy/gcp/validation-output/smoke.json
chatbot-gcp-staging-validate load \
  --output-file deploy/gcp/validation-output/load.json
chatbot-gcp-staging-acceptance
```

통과해야 하는 기준은 다음과 같다.

- Cloud Run revision이 Ready 상태여야 한다.
- gRPC startup probe가 통과해야 한다.
- migration job이 Cloud SQL에 성공해야 한다.
- `AskChatbot`, `GetConversation`, `RecordChatbotFeedback` smoke test가
  통과해야 한다.
- 500-user load validation에서 p95 latency와 failure 기준을 통과해야 한다.
- 추천 card의 순서와 source ID가 recommendation-service 결과와 일치해야 한다.
- LLM이 새로운 술, 장소, 가격, 거리, 재고, 취향 정보를 지어내면 안 된다.

## gateway와 frontend가 해야 하는 일

staging chatbot이 Ready가 된 뒤에 gateway/frontend 작업을 연결한다.

- gateway가 `ai-chatbot-service-staging`를 호출할 수 있는 IAM 또는 네트워크 경로를
  설정한다.
- gateway는 auth-service에서 검증한 사용자 context를 metadata로 전달한다.
- frontend는 chatbot modal에서 gateway endpoint를 호출한다.
- client가 보낸 `user_id`를 신뢰하지 않는다.
- 추천 결과 ranking은 recommendation-service 결과를 그대로 사용한다.

## 비용과 운영 주의사항

Cloud SQL과 Redis는 이미 staging에 생성되어 있으므로 비용이 발생한다.
테스트를 멈추는 기간이 길다면 staging 리소스를 계속 유지할지 결정해야 한다.

운영 전에 추가로 확인할 것은 다음과 같다.

- Cloud Logging에서 chatbot error와 latency를 확인할 수 있는지
- Cloud Monitoring alert를 만들지
- LLM endpoint 비용과 scale limit이 500-user test에 맞는지
- 사용자 입력과 모델 출력 저장에 대한 동의, 보관 기간, 삭제 정책이 있는지
- training data로 쓰기 전에 PII filtering과 opt-out 정책이 있는지

## 요약

지금 사람이 해야 하는 핵심 일은 네 가지다.

1. fine-tuned LLM endpoint와 model name을 확정한다.
2. Cloud SQL 앱 유저와 secret 값을 안전하게 만든다.
3. secret version과 non-secret env를 채운 뒤 Cloud Build deploy를 실행한다.
4. gateway/auth/frontend 연결 전에 preflight, smoke, load, acceptance 검증을 통과시킨다.
