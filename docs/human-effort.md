# 사람이 해야 하는 작업: RAG + 규칙 기반 추천 챗봇

이 문서는 현재 ONTHEBLOCK 챗봇을 어떤 순서로 완성해야 하는지 정리한다.
현재 결정은 **ML 추천 모델을 지금 학습하지 않고, RAG + Rule-based 추천
시스템으로 MVP를 만든다**는 것이다.

## 왜 이 방향인가

지금은 실제 사용자 로그와 정답 라벨이 충분하지 않다. 이 상태에서 ML 기반
추천 모델을 학습하면 추천 품질을 증명하기 어렵고, 왜 그런 추천이 나왔는지도
설명하기 어렵다.

그래서 현재 방향은 다음과 같다.

```text
recommendation-service
  = 설문, 장소, 메뉴, 가격, 분위기, 거리 정보를 이용한 rule-based/heuristic ranking

ai-chatbot-service
  = recommendation-service 결과를 RAG context로 묶고 한국어 설명을 생성

LLM
  = 추천을 만드는 모델이 아니라 grounded Korean response writer
```

교수님 평가에서는 이렇게 설명하면 된다.

```text
데이터가 부족한 초기 서비스 단계에서는 ML 추천 모델을 무리하게 학습하지 않고,
도메인 규칙 기반 추천 엔진으로 설명 가능한 추천을 만든다. 챗봇은 추천 엔진의
ranked result와 reason code를 RAG context로 사용해 근거 있는 한국어 답변을
생성한다. 이후 사용자 로그와 피드백이 쌓이면 ML ranking 또는 fine-tuning으로
확장한다.
```

## 현재 시스템 구조

```text
Flutter / Gateway
  -> ai-chatbot-service
      -> authenticated metadata에서 user context 확인
      -> recommendation-service GetProfileStatus 호출
      -> profile ACTIVE이면 GetBeverageRecommendations 호출
      -> recommendation-service 결과 순서 그대로 grounded context 생성
      -> OpenAI-compatible LLM endpoint 호출
      -> verifier / deterministic fallback
      -> Korean answer + cards 반환
```

중요한 경계:

- chatbot-service는 추천 점수 계산, 정렬, 필터링을 하지 않는다.
- recommendation DB, survey DB, auth DB, map DB를 직접 읽지 않는다.
- client가 보낸 `user_id`를 신뢰하지 않는다.
- recommendation-service 결과에 없는 술, 가격, 장소, 재고, 거리, 분위기를
  만들어내지 않는다.
- 가격 관측값은 live store price가 아니라 참고용 catalog observation으로 말한다.

## 사람이 지금 해야 하는 작업

### 1. Recommendation rule 정의 확인

recommendation-service 쪽에서 다음 정보가 명확해야 한다.

```text
설문 취향 profile
술 category
flavor tag
drink preference
scent preference
price observation
venue/bar/pub atmosphere
menu metadata
location/distance
reason_codes
score
rank
```

사람이 해야 할 일:

- reason code 이름과 의미를 문서화한다.
- 가격, 분위기, 향, 맛, 메뉴, 위치가 어떤 rule로 score에 반영되는지 정리한다.
- 추천 결과가 항상 rank 순서로 반환되는지 확인한다.
- 챗봇에 노출 가능한 field와 내부용 field를 나눈다.

### 2. Grounded chatbot 검증

챗봇은 recommendation-service 결과를 그대로 설명해야 한다.

검증 질문 예시:

```text
내 취향에 맞는 술 추천해줘
달달한 술 추천해줘
가격까지 고려하면 뭐가 좋아?
분위기 좋은 바에서 마실 만한 술 알려줘
왜 이 술이 나한테 맞아?
```

확인해야 하는 것:

- 추천 카드 순서가 recommendation-service rank와 같다.
- 없는 술이나 장소를 답하지 않는다.
- 가격이 있을 때 필수 경고 문구가 나온다.
- profile missing이면 설문 완료/처리 대기 안내를 한다.
- recommendation-service가 비어 있으면 후보 부족 fallback을 말한다.
- unrelated question은 ONTHEBLOCK 범위로 돌려보낸다.

