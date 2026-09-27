# ADDA AI project status

**ADDA AI**. Live site: https://main.dvhyzvzxczywv.amplifyapp.com/

## Current focus

Production Cognito authentication and durable task history are integrated with the
Bedrock-hardening branch on `codex/auth-bedrock-integration`, preserving the workspace
UI. Durable per-user Bedrock usage limits are also live. The protected AWS stack and
Amplify frontend were updated on 2026-09-27; PR review/merge remains.

Stripe billing and the dedicated Settings foundation are implemented, tested and deployed
in fail-closed mode. Live billing intentionally remains disabled until real Stripe
test/live configuration and commercial policies are supplied.

A read-only admin console is deployed for `pesanish5@gmail.com`. It exposes bounded user,
plan, usage and authentication-event summaries, never passwords, tokens, prompts or
documents. Mutating account controls are deliberately not part of this first admin slice.

## Auth

- Email register → `/verify-email` → login
- Google via Cognito Hosted UI (optional; hidden unless the domain, IdP and explicit
  frontend flag are configured)
- Forgot password → `/forgot-password`
- Workspace gated by `AuthGate`; every deployed application API requires a validated
  Cognito JWT and checks disabled-account status
- Registered users: Cognito Users console is source of truth
- DynamoDB stores durable profiles, a maximum of 100 tasks per account and 90-day auth
  audit events; document evidence is scoped to both Cognito subject and document token

## UI parity

- Phase 1 (integrated on `codex/auth-bedrock-integration`):
  provider hardened (token cap, timeout, bounded retry, truncation flag, usage metadata
  in response and logs, 18 new tests → 107); template gained `BedrockMaxTokens`,
  `AlertEmail`-gated SNS + AWS Budget + Lambda/Bedrock alarms, and a cross-region IAM
  grant. Claude Haiku 4.5 reported entitled but denied actual inference. APAC Amazon Nova
  Lite passed two bounded live calls (103 input tokens each; 65/111 output tokens) and is
  deployed with a $10 monthly budget and API/Bedrock alarms.
- Integration branch combines `feat/bedrock-coding` and `feat/production-auth`; it is
  deployed and still needs PR review/merge.
- Private task history now syncs across sessions, with Archive, restore and confirmed
  permanent deletion. The activity panel shows model, token total, model time and retry
  attempts when the provider returns usage metadata. Rare UI attribution and third-party
  notices are included.
- Coding now offers Automatic, Nova Micro, Nova Lite and Nova Pro. All three model tiers
  passed two bounded live calls. The API resolves public aliases through a fixed allowlist;
  clients cannot submit arbitrary Bedrock IDs. Clicking the ADDA AI logo performs a full
  page refresh.
- Bedrock Coding usage is isolated by Cognito subject and persisted in atomic DynamoDB
  daily/monthly windows. The account menu shows requests, tokens and UTC reset times.
  Current limits are 25 requests/50,000 tokens daily and 250 requests/500,000 tokens
  monthly. Search, documents and extractive Research do not consume that allowance.
- Stripe Checkout, customer portal, invoice summaries and signed webhook-driven Pro
  entitlements are implemented. Exact Price matching and webhook replay protection prevent
  the browser from granting access. `/settings/` contains Account, Plan & Usage and
  Appearance; later categories are visibly marked planned.

## Known Issues

- Coding uses Bedrock (`apac.amazon.nova-lite-v1:0`). The SNS alarm subscription is pending
  recipient confirmation at `pesanish5@gmail.com`.
- Local-development documents in memory are capped at 10 globally; staging uses the
  configured private S3 bucket.
- Rate limiter is per process; Lambda instances do not share counts.
- Exact token totals are available only after Bedrock replies, so one bounded response can
  cross a token ceiling; the next model request is rejected. Request limits remain atomic.
- Local venv is Python 3.14 while CI/deploy use 3.13.
- `docker compose` build/run unverified. Frontend has no eslint.
- The new Three.js component from `main` is present but is not mounted by a page yet;
  integrate it with reduced-motion/lazy-loading controls or remove the unused module.

## Security Issues

- Resolved and deployed: fail-closed Cognito authentication and per-user document ownership.
- Medium: secrets as CloudFormation parameters → env vars. Fix: Phase 6 Secrets Manager.
- Medium: no CSP on the static site. Fix: Phase 7.
- Details and strengths: `docs/PRODUCTION_AUDIT.md`, `SECURITY.md`.

