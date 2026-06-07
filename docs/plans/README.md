# Zero-To-Hero Plan Index

This directory breaks the ONTHEBLOCK AI chatbot production path into numbered,
implementation-ready steps. Follow the files in order unless a later step is
explicitly marked as optional.

Target architecture is GCP server-first. Android clients call backend services;
recommendation-service owns rule-based/heuristic ranking and facts;
ai-chatbot-service owns orchestration, storage, grounding, and response
formatting. On-device LLM is a later optimization after server production is
stable.

## Sequence

| Step | Plan | Outcome |
|---|---|---|
| 001 | `001-repository-contract-baseline.md` | Safe repo, service boundaries, and proto baseline |
| 002 | `002-local-chatbot-runtime.md` | Deterministic local chatbot runtime |
| 003 | `003-recommendation-grounding.md` | Recommendation-service facts drive all answers |
| 004 | `004-storage-feedback-learning-readiness.md` | Chatbot-owned storage and feedback |
| 005 | `005-cache-load-readiness.md` | Redis cache, async persistence, and 500-user validation |
| 006 | `006-gcp-staging.md` | Non-production GCP staging environment |
| 007 | `007-frontend-chatbot-integration.md` | Flutter app integration with staged chatbot service |
| 008 | `008-server-llm-deployment.md` | Base writer model behind server inference endpoint |
| 009 | `009-evaluation-release-gates.md` | Grounding, ranking, tone, and load release gates |
| 010 | `010-training-data-pipeline.md` | Approved evaluation and future training data loop |
| 011 | `011-production-launch.md` | Production rollout, monitoring, and rollback |
| 012 | `012-on-device-llm.md` | Optional Android on-device LLM optimization |
| 013 | `013-rag-rule-based-direction.md` | RAG + rule-based recommendation MVP direction |
| 014 | `014-production-chatbot-routing-diversity.md` | Production routing, venue intent, and alternative recommendation diversity |
| 015 | `015-production-harden-routing.md` | Production routing hardening (venue follow-up, context-driven request filters) |
| 016 | `016-production-storage-hardening.md` | Async persistence hardening for queue-full and write reliability |

## Non-Negotiable Rules

- Do not deploy production without explicit human approval.
- Do not commit secrets, service-account files, DB passwords, or real user
  tokens.
- Do not accept trusted user identity from chatbot request bodies.
- Do not read survey-service, map-service, or place-service databases directly.
- Do not use the LLM to rank, rerank, or create recommendation candidates.
- Do not invent place, price, flavor, drink, scent, inventory, availability, or
  distance facts.
- Do not use stored chatbot logs for training until consent, retention,
  deletion, and PII filtering policy is finalized.

Reference docs:

- `docs/chatbot/chatbot-architecture.md`
- `docs/chatbot/model-strategy.md`
- `docs/chatbot/storage-and-learning.md`
- `docs/chatbot/scaling-and-cache-plan.md`
- `docs/human-effort.md`
