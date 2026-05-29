# 009 Evaluation And Release Gates

## Goal

Prevent regressions in grounding, ranking, refusal, tone, latency, and cost
before production release.

## Deliverables

- App-specific evaluation fixtures:
  - grounded recommendation cases
  - no-answer cases
  - out-of-scope cases
  - ranking integrity cases
  - Korean tone cases
  - load/cache cases
- Offline evaluator can call the configured LLM endpoint.
- Staging validation outputs latency and failure summaries.
- Release gate is documented and repeatable.

## Acceptance Gate

- No invented facts in evaluation.
- No candidate reordering.
- No unrelated general-knowledge answers.
- Korean tone is concise and polite.
- 500-user load validation passes.
- Required dashboards or metric snapshots show acceptable latency and error
  rates.

## Current Status

Policy exists. Evaluation fixtures and offline evaluator still need
implementation.

## Next Step

Continue with `010-training-data-pipeline.md`.
