# ADDA AI

A multi-agent workspace with visible routing, document evidence and a bounded Research workflow.

## What works now

| Capability | Implemented behavior | Verification |
| --- | --- | --- |
| Workspace | Task history for the current page session, upload, citation cards, code highlighting/copy and completed activity | Local browser, types and production build checked |
| Coding | LangGraph route to a labeled fixed fixture, or configured Bedrock Converse | Fixture verified; real Bedrock inference pending |
| Documents | PDF/TXT upload, local keyword retrieval and page-cited excerpts | Local API tests and browser flow verified |
| Research | LangGraph plan → two evidence checks → cited extractive brief | Attached-document workflow verified locally |
| Search | Tavily adapter with bounded results, optional Tavily summary, and real source URLs | Live Search verified on the canonical local API when `TAVILY_API_KEY` is set |
| AWS | Amplify frontend + API Gateway/Lambda (`adda-ai-demo`, `ap-south-1`) | Deployed and health-checked; Coding remains demo provider; Bedrock live inference still pending |

The `/login/`, `/register/`, `/verify-email/` and `/forgot-password/` flows use Amazon
Cognito when configured. The workspace and application APIs require a signed Cognito
session in deployed environments. The infrastructure template provisions the user pool,
public web client and durable DynamoDB profiles; optional Google federation requires a
separate Google OAuth client and is off by default.

Documents and document Research work without an API key. They use real source text, **not embeddings or language-model synthesis**. Default Coding mode is `demo`: its answer is a fixed connection-test fixture, not generated code. Live provider errors never silently fall back to that fixture.

**Maturity: production-hardening in progress.** Authentication, request controls,
durable profiles and per-user document isolation are implemented and locally tested.
The currently published site still runs the earlier public demo until the integration
stack and frontend are deployed and smoke-tested. Live Bedrock inference also remains
externally unverified. [PROJECT_STATUS.md](PROJECT_STATUS.md) is the source of truth.

Documentation set:

- [PRODUCTION_AUDIT.md](docs/PRODUCTION_AUDIT.md) — findings, stub → production list, git workflow.
- [ROADMAP.md](docs/ROADMAP.md) — Phases 0–10 with completion criteria and maturity definitions.
- [ADRs](docs/adr/) — compute, database, authentication, vector store, async research.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md), [DEVELOPMENT.md](DEVELOPMENT.md), [DEPLOYMENT.md](docs/DEPLOYMENT.md), [SECURITY.md](SECURITY.md), [OPERATIONS.md](OPERATIONS.md).
- Hackathon-era notes: [docs/STATUS.md](docs/STATUS.md), [DEMO_GUIDE.md](DEMO_GUIDE.md), [PITCH.md](PITCH.md).

## Run locally

Use Node.js 22+ and Python 3.13+. From this repository root on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/api/requirements-dev.txt
if (!(Test-Path services/api/.env)) { Copy-Item services/api/.env.example services/api/.env }
if (!(Test-Path apps/web/.env.local)) { Copy-Item apps/web/.env.example apps/web/.env.local }
Push-Location apps/web
npm.cmd ci
Pop-Location
```

Start the API in one terminal:

```powershell
.\.venv\Scripts\python.exe scripts\start_api.py
```

Start the frontend in another:

```powershell
cd apps/web
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

Open [ADDA AI](http://127.0.0.1:3000). Follow [DEMO_GUIDE.md](DEMO_GUIDE.md). API schema: [local OpenAPI](http://127.0.0.1:8000/docs).

On macOS/Linux use `.venv/bin/python`, `cp` and `npm` equivalents. `docker compose up --build` is a prepared alternative, but its build/run has not been verified and it does not inherit host AWS credentials automatically.

## Configuration and limits

Backend `.env` controls `APP_ENV`, model/search/document settings and Cognito identifiers;
see `services/api/.env.example`. Staging and production refuse guest mode, missing Cognito
or durable profile configuration, insecure origins, and unsafe provider configuration.
Every response carries `X-Request-ID`, and `GET /ready` reports dependency checks. The
frontend needs the API URL plus the public Cognito pool/client identifiers. Never put
AWS/provider secrets in public frontend variables.

Uploads accept PDF or UTF-8 TXT up to 5 MB, with PDFs capped at 30 pages. Extracted text and PDF decompression are additionally bounded. Documents live in one API process for up to one hour, at most ten documents, and disappear on restart. Each document requires its separate secret token for retrieval and deletion. There is no durable storage or multi-instance document support. Browser task history is memory-only; prompts are independent, not a conversation-memory system.

The Lambda template stores documents in a private S3 bucket with one-day expiry so separate instances share them. No vector database, embeddings, OCR or generated-code execution is implemented; see the roadmap.

## Live services

Follow [AWS setup](docs/AWS_SETUP.md). AWS CLI is installed on the originating workstation and the named profile `nexusai` has passed STS identity verification; the default profile is not signed in. This does not prove Bedrock inference. The configured model still needs a real invocation check. Set `AWS_PROFILE=nexusai` in the backend terminal when using that profile, then select `NEXUS_PROVIDER=bedrock` only after verification.

`TAVILY_API_KEY` enables Search and web Research. Put it only in `services/api/.env`, then restart the API. Do not put it in `apps/web/.env.local`. On the canonical pair (`127.0.0.1:3000` → `127.0.0.1:8000`) Search is live when `/health` reports `capabilities.search: true`. Search asks Tavily for at most five basic results plus a provider summary, and lists only HTTP(S) URLs Tavily returned. It does not independently read or verify full source pages. Health reports configuration/capabilities, while each chat response labels its actual provider (`demo`, `bedrock`, `extractive` or `tavily`). Health alone never proves Bedrock access.

## Verify and hand off

```powershell
Push-Location services/api
..\..\.venv\Scripts\python.exe -m ruff check .
..\..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
Push-Location apps/web
npm.cmd run typecheck
npm.cmd run build
Pop-Location
```

Backend tests exercise graph routing, document parsing/isolation/limits, Research and provider errors; external calls are mocked. The latest verified scope is in [docs/STATUS.md](docs/STATUS.md).

- `apps/web/`: Next.js static frontend.
- `services/api/app/`: FastAPI, LangGraph, specialist modules and sample PDF.
- `services/api/tests/`: backend tests.
- `infra/template.yaml`, `amplify.yml`: prepared AWS deployment configuration.
- [Architecture](docs/ARCHITECTURE.md), [four-person task plan](docs/TASK_PLAN.md), [deployment runbook](docs/DEPLOYMENT.md).

Two application runtimes, web and API; agents remain modules inside the API. No fine-tuning, Kubernetes or Redis.
