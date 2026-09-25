# ADDA AI project status

**ADDA AI**. Live site: https://main.dvhyzvzxczywv.amplifyapp.com/

## Current focus

Production Cognito authentication integrated with the Bedrock-hardening branch on
`codex/auth-bedrock-integration`, preserving the workspace UI. The protected AWS stack
and Amplify frontend were deployed on 2026-09-25; PR review/merge remains.

## Auth

- Email register → `/verify-email` → login
- Google via Cognito Hosted UI (optional; hidden unless the domain, IdP and explicit
  frontend flag are configured)
- Forgot password → `/forgot-password`
- Workspace gated by `AuthGate`; every deployed application API requires a validated
  Cognito JWT and checks disabled-account status
- Registered users: Cognito Users console is source of truth
- DynamoDB stores durable profiles and 90-day auth audit events; document evidence is
  scoped to both Cognito subject and document token

## UI parity

- Phase 1 (branch `feat/bedrock-coding`, on top of `feat/production-baseline`):
  provider hardened (token cap, timeout, bounded retry, truncation flag, usage metadata
  in response and logs, 18 new tests → 107); template gained `BedrockMaxTokens`,
  `AlertEmail`-gated SNS + AWS Budget + Lambda/Bedrock alarms, and a cross-region IAM
  grant. Model entitlement for `anthropic.claude-haiku-4-5` verified AUTHORIZED /
  AVAILABLE in `ap-south-1` without invoking. **Waiting on approval** for the first
  billable calls and for the alert email/budget amount; nothing paid has run.
- Integration branch combines `feat/bedrock-coding` and `feat/production-auth`; it still
  needs PR review/merge and deployment.

## Known Issues

- Coding in the live demo is the fixture (`Provider=demo`). The conditional
  `bedrock:InvokeModel` policy is deployed but inactive until `Provider=bedrock`.
- Documents in memory are capped at 10 globally on the container path (set
  `DOCUMENT_BUCKET` for anything shared).
- Rate limiter is per process; Lambda instances do not share counts.
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
  (job 13 SUCCEED on 2026-09-25). URL https://main.dvhyzvzxczywv.amplifyapp.com/
- API: CloudFormation stack `adda-ai-demo` (UPDATE_COMPLETE 2026-09-25),
  HTTP API `pqrxb30pg5`, Lambda Python 3.13, Cognito user pool, encrypted/PITR DynamoDB
  profiles and private S3 documents bucket (1-day lifecycle). Running integration branch
  with `AppEnv=staging`, `Provider=demo`, `AUTH_REQUIRED=true`, `DemoAccessToken=""`.
  Artifact bucket `adda-ai-artifacts-<account>-ap-south-1`.
  Deploy path: `python scripts/build_lambda_package.py` → `aws cloudformation package`
  → `aws cloudformation deploy` (see OPERATIONS.md). No Docker or SAM CLI needed.
- Live verification after auth deploy: `/health` reports Cognito configured/required;
  `/ready` → 200; anonymous chat → 401; live root/login/register/recovery → 200; deployed
  bundles contain the generated pool/client/API identifiers; Amplify-origin CORS is correct.
  Real email delivery and an authenticated cross-user document smoke test remain pending.
- Target architecture (ADRs 0001–0005): ECS Fargate, Postgres + pgvector, Cognito, SQS
  worker. Nothing provisioned yet; all require approval (recurring cost).

## Tests

- Backend: `python -m pytest services/api/tests -q` → 116 passed (2026-09-25).
- Lint: `ruff check .` clean. `pip-audit -r requirements.txt --strict`: no known
  vulnerabilities.
- Frontend: `npm run typecheck` and `npm run build` passed on the integration branch;
  registration, verification, recovery and guarded workspace routes are in the static build.
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

Review and merge PR #6, then run signup/verification/login/recovery with a real recipient
and the authenticated cross-user document isolation matrix. Configure production SES
before declaring production. Enable Bedrock only with an alert email
and approved budget, then run the bounded model verification matrix. The BrandMark/fluid-
orb workspace is preserved.
