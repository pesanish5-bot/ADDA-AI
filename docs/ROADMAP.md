# Roadmap to production

Each phase ends with its completion criteria met and `PROJECT_STATUS.md` updated. Phases
needing paid AWS resources say so; provisioning waits for explicit approval.

Maturity labels used in `PROJECT_STATUS.md`:

- **prototype**: works for a demo; no auth, no durable data or no observability.
- **alpha**: authenticated, logged, tested; single environment; data may be lost.
- **beta**: staging + production, migrations, backups verified by a restore drill, alarms.
- **production candidate**: incident runbook, rollback rehearsed, load-tested at target,
  security review of auth/data paths complete, no known high findings.
- **production**: candidate criteria held for 30 days of real use with SLO met.

## Phase 0 — Baseline hardening (done 2026-09-24)

Objective: make the existing API safe to operate and observable.
Tasks: environment guards, request IDs, JSON logs, per-client limiter, safe 500s,
`/ready`, CI with lint + vulnerability scans, ADRs, docs set.
Completion: 89 tests pass; CI green; production refuses fixture. **Met.**

## Phase 1 — Real coding provider and cost guardrails

Objective: Coding answers come from Bedrock in the deployed environment.
Tasks: verify model access in `ap-south-1` with `check_bedrock.py`; deploy with
`Provider=bedrock AppEnv=staging`; AWS Budget + CloudWatch alarms (5xx rate, invocation
count, duration p95, Bedrock invocation count); dashboard; frontend shows provider badge
from response (already) and removes "demo" copy when provider is `bedrock`.
Dependencies: Bedrock model access approval (may incur cost; ask first).
Completion: live `/api/chat` returns `provider=bedrock` through the browser; alarm fires
in a test; budget exists. Tests: contract test on `ChatResponse.provider`; log assertion.

## Phase 2 — Identity and persistence (alpha)

Objective: real users, their data stored durably and isolated.
Tasks: Cognito pool (ADR-0003); PKCE login in the static frontend; JWT dependency in
FastAPI; Postgres via Aurora Serverless v2 or RDS (ADR-0002) with SQLAlchemy + Alembic;
tables `users`, `conversations`, `messages`, `documents`, `research_jobs`; document
ownership replaces bearer tokens for signed-in users; per-user quotas; account deletion
cascade; retention policy (documents 30 days default, configurable).
Dependencies: VPC, Secrets Manager (paid resources: approve first).
Completion: two users cannot see each other's conversations or documents (tests);
migrations run in CI against a Postgres service container; `alembic upgrade head` is a
deploy step. Tests: auth unit tests with a local JWKS, isolation tests, migration
round-trip.

## Phase 3 — Semantic retrieval and grounded answers

Objective: Documents answer questions the keyword scorer cannot.
Tasks: Titan embeddings; `pgvector` HNSW; hybrid ranking; grounded answer generation with
verified citations; prompt-injection framing of retrieved text; OCR for image-only PDFs
via Amazon Textract behind a flag (paid; approve first).
Completion: retrieval benchmark on sample corpus ≥ baseline on recall@3; no answer
without at least one verifiable citation. Tests: golden question set; injection fixture
that instructs the model to ignore the question must not change routing or output shape.

## Phase 4 — Compute migration (ADR-0001)

Objective: API and worker on ECS Fargate with streaming.
Tasks: ALB + WAF (rate rule, managed core rules); task definitions; `/ready` as deploy
gate; SSE streaming for Coding; remove Mangum path once traffic is cut over.
Dependencies: Phase 2 VPC. Paid.
Completion: zero-downtime deploy demonstrated; streaming visible in UI; SAM stack retired.

## Phase 5 — Asynchronous research (ADR-0005)

Objective: multi-step research with model synthesis that survives disconnects.
Tasks: SQS + DLQ; worker entrypoint; job API; progress in UI; per-user concurrency and
daily quota; source fetcher with SSRF guard (deny private ranges, no redirects, size/time
caps) if full-page reading is added.
Completion: job completes after client reload; DLQ alarm; quota enforced (tests).

## Phase 6 — Environments, secrets, delivery (beta)

Objective: staging and production as separate stacks with safe delivery.
Tasks: one IaC system (CDK or CloudFormation) covering API, DB, queue, Amplify app;
Secrets Manager for all secrets; GitHub Actions deploy on tag to staging, manual approval
to production; rollback = redeploy previous image/artifact (documented and rehearsed);
Alembic downgrade policy; backups with 7-day PITR and a restore drill recorded in
OPERATIONS.md.
Completion: staging deploy from CI; production rollback rehearsed once; restore drill done.

## Phase 7 — Security and privacy hardening

Objective: close remaining audit items before wider use.
Tasks: CSP and security headers on Amplify (`customHttp.yml`); dependency update
automation (Dependabot); secret scanning in CI; privacy notice listing Bedrock and Tavily
as processors; data export and deletion endpoints; audit log table; threat model doc.
Completion: no high findings in a second review; headers verified with an external scan.

## Phase 8 — Frontend productionization

Objective: maintainable UI with real auth state.
Tasks: eslint config; split `page.tsx` into components/hooks; error boundaries; auth
context; persistent history from API; accessibility pass; Playwright smoke tests in CI.
Completion: lint in CI; Playwright covers login → chat → upload → cite.

## Phase 9 — Performance and reliability

Objective: known capacity and graceful degradation.
Tasks: k6 load test at target (e.g. 50 concurrent users); connection pool sizing;
timeouts and circuit breaking for Bedrock/Tavily; SLOs (availability 99.5%, p95 chat
< 15 s non-streaming) with alarms; chaos check: Tavily down → Search reports, others work.
Completion: load test report in `docs/`; SLO dashboard; degradation tests pass.

## Phase 10 — Production candidate and launch

Objective: operate for real.
Tasks: incident runbook drills; on-call expectations; cost review; go/no-go against the
production-candidate label; 30-day observation window.
Completion: label promoted to production with evidence in `PROJECT_STATUS.md`.
