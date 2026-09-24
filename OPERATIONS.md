# Operations

## Environments

| Name | Frontend | API | Notes |
| --- | --- | --- | --- |
| local | http://127.0.0.1:3000 | http://127.0.0.1:8000 | `APP_ENV=development`, fixture allowed |
| demo (current cloud) | Amplify `main` branch, `ap-south-1` | API Gateway + Lambda `adda-ai-demo` | Single shared environment; treat as staging |

Separate staging and production stacks arrive in Phase 6.

## Health and readiness

- `GET /health` — liveness and configuration summary. No network calls. Safe for uptime
  monitors.
- `GET /ready` — dependency checks (`document_bucket` via `HeadBucket`, provider
  configuration). Returns 503 with the failing check list. Never invokes a model.

## Logs

One JSON line per request from logger `adda.api`:

```json
{"ts":"...","level":"INFO","logger":"adda.api","message":"request","request_id":"…","method":"POST","path":"/api/chat","status":200,"duration_ms":412,"route":"chat","agent":"coding","provider":"bedrock"}
```

Every response carries `X-Request-ID`; error bodies include `detail.request_id`. Ask users
for that id when triaging. Lambda logs land in CloudWatch log group
`/aws/lambda/<function>`; filter with `{ $.request_id = "…" }`.

Levels: 2xx/3xx INFO, 4xx WARNING, 5xx ERROR. `configuration warning` lines at startup
list unsafe-but-allowed settings.

## Alarms and dashboards

Not yet created (Phase 1). Planned: 5xx rate > 5% over 5 min, p95 duration > 20 s,
Lambda throttles > 0, Bedrock invocation count per hour, AWS Budget on the account.

## Deploy and rollback (current CloudFormation/Amplify path)

API deploy without Docker or SAM CLI (profile `nexusai`, region `ap-south-1`):

```powershell
python scripts/build_lambda_package.py                     # build/lambda/api.zip
# template copy with CodeUri: api.zip, written WITHOUT a UTF-8 BOM (PowerShell Set-Content adds one)
aws cloudformation package --template-file build/lambda/template.yaml `
  --s3-bucket adda-ai-artifacts-<account>-ap-south-1 --s3-prefix adda-ai-demo `
  --output-template-file build/lambda/packaged.yaml
aws cloudformation deploy --template-file build/lambda/packaged.yaml --stack-name adda-ai-demo `
  --capabilities CAPABILITY_IAM --parameter-overrides file://params.json --no-fail-on-empty-changeset
```

Unlisted parameters keep their previous values. Always pass `DemoAccessToken` explicitly
(currently empty for the public demo) so the stack never silently re-enables the gate.
Then check `/health`, `/ready` and one chat call with `X-Request-ID`.

Rollback:

- API: redeploy the previous commit with the same steps, or in the CloudFormation
  console pick the stack → Stack actions → roll back to the previous template.
  Parameters are unchanged unless stated in the release note.
- Frontend: Amplify console → the app → `main` → previous successful job → **Redeploy this
  version**. Manual zip deploys keep the last artifacts.

Record every cloud change in `PROJECT_STATUS.md` (Infrastructure section).

## Incident checklist

1. Confirm with `/health` and `/ready` from outside; note `X-Request-ID` of a failing call.
2. Query logs by request id; check `error_code` and `status`.
3. Provider incident (`provider_unavailable`, `aws_*`): confirm Bedrock/Tavily status; the
   app already fails closed and tells the user; do not switch production to the fixture.
4. Abuse (`rate_limited` spikes from one client): tighten API Gateway throttle or add a
   WAF IP rule; the per-process limiter is a brake, not a block list.
5. Suspected data exposure: disable the `documents/*` S3 prefix access on the role, rotate
   `DEMO_ACCESS_TOKEN`, preserve logs, then investigate. Ask before deleting anything.

## Backups

Documents are intentionally short-lived and not backed up. There is no database yet.
When Postgres arrives (Phase 2): automated snapshots, 7-day PITR, quarterly restore drill
logged here.

## Cost controls

Paid calls happen only with `NEXUS_PROVIDER=bedrock` or a `TAVILY_API_KEY`. Both are
bounded per request. Do not enable either in a shared environment without a budget alarm.
