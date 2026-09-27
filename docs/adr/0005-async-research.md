# ADR-0005: Asynchronous research workflow

Status: Accepted 2026-09-24. Implementation: Phase 5.

## Context

Research runs synchronously inside `/api/chat`: plan → two lookups → extractive brief.
A real version (more lookups, model synthesis) takes 20–90 s, longer than API Gateway or a
patient browser allows, and should survive a client disconnect.

## Options

- Step Functions: robust but another DSL; LangGraph already expresses the workflow.
- SQS queue + worker task running the same image (`python -m app.worker`); job rows in
  Postgres; frontend polls `GET /api/research/{job_id}` (SSE later).
- Celery/Redis: adds Redis, which project rules exclude.

## Decision

SQS + worker (same image, ADR-0001). Job state machine: `queued → running → done|failed`,
with bounded steps recorded as `activity` so the UI keeps its trace. Dead-letter queue
after 3 attempts; visibility timeout above the worst-case step time.

## Consequences

- Idempotent job handling keyed by `job_id`.
- Per-user concurrent job limit (default 2) and daily quota enforce cost control.
- The synchronous path remains for the attached-document case, which is fast.
