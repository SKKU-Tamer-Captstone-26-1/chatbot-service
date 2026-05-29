# 012 Optional On-Device LLM

## Goal

Reduce latency/cost for supported Android devices while keeping backend truth,
storage, and fallback.

## Decision

On-device LLM is not MVP. Add it only after server production is stable.

## Allowed On-Device Responsibilities

- Lightweight intent hints.
- Short Korean wording from already-downloaded grounded facts.
- Offline cached explanations where source facts are already present and fresh.

## Server-Side Responsibilities Remain

- Auth.
- Recommendation ranking.
- Place, price, inventory, freshness, and distance facts.
- Conversation storage and feedback.
- Training data export.
- Abuse control and rate limiting.
- Fallback LLM response.

## Acceptance Gate

- Unsupported devices automatically use server LLM.
- On-device output uses the same grounding rules.
- Model package size, battery, latency, and thermal behavior are acceptable.
- Server can disable on-device path through remote config.

## Current Status

Future optimization only.
