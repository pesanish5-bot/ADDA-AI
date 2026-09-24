# ADDA AI — project status

Updated 2026-09-24. Branch `feat/production-baseline` in `outputs/nexusai-mvp`
(`outputs/nexusai` is a second worktree holding `main`; do not edit both at once).

## Current Production Stage

**Prototype** (backend approaching alpha). Deploys and is public, but has no user
identity, no durable data, and Coding still returns a labelled fixture in the cloud.
Not production-ready. Definitions in `docs/ROADMAP.md`.

## Working

- Routing: deterministic `select_agent` → Coding / Documents / Search / Research.
- Documents: PDF/TXT upload with strict validation, keyword retrieval, page citations,
  per-document token, in-memory or S3 store with expiry.
- Search: Tavily adapter (bounded, URL-only citations) when a key is configured.
- Research: plan → two lookups → extractive cited brief (no model synthesis).
- Coding: fixture (`demo`) or Bedrock Converse (`bedrock`), errors fail closed.
- Platform (new): `APP_ENV` guards, `X-Request-ID`, JSON access logs, per-client rate
  limiting, safe 500s, `/ready`, security headers, docs hidden in production.
- Frontend: static Next.js export on Amplify; session history, theme-aware brand, orb,
  stop button, try-prompts, citation cards.
- CI: ruff, pytest (3.13), pip-audit, typecheck, build, npm audit, sam validate.

## In Progress

- Phase 1 (branch `feat/bedrock-coding`, on top of `feat/production-baseline`):
  provider hardened (token cap, timeout, bounded retry, truncation flag, usage metadata
  in response and logs, 18 new tests → 107); template gained `BedrockMaxTokens`,
  `AlertEmail`-gated SNS + AWS Budget + Lambda/Bedrock alarms, and a cross-region IAM
  grant. Model entitlement for `anthropic.claude-haiku-4-5` verified AUTHORIZED /
  AVAILABLE in `ap-south-1` without invoking. **Waiting on approval** for the first
  billable calls and for the alert email/budget amount; nothing paid has run.
- Branches: neither `feat/production-baseline` nor `feat/bedrock-coding` is merged to
  `main` (`origin/main` = `4e393fc`). Merge in that order; retire `codex/hackathon-mvp`.

## Known Issues

- Coding in the live demo is the fixture (`Provider=demo`). The conditional
  `bedrock:InvokeModel` policy is deployed but inactive until `Provider=bedrock`.
- Documents in memory are capped at 10 globally on the container path (set
  `DOCUMENT_BUCKET` for anything shared).
- Rate limiter is per process; Lambda instances do not share counts.
- Local venv is Python 3.14 while CI/deploy use 3.13.
- `docker compose` build/run unverified. Frontend has no eslint.
- `/login`, `/register` are UI previews only.

## Security Issues

- Critical: no authentication; the public API can spend provider budget (mitigated by
  edge throttle, per-client limiter, and paid providers being off). Fix: Phase 2 Cognito.
- High: document access is token possession, not user ownership. Fix: Phase 2.
- Medium: secrets as CloudFormation parameters → env vars. Fix: Phase 6 Secrets Manager.
- Medium: no CSP on the static site. Fix: Phase 7.
- Details and strengths: `docs/PRODUCTION_AUDIT.md`, `SECURITY.md`.

## Infrastructure

- Frontend: Amplify app `dvhyzvzxczywv`, branch `main`, `ap-south-1`, manual zip deploys
  (last job 11). URL https://main.dvhyzvzxczywv.amplifyapp.com/
- API: CloudFormation stack `adda-ai-demo` (UPDATE_COMPLETE 2026-09-24 12:50 IST),
  HTTP API `pqrxb30pg5`, Lambda Python 3.13, private S3 documents bucket (1-day
  lifecycle). Running commit `e47e634` with `AppEnv=staging`, `Provider=demo`,
  `DemoAccessToken=""` (stack parameter now matches the public-demo Lambda config; the
  earlier drift is resolved). Artifact bucket `adda-ai-artifacts-<account>-ap-south-1`.
  Deploy path: `python scripts/build_lambda_package.py` → `aws cloudformation package`
  → `aws cloudformation deploy` (see OPERATIONS.md). No Docker or SAM CLI needed.
- Live verification after deploy: `/health` → `environment: staging`, `version: 0.2.0`;
  `/ready` → 200 with `document_bucket` ok; chat returns `X-Request-ID` and CORS headers
  for the Amplify origin; 422 error carries `request_id`; sample PDF upload → cited
  extractive answer → delete all 200; JSON access log lines present in CloudWatch.
- Target architecture (ADRs 0001–0005): ECS Fargate, Postgres + pgvector, Cognito, SQS
  worker. Nothing provisioned yet; all require approval (recurring cost).

## Tests

- Backend: `python -m pytest -q` in `services/api` → 107 passed (2026-09-24, Phase 1
  provider tests added; baseline was 89).
- Lint: `ruff check .` clean. `pip-audit -r requirements.txt --strict`: no known
  vulnerabilities.
- Frontend: `npm run typecheck`, `npm run build` last passed on `d63429e` (no frontend
  changes since). `npm audit` clean.
- Not run this pass: SAM validate (CLI not installed locally; runs in CI), live cloud
  smoke against the new template.

## External Services

- Amazon Bedrock: configured via `BEDROCK_MODEL_ID`; live inference **unverified**.
- Tavily: key held in local `.env` and stack parameter; live Search verified earlier in
  the hackathon phase, not re-run today.
- AWS account: profile `nexusai`, region `ap-south-1`.

## Latest Decisions

- 2026-09-24: ADR-0001 ECS Fargate over Lambda (Phase 4); ADR-0002 Postgres + pgvector;
  ADR-0003 Cognito; ADR-0004 pgvector hybrid retrieval; ADR-0005 SQS + worker for
  research. Production refuses the demo fixture unless explicitly allowed. Git: `main`
  protected, short-lived branches, squash merge, tags deploy.

## Next Priority

Phase 1 completion, gated on approval: (1) two bounded `check_bedrock --invoke` calls
with `global.anthropic.claude-haiku-4-5-20251001-v1:0`; (2) deploy `Provider=bedrock`
with `AlertEmail` + `MonthlyBudgetUsd` so the budget and alarms exist before public
traffic reaches the model; (3) run the verification matrix through the deployed app
(normal request, code explanation, debug request, larger request, failure path, fixture
guard) and record results here. Then Phase 2 (Cognito + Postgres) on
`feat/auth-persistence`.
