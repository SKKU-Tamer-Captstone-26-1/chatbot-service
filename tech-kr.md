# 챗봇 서비스 기술 선택 기록

## 사용자가 물어본 핵심 질문

사용자는 이런 문제를 물어봤다.

```text
사용자가 질문을 넣고 500명 정도가 동시에 사용하면,
매번 데이터베이스를 읽어서 답변하는 방식은 비용이 너무 크지 않은가?
이 부분을 고려했는가?
```

답은 다음과 같다.

```text
맞다. 매 요청마다 전체 대화 기록이나 비싼 외부 데이터를 읽으면
비용과 지연 시간이 빠르게 커진다. 그래서 AskChatbot의 hot path에서
전체 대화 DB를 읽지 않고, 추천 결과와 프롬프트 컨텍스트를 캐시하고,
대화 로그 저장은 비동기화하는 방향으로 구현했다.
```

## 무엇을 구현했는가

이번 구현의 목적은 `AskChatbot` 요청이 많아졌을 때 추천 서비스,
PostgreSQL, LLM 호출 비용이 과도하게 커지는 것을 줄이는 것이다.

구현한 내용은 다음과 같다.

- 추천 서비스 응답 캐시
- Redis/Memorystore용 캐시 백엔드
- 테스트와 단일 프로세스 개발용 인메모리 캐시
- 500명 동시 요청에서 같은 캐시 키로 몰릴 때 중복 upstream 호출을 막는 per-key lock
- 프로필 상태 캐시
- 주류 추천 결과 캐시
- 장소 추천 결과 캐시
- 장소 추천 캐시용 location bucket
- grounded prompt context 캐시
- `AskChatbot`, LLM, 추천 호출, 캐시 hit/miss, 저장소 write metrics
- 대화 로그와 retrieval trace 저장을 위한 bounded async persistence queue
- stale/expired 장소 정보 필터링
- 사람이 결정해야 하는 production 작업을 `docs/human-effort.md`에 기록

## 어떻게 동작하는가

현재 `AskChatbot`의 주요 흐름은 다음과 같다.

```text
AskChatbot
  -> 인증 metadata에서 user_id 확인
  -> intent 분류
  -> 추천 서비스 응답 캐시 조회
  -> 캐시 miss이면 recommendation-service 호출
  -> recommendation-service 결과로만 grounded context 생성
  -> prompt context 캐시 조회/저장
  -> LLM은 자연어 답변만 생성
  -> verifier로 최소 검증
  -> chatbot-owned storage에 대화/trace 저장
```

중요한 점은 `AskChatbot`이 기본적으로 전체 대화 기록을 읽지 않는다는
것이다. 대화 기록은 평가, 피드백, 향후 학습 데이터 후보를 위한 로그이지,
매번 답변을 만들기 위한 primary read source가 아니다.

## 기술 선택과 이유

### Python gRPC

챗봇 서비스는 독립 gRPC 서비스로 유지했다.

이유:

- 기존 서비스들이 gRPC 계약 중심으로 나뉘어 있다.
- Flutter/client, auth-service, recommendation-service와 명확한 contract를 둘 수 있다.
- request body에 `user_id`를 넣지 않고 metadata 기반 인증 흐름을 강제하기 쉽다.

### recommendation-service를 ranking owner로 유지

LLM이나 chatbot-service가 추천 순위를 다시 계산하지 않도록 했다.

이유:

- recommendation-service가 profile revision, score, reason code, ranking 의미를 소유한다.
- 챗봇이 re-rank하면 추천 시스템의 책임 경계가 깨진다.
- 캐시는 추천 결과를 빠르게 재사용하기 위한 것이지, 새로운 ranking source가 아니다.

### Redis/Memorystore 캐시

Production 캐시 백엔드는 Redis/Memorystore를 기준으로 잡았다.

이유:

