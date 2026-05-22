# Codex Task Template

Copy this template when asking Codex/AI agent to work in this repo.

```text
You are working in the ONTHEBLOCK ai-assistant-service repository.

Before changing files, read:
- AGENT.md
- .agent/HARNESS.md
- .agent/DOMAIN_BOUNDARIES.md
- .agent/ACCEPTANCE_CHECKLIST.md

Task:
<describe the task>

Important constraints:
- This is a Python/gRPC service.
- The assistant is separate from chat-service.
- The assistant is shown as a modal from Home/Board screens.
- User identity must come from authenticated metadata, not request body user_id.
- The assistant must answer in polite Korean.
- Recommendation-service owns ranking, score breakdowns, and reason codes.
- The LLM must only generate grounded natural-language responses.
- RAG must not be used as the recommendation ranking engine.
- No retrieved evidence means no answer.
- Do not read survey-service or map-service databases directly.
- Do not commit secrets or service account keys.
- Do not implement production deployment unless explicitly requested.

Please do this workflow:
1. Inspect the repo.
2. Summarize current state.
3. Produce an execution plan.
4. Implement only the requested scope.
5. Update docs if behavior changes.
6. Run available tests/checks or explain why not.
7. Report changed files and remaining risks.

Expected output:
- Summary
- Files changed
- Tests/checks
- Risks
- Next steps
```
