# Development

## Runtimes

- Python 3.13 (deploy target and CI). A 3.14 venv works locally but resolve dependency
  differences against 3.13 before trusting a lock change.
- Node.js 22, npm 10.
- Optional: Docker for `compose.yaml`, AWS CLI + SAM CLI for cloud work.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/api/requirements-dev.txt
Copy-Item services/api/.env.example services/api/.env
Copy-Item apps/web/.env.example apps/web/.env.local
Push-Location apps/web; npm ci; Pop-Location
```

Run the API (`scripts/start_api.py` or `uvicorn app.main:app --reload --port 8000` from
`services/api`) and the web app (`npm run dev -- --hostname 127.0.0.1 --port 3000`).

## Checks (run before every commit)

```powershell
Push-Location services/api
python -m ruff check .            # lint; `--fix` for import order
python -m pytest -q               # 89 tests, external calls mocked
python -m pip_audit -r requirements.txt --strict
Pop-Location
Push-Location apps/web
npm run typecheck
npm run build
npm audit --omit=dev --audit-level=high
Pop-Location
```

CI (`.github/workflows/checks.yml`) runs the same plus `sam validate --lint`.

## Dependencies

`requirements.in` / `requirements-dev.in` are the sources; the `.txt` files are pinned
locks produced with `pip-compile <file>.in -o <file>.txt --no-header --no-annotate
--strip-extras`. Edit the `.in`, recompile, review the diff, commit both.

## Configuration

All backend settings are environment variables documented in `services/api/.env.example`
and typed in `app/config.py`. `Settings.validate_for_environment()` runs at startup;
add a check there when introducing a setting that is unsafe in production.

## Code layout

- `services/api/app/main.py` — app factory, middleware order, routes, error handlers.
- `app/config.py` — settings and environment guards.
- `app/observability.py` — request id, JSON logging, `annotate()` for safe log fields.
- `app/ratelimit.py` — per-client limiter middleware.
- `app/body_limit.py` — request body caps.
- `app/graph.py` — LangGraph routing; `app/agents/*` — document, search, research.
- `app/providers.py` — Bedrock Converse adapter and error mapping.
- `apps/web/app/page.tsx` — workspace UI; `apps/web/components/*` — brand, orb, auth views.

## Conventions

- Log with `log_event()` / `annotate()`; never log prompts, document text or tokens.
- Raise `ProviderError(message, code, status)` for user-visible failures; codes are part
  of the API contract (`docs/ARCHITECTURE.md`).
- New settings need a `.env.example` line, a `template.yaml` parameter when
  cloud-relevant, and a test.
- Keep demo fixtures labelled as fixtures in UI copy and API `provider` fields.

## Git workflow

`main` is protected and deployable. Branch from it (`feat/*`, `fix/*`), open a PR, CI
must be green, squash merge. Tag `v0.x.y` for deployments (automation in Phase 6).
Never force-push shared branches. Commit messages: `area: what changed` plus a short body.
