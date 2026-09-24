# NexusAI handoff

## Current goal
Finish the professional frontend for the hackathon. User will handle deployment separately.

## Authoritative working copy
Use `outputs/nexusai-mvp`, branch `codex/hackathon-mvp`. The active frontend on
localhost:3000 and API on 127.0.0.1:8000 run this copy. Original `outputs/nexusai`
has older code but still supplies the Python venv and backend environment to the
startup script. Do not overwrite either checkout or run simultaneous frontend edits.

## Current working state
- Coding: working labelled fixture, real Bedrock inference unverified.
- Documents: real PDF/TXT keyword retrieval, page citations, temporary token-protected uploads.
- Research: plan, retrieve twice, assemble cited evidence; no model synthesis.
- Search: Tavily key configured; current adapter requests a provider summary and sources.
  Earlier Cursor notes report live Search success; this latest UI pass did not repeat paid calls.
- AWS: Amplify + API Gateway/Lambda deployed in `ap-south-1` (`adda-ai-demo`); health verified. No live Bedrock claim. Public demo needs no access token. Fluid Orb UI live (Amplify job 7).

## Completed this pass
Audited both checkouts, running services, environment presence without showing secrets,
Cursor's new startup script, Search summary behavior, frontend and demo notes.
Replaced promotional dark UI with neutral light workspace, compact navigation,
focused composer, result-first layout and a separate activity panel on desktop.
Kept upload, citations, history, code highlighting/copy and existing API contracts.
Removed external font request and decorative noise. Search badge says Enabled:
configuration is not proof of a successful live request.

## Verified
- Full backend suite: 71 passed (one existing dependency deprecation warning).
- Final frontend typecheck and production build passed, including the result-first layout.
- Browser: Coding fixture; sample PDF budget INR 180,000 cited page 2;
  Research four-step workflow; mobile menu and history selection.
- Desktop 1440px and mobile 390px checks, no horizontal overflow observed.
- Browser error/warning log empty during this pass.

## Files changed in this pass
`apps/web/app/page.tsx`, `apps/web/app/globals.css`, this file, `docs/STATUS.md`.
Pre-edit frontend copies saved under workspace `work/frontend-before-refinement-*`.
No backend, credentials, startup settings, or deployment resources changed.
Combined older Cursor/Codex changes are still uncommitted; authorship cannot be
reconstructed precisely from one shared dirty tree. Do not attribute all changes to one tool.

## Commands
From MVP root: `../nexusai/.venv/Scripts/python.exe -m pytest services/api/tests -q`.
From apps/web: `npm.cmd run typecheck`, `npm.cmd run build`.
API: `../nexusai/.venv/Scripts/python.exe scripts/start_api.py`.
Frontend: `npm.cmd run dev -- --hostname 127.0.0.1 --port 3000`.

## Remaining / exact next action
Hosted demo is live and public: visitors do not need a demo access token.
Local frontend/API remain available for development. Bedrock live inference remains pending.