- 여러 chatbot-service instance가 같은 캐시를 공유해야 한다.
- process-local memory cache는 instance가 늘어나면 hit rate가 낮아진다.
- TTL 기반 만료가 단순하고 운영 방식이 검증되어 있다.
- Google Cloud 환경에서는 Memorystore로 운영하기 적합하다.

현재 설정:

```text
CHATBOT_CACHE_BACKEND=redis
CHATBOT_CACHE_REDIS_URL=redis://...
```

로컬 개발과 테스트에서는 `memory` backend를 사용할 수 있다.

### In-memory cache

`InMemoryCache`도 구현했다.

이유:

- 단위 테스트에서 Redis 서버가 없어도 캐시 동작을 검증할 수 있다.
- 로컬 단일 프로세스 개발에서는 충분히 빠르고 단순하다.
- production Redis 구현과 같은 interface를 사용하므로 교체가 쉽다.

### Per-key lock

캐시 miss가 동시에 500개 발생하는 cold-cache stampede를 막기 위해
추천 캐시 wrapper 안에 per-key lock을 넣었다.

이유:

- 캐시가 있어도 첫 요청이 동시에 몰리면 500개 요청이 모두 recommendation-service를 때릴 수 있다.
- 같은 user/profile/filter 조합은 한 요청만 upstream을 호출하고 나머지는 채워진 캐시를 재사용해야 한다.
- 이 기능은 특히 이벤트 직후나 서버 재시작 직후에 중요하다.

### Cache key에 profile revision 포함

주류 추천 cache key는 이런 형태다.

```text
beverage_recs:{user_id}:{profile_revision}:{category}:{budget_mode}:{limit}
```

이유:

- 사용자의 취향 profile이 바뀌면 이전 추천 결과를 쓰면 안 된다.
- `profile_revision`이 바뀌면 자연스럽게 다른 cache key가 된다.
- invalidation을 복잡하게 만들지 않고도 stale recommendation 사용을 줄일 수 있다.

### 장소 추천에 location bucket 사용

장소 추천은 정확한 `lat/lng` 자체를 cache key로 쓰지 않고 bucket으로 묶는다.

```text
venue_recs:{user_id}:{profile_revision}:{selected_beverage_id}:{location_bucket}:{radius_m}:{budget_mode}:{limit}
```

이유:

- 위치가 소수점 아주 작은 차이로 달라도 사실상 같은 주변 검색일 수 있다.
- exact lat/lng를 쓰면 cache reuse가 거의 안 된다.
- bucket을 쓰면 근처 사용자의 같은 의도 요청을 재사용할 수 있다.

주의:

- bucket 크기가 너무 크면 거리/가격/장소 정확도가 떨어질 수 있다.
- 그래서 최종 precision은 human/product/map owner가 확인해야 한다.
- 이 항목은 `docs/human-effort.md`에 기록했다.

### Prompt context cache

추천 서비스 결과로 만든 grounded context를 hash해서 prompt context JSON을 캐시한다.

이유:

- 같은 추천 결과와 같은 intent라면 LLM에 넘기는 context JSON도 반복해서 만들 필요가 없다.
- LLM 답변 자체를 적극적으로 캐시하는 것보다 안전하다.
- 답변 text 캐시는 사용자 질문 표현과 tone 문제가 있어 더 보수적으로 접근해야 한다.

캐시 조건:

- evidence가 있어야 한다.
- missing facts가 없어야 한다.
- confidence가 0보다 커야 한다.
- profile status가 active여야 한다.

### Async conversation persistence

대화 로그 저장은 `AsyncConversationRepository`로 비동기화했다.

이유:

- 사용자는 답변을 기다리고 있는데 PostgreSQL log write가 latency를 늘릴 수 있다.
- conversation/message/retrieval trace는 중요하지만 답변 생성 자체의 source of truth는 아니다.
- bounded queue를 두면 무한 메모리 증가를 막을 수 있다.
- retry와 dead-letter 기록을 두면 저장 실패를 관찰할 수 있다.

