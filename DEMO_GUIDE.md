# ADDA AI — local demo guide

Run the frontend and API from the same checkout of this repository. Do not use leftover local services on ports 8001–8008.

## Canonical URLs

| Role | URL |
| --- | --- |
| Frontend | [http://127.0.0.1:3000](http://127.0.0.1:3000) |
| Backend | `http://127.0.0.1:8000` |
| Health | `http://127.0.0.1:8000/health` |

Go / no-go: the UI badge reads **Workspace connected**. `GET /health` is `provider: demo`, `capabilities.coding: true`, `capabilities.document: true`, `capabilities.search: true`.

Keep `NEXUS_PROVIDER=demo`. Coding is a labelled fixture. **Do not claim Bedrock works.**

Use a wide window so the activity panel sits beside the result.

## Start commands

From the repository root, create and install the `.venv` as described in [README.md](README.md).

**1. Stop leftover local servers** so nothing else is bound to 3000 or 8000.

**2. Backend** (terminal 1):

```powershell
.\.venv\Scripts\python.exe scripts\start_api.py
```

This binds **8000**, keeps Coding in demo mode, enables documents, allows `http://localhost:3000` and `http://127.0.0.1:3000`, and loads a nonempty `TAVILY_API_KEY` from `services/api/.env`. It does not print the key.

**3. Frontend** (terminal 2):

```powershell
cd apps\web
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

`apps/web/.env.local` must be exactly:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

**4. Open** [http://127.0.0.1:3000](http://127.0.0.1:3000) — not 3002.

A reload clears task history and the attachment. An API restart clears uploaded documents. Reattach the sample PDF if that happens.

## Exact demo sequence

### 1. Coding (about 45 seconds)

Click **Code a function**, then **Run task**.

Tested prompt: `Write a Python function to reverse a string.`

Expected: **ADDA → Coding Agent**; labelled **fixed sample, not an AI-generated answer**; highlighted `reverse_string` block; **Copy code**; activity **Router → Coding agent**. Footer: **Fixed coding fixture · no model**.

### 2. Live Search (about 45 seconds)

Click **Search the web**, then **Run task**.

Tested prompt: `What are the latest developments in AI agents?`

Expected: **ADDA → Search Agent**; Tavily summary plus **Evidence & sources** with real `https://` links; activity **Router → Search agent** (`Queried Tavily (basic, max 5)`). Footer: **Retrieved web sources · Tavily**.

### 3. PDF / document Q&A (about 60 seconds)

Click **Explore sample document**. This attaches the fictional three-page `atlas-project.pdf`.

Tested prompt: `What is the approved budget?`

Expected: **ADDA → Document Agent**; excerpt containing **INR 180,000**; source card **Page 2**; activity **Router → Document retrieval**. Say this is local keyword retrieval, not a language model.

### 4. Research (about 60 seconds)

With the PDF still attached, click **Research this document**, then **Run task**.

Tested prompt: `Research this document: summarize the evidence and identify the risks and limitations.`

Expected: **ADDA → Research Agent**; **Research evidence brief** with **Extractive workflow — no AI synthesis**; page-cited excerpts; activity **Router → Research plan → Collect evidence → Evidence brief**. Session history on the left can switch back to Coding, Search, or the budget answer.

## Fallback if Search or the API fails

1. Confirm you are on [http://127.0.0.1:3000](http://127.0.0.1:3000), not 3002, and that `/health` is `http://127.0.0.1:8000/health`.
2. If the badge is **Workspace offline**, the backend is not running. Restart `scripts\start_api.py`.
3. If Search shows **Key needed** or `/health` has `search: false`, add `TAVILY_API_KEY` to `services/api/.env` (backend only), save the file, restart the API. Do not put the key in `apps/web/.env.local`. Skip Search and continue with Documents + Coding rather than inventing results.
4. If a Search request returns `search_not_configured`, `search_unauthorized`, `search_rate_limited`, or `search_timeout`, say Search is unavailable and move to the PDF.
5. Never fall back to an older process on **8001** (that API reports `search: false`).

## Known limitation

Coding currently uses the labelled **demo** provider because live Amazon Bedrock inference is unavailable / unverified. Do not say Coding is a model answer. Hosted demo URLs (when used): frontend `https://main.dvhyzvzxczywv.amplifyapp.com/`, API `https://pqrxb30pg5.execute-api.ap-south-1.amazonaws.com`. The public demo currently needs **no access token**. Documents are not embeddings, OCR, or LLM synthesis. Session history and uploads do not survive reload or API restart.
