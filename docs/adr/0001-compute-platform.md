# ADR-0001: API compute platform

Status: Accepted 2026-09-24. Implementation: Phase 4.

## Context

The API runs as one Lambda function (Python 3.13, 512 MB, 28 s) behind HTTP API via
Mangum. Requirements ahead: real Bedrock calls (5–20 s), multi-step research (two or more
lookups plus synthesis), streaming responses, a database connection pool, and background
work. Lambda's 30 s API Gateway limit, per-invocation connection churn and lack of
response streaming through HTTP API make each of these awkward. Cost at current traffic is
negligible on either platform.

## Options

1. Stay on Lambda; split long work into Step Functions. Cheapest at idle, but every
   feature becomes orchestration plumbing and streaming stays unsolved.
2. ECS Fargate service behind an ALB, same container image as `services/api/Dockerfile`,
   plus one worker service reading SQS. Always-on cost (~1 small task per env), simple
   mental model, streaming and pooled DB connections work natively.
3. App Runner. Simpler than ECS but less control over networking (RDS in private subnet)
   and no sidecar worker.

## Decision

ECS Fargate (option 2) for the API and the research worker, one image, two task
definitions. Lambda remains acceptable for the current demo stage; migration happens
when the database (ADR-0002) lands, since both need a VPC.

## Consequences

- Fixed monthly baseline cost per environment; needs user approval before provisioning.
- Health checks: ALB → `/health`; `/ready` gates deployments.
- Per-process rate limiting becomes per-task; WAF rate rules on the ALB provide the edge limit.
- Mangum handler stays until cutover so the SAM path keeps working.
