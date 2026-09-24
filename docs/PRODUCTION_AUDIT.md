# Production readiness audit

Date: 2026-09-24. Scope: commit `d63429e` (end of hackathon phase) plus the baseline
hardening in `8261f88`. Evidence is the code, 89 passing backend tests, a clean frontend
typecheck/build, `npm audit` and `pip-audit` runs, and the live Amplify/API Gateway
deployment in `ap-south-1`. Nothing here is a compliance claim.

## Verdict

**Maturity: prototype with alpha-grade backend.** The system deploys, is publicly
reachable and handles hostile input carefully, but it has no user identity, no
durable data, one fixture-backed capability and, until this pass, no logging. It is not
production-ready. See `PROJECT_STATUS.md` for the running status and `docs/ROADMAP.md`
for the path.

## Architecture

| Area | Finding | Severity | Status |
| --- | --- | --- | --- |
| Compute | Lambda + Mangum behind HTTP API. 28 s ceiling; cold starts on a 512 MB Python image with LangGraph; no streaming. Real Bedrock + two-lookup research already brushes the limit. | High | ADR-0001: move API to ECS Fargate in Phase 4 |
| State | Everything is process memory: documents (10 global), history (browser sessionStorage), nothing else. No database. | High | ADR-0002: Postgres + pgvector, Phase 2 |
| Document store | S3 path exists for Lambda; TTL 1 day via lifecycle; token hash stored beside content. Fine as evidence cache, not as user data. | Medium | Keep as blob tier; ownership metadata moves to Postgres |
| Agents | Deterministic regex router → four LangGraph nodes. Only Coding calls a model. Documents = keyword scoring; Research = extractive concatenation; Search = Tavily pass-through. Honest, cheap, but "agents" overstates it. | Medium | Reframe as routed workflows; add LLM synthesis where it adds value (Phase 3, 5) |
| Async | None. Research runs inside the request. | Medium | ADR-0005: SQS + worker, Phase 5 |
| IaC | Single SAM template for API; Amplify configured by hand (manual zip deploy). Two systems, one undocumented. | Medium | Phase 6: Amplify in CloudFormation or CDK; single stack per env |
| Environments | One shared environment doubles as demo and "production". | High | Phase 6: staging + production stacks |

## Application quality

| Finding | Severity | Status |
| --- | --- | --- |
| Coding defaults to a fixed fixture; Bedrock path exists but was never exercised against a real model from Lambda (role lacked `bedrock:InvokeModel`). | High | Role fixed conditionally in `8261f88`; live verification is Phase 1 |
| No structured logging, request IDs or metrics. | High | Fixed in `8261f88` (JSON access log, X-Request-ID); metrics/alarms Phase 1 |
| Unhandled exceptions produced Starlette's default 500 with no correlation. | Medium | Fixed: JSON `internal_error` with request_id |
| Startup accepts unsafe combinations (production + fixture, http origins). | Medium | Fixed: `validate_for_environment()` |
| No liveness/readiness distinction. | Low | Fixed: `/health` vs `/ready` |
| No lint or dependency scanning in CI. | Medium | Fixed: ruff, pip-audit, npm audit, sam validate |
| Local venv is Python 3.14; deploy target 3.13. | Low | Documented in DEVELOPMENT.md; CI pins 3.13 |
| Frontend has no eslint (Next 16 removed `next lint`). | Low | Phase 8 |
| Frontend state lives in one 700-line component. | Low | Phase 8 refactor when auth lands |

## Security

