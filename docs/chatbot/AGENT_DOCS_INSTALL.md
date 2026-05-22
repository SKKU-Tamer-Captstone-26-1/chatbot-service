# Agent Docs Install Guide

## Purpose

This guide explains how to install the agent harness into the `ai-chatbot-service` repository root.

## Install

Copy these files into the repository root:

```text
AGENT.md
AGENTS.md
.agent/
docs/chatbot/CODEX_BOOTSTRAP_PROMPT.md
```

If the repository already has `AGENTS.md`, merge rules carefully. Do not delete existing safety rules.

## Verify

After copying, run:

```bash
find . -maxdepth 3 -type f | sort | grep -E 'AGENT|\.agent|docs/chatbot'
```

Expected key files:

```text
./AGENT.md
./AGENTS.md
./.agent/HARNESS.md
./.agent/DOMAIN_BOUNDARIES.md
./.agent/EXEC_PLAN_TEMPLATE.md
./.agent/CODEX_TASK_TEMPLATE.md
./.agent/ACCEPTANCE_CHECKLIST.md
./docs/chatbot/CODEX_BOOTSTRAP_PROMPT.md
```

## First Agent Task

Open `docs/chatbot/CODEX_BOOTSTRAP_PROMPT.md` and send that prompt to the agent.