단, feedback은 사용자가 직접 결과를 보는 작업이므로 pending write를 drain한 뒤 처리한다.

### MetricsRecorder

작은 in-process metrics recorder를 만들었다.

이유:

- cache hit/miss, recommendation call, LLM call, storage write latency를 먼저 관찰해야 TTL과 queue size를 조정할 수 있다.
- 지금은 외부 monitoring vendor를 정하지 않았으므로 내부 interface부터 만들었다.
- 나중에 OpenTelemetry, Cloud Monitoring, Prometheus 등으로 bridge하기 쉽다.

기록하는 대표 값:

- `chatbot.ask`
- `llm.call`
- `recommendation.call`
- `recommendation.cache_hit`
- `recommendation.cache_miss`
- `recommendation.cache_bypass`
- `storage.write`
- `storage.write_retry`
- `storage.write_dead_letter`

### stale/expired venue fact 차단

장소 추천에서 `VENUE_FRESHNESS_STATUS_STALE`,
`VENUE_FRESHNESS_STATUS_EXPIRED`, unavailable 상태는 confident answer로 쓰지 않게 했다.

이유:

- 가격, 재고, 거리, availability는 stale하면 사용자에게 잘못된 정보를 줄 수 있다.
- 모르면 답변하지 않는 것이 이 챗봇의 기본 정책이다.
- 추천 후보가 stale이면 `INSUFFICIENT_DATA`로 내려가는 편이 안전하다.

## 왜 DB를 매번 읽지 않는가

PostgreSQL에 저장하는 데이터는 다음 목적이다.

- conversation audit
- evaluation
- feedback
- future learning 후보
- retrieval trace 추적

하지만 매 질문마다 전체 conversation history를 읽으면 문제가 생긴다.

- 사용자가 많아질수록 DB read QPS가 커진다.
- 오래된 대화가 많을수록 prompt가 커진다.
- LLM 비용과 latency가 커진다.
- 중요하지 않은 이전 말까지 LLM에 들어가 hallucination 가능성이 생긴다.

그래서 기본 정책은 다음이다.

```text
AskChatbot hot path에서는 전체 대화 기록을 읽지 않는다.
multi-turn context가 필요할 때만 최근 N개 메시지나 rolling summary를 사용한다.
```

## 사람이 결정해야 하는 것

다음은 코드만으로 확정할 수 없어서 `docs/human-effort.md`에 기록했다.

- production Redis/Memorystore URL
- Redis를 production 필수로 할지 여부
- profile/beverage/venue/prompt context TTL
- venue location bucket precision
- staging recommendation-service gRPC 주소와 TLS 설정
- staging auth metadata contract와 test token
- staging PostgreSQL DSN
- staging Redis/Memorystore endpoint
- 500-user load test 실행
- async persistence의 read-after-write 허용 범위
- training에 저장 로그를 쓰기 전 consent, retention, deletion, PII filtering 정책

## 현재 검증한 것

로컬에서 검증한 내용:

- lint 통과
- pytest 통과
- proto descriptor 생성 통과
- migration list 확인
- Redis Python dependency import 확인
- 500개 동시 동일 추천 요청에서 upstream recommendation call이 1회만 발생하는 단위 테스트
- stale venue fact가 confident answer로 가지 않는 테스트
- prompt context cache hit/miss 테스트
- async persistence가 안정적인 ID를 반환하고 나중에 저장하는 테스트

## 아직 production에서 검증해야 하는 것

아직 production/staging 인프라가 필요해서 사람이 해야 하는 검증:

- 실제 Redis/Memorystore 연결
- 실제 recommendation-service QPS 감소 확인
- 실제 PostgreSQL write latency 확인
- 실제 LLM endpoint latency 확인
- 500 concurrent user load test
- Redis 장애 시 fallback 동작
- recommendation-service 지연/장애 시 동작
- Postgres 지연/장애 시 async queue/dead-letter 동작

이 항목들은 `docs/human-effort.md`에 따로 정리되어 있다.