| Finding | Severity | Status |
| --- | --- | --- |
| No authentication. Optional shared `X-Demo-Token` compared in constant time; live deployment runs without it. Anyone can call `/api/chat` and spend Tavily/Bedrock budget. | Critical | ADR-0003: Cognito JWT, Phase 2. Until then: token gate + edge throttle + per-client limiter |
| Document authorization = possession of a per-document token; not bound to a user. Deletion by anyone holding the token. | High | Phase 2: ownership rows in Postgres |
| Rate limiting was only API Gateway global (2 rps burst 5): one client could starve everyone. | High | Per-client limiter added (per-process); WAF rate rule in Phase 6 |
| Secrets travel as CloudFormation parameters into Lambda env vars (NoEcho but visible in console/config). | Medium | Phase 6: Secrets Manager / SSM SecureString with runtime fetch |
| No CSP or other security headers on the static site. | Medium | Phase 8: Amplify custom headers (`customHttp.yml`) |
| Prompt-injection surface currently low (document text is never sent to a model, no tools). Grows with grounded RAG and LLM research. | Medium (future) | Phase 3/5: untrusted-content framing, no tool execution, output filtering |
| SSRF: not applicable yet (no arbitrary URL fetch). Search returns Tavily URLs only. | Low (future) | Any future fetcher must block private ranges and follow no redirects |
| In-memory DocumentStore capped at 10 globally → trivial DoS on the container path. | Medium | Non-Lambda deployments must set `DOCUMENT_BUCKET` (warned at startup); per-user quotas Phase 2 |
| Upload handling: magic-byte checks, 5 MB cap, 30 pages, decompression and text bounds, filename never trusted. | Strength | Keep tests |
| CORS restricted to configured origins; markdown rendered with `skipHtml` and http(s)-only links. | Strength | Keep |
| No secrets found in repository or history; `.env` ignored; `npm audit` and `pip-audit` clean. | Strength | Enforced in CI now |

## Data and privacy

| Finding | Status |
| --- | --- |
| Uploaded document text persists ≤1 h in memory or ≤1 day in S3 (SSE-S3). No PII classification. | Document in SECURITY.md; per-user deletion API in Phase 2 |
| Chat history stays in the browser session only. No server retention today. | Retention policy defined before Phase 2 persistence |
| Logs (new) contain method, path, status, duration, agent, provider, error code, request id. No prompt or document content, no tokens. | Enforced by test `test_access_log_is_json_without_prompt_text` |
| Third parties receiving user content: Amazon Bedrock (prompt), Tavily (search query). | Must be disclosed in product privacy notice (Phase 7) |

## Cost controls

Bedrock is only reachable with `NEXUS_PROVIDER=bedrock`; Tavily only with a key. Both are
bounded (1 attempt, short timeouts, ≤5 results). No budget alarms exist. Phase 1 adds AWS
Budgets + CloudWatch alarms on invocation count and 5xx rate before any paid provider is
enabled by default.

## Stub → production replacement list

| Stub | Where | Replacement | Phase |
| --- | --- | --- | --- |
| `DEMO_ANSWER` fixture | `providers.py` | Bedrock Converse verified end-to-end; production refuses fixture (done) | 1 |
| `/login`, `/register` previews | `apps/web/app/login`, `register` | Cognito Hosted UI / Amplify Auth with PKCE; JWT to API | 2 |
| `X-Demo-Token` shared gate | `main.py` | Cognito JWT verification (JWKS cache) | 2 |
| sessionStorage history | `page.tsx` | `conversations` / `messages` tables per user | 2 |
| Per-document bearer token | `agents/document.py`, `s3_document.py` | Ownership in Postgres; token retained only for anonymous demo | 2 |
| Keyword scoring retrieval | `agents/document.py` | Chunk embeddings in pgvector + BM25 hybrid; grounded answer with citations | 3 |
| Extractive research brief | `agents/research.py` | Async job: plan → bounded lookups → LLM synthesis with citations, progress updates | 5 |
| Global 10-document cap | `DocumentStore` | Per-user quota, S3 for blobs, Postgres for metadata | 2 |
| Manual Amplify zip deploy | runbook | CI deploy on tag, staging first, rollback = previous artifact | 6 |
| CloudFormation param secrets | `template.yaml` | Secrets Manager references | 6 |

## Git workflow

Two long-lived branches existed (`main` stale at `1ff16f1`, `codex/hackathon-mvp` current).
Adopt: `main` protected and deployable; short-lived `feat/*` / `fix/*` branches; PR with CI
green; squash merge; tags `v0.x.y` trigger deploy. First step: fast-forward `main` to
`codex/hackathon-mvp`, merge `feat/production-baseline`, delete the hackathon branch.