## Infrastructure

- Frontend: Amplify app `dvhyzvzxczywv`, branch `main`, `ap-south-1`, manual zip deploys
  (job 19 SUCCEED on 2026-09-27). The published UI includes adaptive device appearance,
  manual light/dark modes, five persistent accent choices, private history, Archive and
  the verified model selector, daily/monthly account usage, `/settings/` and `/admin/`.
  URL https://main.dvhyzvzxczywv.amplifyapp.com/
- API: CloudFormation stack `adda-ai-demo` (UPDATE_COMPLETE 2026-09-27),
  HTTP API `pqrxb30pg5`, Lambda Python 3.13, Cognito user pool, encrypted/PITR DynamoDB
  profiles/task history and private S3 documents bucket (1-day lifecycle). Running integration branch
  with `AppEnv=staging`, `Provider=bedrock`, APAC Nova Lite, `AUTH_REQUIRED=true`,
  `DemoAccessToken=""`, durable usage limits and a $10 monthly budget.
  Artifact bucket `adda-ai-artifacts-<account>-ap-south-1`.
  Deploy path: `python scripts/build_lambda_package.py` → `aws cloudformation package`
  → `aws cloudformation deploy` (see OPERATIONS.md). No Docker or SAM CLI needed.
- Live verification after Settings/billing deploy: `/health` reports Cognito
  configured/required and billing disabled; `/ready` → 200; anonymous billing → 401;
  disabled webhook → 503; `/settings/` → 200 with production API, Plan & Usage, Checkout
  and portal references in the served bundle. Anonymous history → 401;
  root/login/register/recovery routes → 200. Published bundles contain the Archive,
  history-sync, usage and attribution UI. Automated tests cover
  cross-user task and quota isolation. A temporary live DynamoDB smoke record confirmed
  atomic daily/monthly request and exact token accumulation and was then deleted. An
  authenticated live usage/history/archive click-through and cross-user document smoke
  test remain pending.
- Admin verification: the role check has automated admin/non-admin/anonymous coverage;
  the live API rejects anonymous access with 401; `entity-created-index` is active and
  indexes the existing profile; `/admin/` returns 200 and its production bundle contains
  the protected overview endpoint and privacy copy. Authenticated browser click-through
  remains pending.
- Target architecture (ADRs 0001–0005): ECS Fargate, Postgres + pgvector, Cognito, SQS
  worker. Nothing provisioned yet; all require approval (recurring cost).

## Tests

- Backend: `python -m pytest services/api/tests -q` → 144 passed (2026-09-27).
- Lint: `ruff check .` clean. `pip-audit -r requirements.txt --strict`: no known
  vulnerabilities.
- Frontend: `npm run typecheck` and `npm run build` passed on the integration branch;
  registration, verification, recovery, guarded workspace, history and Archive are in the
  static build.
- CI passed API, web and SAM lint checks. Local SAM CLI is not installed. Live cloud
  health/readiness, the three-model catalog, anonymous request rejection and public
  route/bundle checks passed.

## External Services

- Amazon Bedrock: Nova Lite live inference verified locally and deployed; an authenticated
  browser Coding request is the remaining end-to-end confirmation.
- Tavily: key held in local `.env` and stack parameter; live Search verified earlier in
  the hackathon phase, not re-run today.
- AWS account: profile `nexusai`, region `ap-south-1`.

## Latest Decisions

- 2026-09-24: ADR-0001 ECS Fargate over Lambda (Phase 4); ADR-0002 Postgres + pgvector;
  ADR-0003 Cognito; ADR-0004 pgvector hybrid retrieval; ADR-0005 SQS + worker for
  research. Production refuses the demo fixture unless explicitly allowed. Git: `main`
  protected, short-lived branches, squash merge, tags deploy.

## Next Priority

Run an authenticated browser usage/history/archive smoke test and the cross-user document
isolation matrix, confirm the AWS SNS subscription email, then review/merge PR #6.
Configure production SES before declaring production. The next product slice is graceful
automatic-model fallback, followed by audited admin account controls. Before enabling
Stripe, approve the recurring price, quota economics, taxes, terms and refund policy;
payment credentials and those commercial decisions are not configured yet.