### 3. GCP staging 연결

현재 staging recommendation-service target:

```text
RECOMMENDATION_SERVICE_GRPC_ADDR=recommendation-service-44649239380.asia-northeast3.run.app:443
RECOMMENDATION_SERVICE_GRPC_TLS=true
RECOMMENDATION_SERVICE_SERVERLESS_AUTH_MODE=google_id_token
RECOMMENDATION_SERVICE_SERVERLESS_AUDIENCE=https://recommendation-service-44649239380.asia-northeast3.run.app
```

사람이 해야 할 일:

- chatbot runtime service account에 recommendation-service `run.invoker` 권한을 준다.
- gateway가 `authorization: Bearer <user_access_token>`을 chatbot-service로 전달하게 한다.
- chatbot-service가 recommendation-service로 같은 user token을 forward하는지 확인한다.
- private Cloud Run이면 chatbot-service가 `x-serverless-authorization`을 서버에서 붙인다.

### 4. LLM endpoint 결정

지금은 fine-tuning하지 않는다. 작은 base instruction model을 writer로 쓴다.

추천 설정:

```text
CHATBOT_LLM_ENDPOINT_URL=https://<llm-endpoint>/v1/chat/completions
CHATBOT_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
CHATBOT_LLM_AUTH_MODE=none
```

protected endpoint라면:

```text
CHATBOT_LLM_AUTH_MODE=bearer_env
CHATBOT_LLM_API_KEY_ENV=HF_TOKEN
```

사람이 해야 할 일:

- LLM endpoint URL을 정한다.
- auth mode를 정한다.
- staging secret version을 채운다.
- 한국어 답변 품질과 latency를 확인한다.

### 5. 평가 데이터 만들기

ML 학습 데이터가 아니라 **평가 데이터**를 먼저 만든다.

필요한 eval set:

```text
golden recommendation cases
missing profile cases
empty recommendation cases
out-of-scope cases
ranking integrity cases
price/inventory uncertainty cases
Korean tone cases
load/cache cases
```

사람이 해야 할 일:

- 정상 추천 20-50개를 만든다.
- no-answer/fallback case를 20개 이상 만든다.
- LLM이 지어내면 안 되는 case를 만든다.
- 추천 순서가 바뀌면 실패하도록 확인한다.
- 교수님 데모용 성공/실패 방어 예시를 준비한다.

## GCP 20만원 크레딧 사용 방식

GCP 크레딧은 학습보다 staging과 검증에 쓴다.

우선순위:

```text
1. Cloud Run chatbot-service staging
2. Cloud SQL chatbot storage
3. Redis/Memorystore cache
4. 짧은 LLM serving 검증
5. smoke/load validation
```

피해야 할 것:

```text
GCP에서 장시간 GPU fine-tuning
항상 켜져 있는 GPU endpoint
큰 모델 14B/32B 실험
데이터 없는 ML ranking 학습
```

Colab Pro는 당장은 필수가 아니다. 나중에 충분한 로그와 라벨이 생기면
fine-tuning smoke test에 쓴다.

## 나중에 ML로 넘어가는 조건

다음 조건이 만족되면 ML ranking 또는 fine-tuning을 다시 검토한다.

```text
충분한 사용자 질문/답변 로그
추천 클릭/선택/피드백
명확한 success label
PII filtering
consent / retention / deletion policy
train/eval split
baseline rule-based 성능 지표
```

그 전까지는 rule-based 추천이 더 안전하다.

## 지금 결론

지금 해야 할 일은 “모델 학습”이 아니라 다음이다.

```text
1. recommendation-service rule/reason code 품질 올리기
2. chatbot-service가 결과를 RAG context로 안전하게 설명하게 하기
3. staging end-to-end 검증하기
4. 평가 케이스 만들기
5. 로그와 피드백을 저장해서 나중에 ML로 확장할 준비하기
```
