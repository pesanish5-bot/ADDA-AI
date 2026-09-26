# Security

## Reporting

Report vulnerabilities privately to the repository owner (GitHub private vulnerability
reporting or a direct message). Do not open public issues for security problems.

## Current security model (2026-09-25, integration branch)

- **Identity**: Amazon Cognito email registration, verification, recovery and signed JWT
  validation. Staging/production fail startup unless authentication, Cognito and the
  durable profile table are configured. This protected configuration is deployed to the
  published staging environment.
- **Document access**: both the authenticated Cognito subject and a per-document random
  token are required. S3 stores only the token hash beside extracted text. Cross-user
  lookup and deletion return the same 404 as missing data. Tokens are never logged.
- **Transport**: HTTPS via API Gateway and Amplify. CORS is limited to configured origins
  and three methods; `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`
  and `Cache-Control: no-store` are set on API responses.
- **Input handling**: uploads are checked by magic bytes, size (5 MB), page count (30),
  decompression and text bounds; filenames are never trusted or stored as paths. Chat
  bodies are capped at 64 KB and 12,000 characters, schema `extra=forbid`.
- **Model and tools**: only the Coding route calls a model. No tool execution, no code
  execution, no arbitrary URL fetching. Document text is not sent to a model today.
- **Rate limiting**: API Gateway route throttle plus a per-client, per-process limiter
  (chat 20/min, upload 10/min). Not a quota system.
- **Secrets**: none in the repository. Local `.env` files are ignored. Cloud values are
  CloudFormation `NoEcho` parameters → Lambda environment (to be moved to Secrets Manager
  in Phase 6). Never place provider keys in `NEXT_PUBLIC_*` variables.
- **Logging**: JSON access logs with request id, method, path, status, duration, agent,
  provider and error code. Never prompts, document content, tokens or credentials; a test
  enforces this.
- **Dependencies**: `pip-audit` and `npm audit --audit-level=high` run in CI.

## Environment guards

`APP_ENV=staging` and `production` refuse to start without mandatory Cognito auth and a
durable profile table, with a development JWT secret, or with insecure origins.
Production also refuses an unapproved demo fixture; Bedrock requires a model id.
Interactive API docs are disabled in production.

## Data handling

| Data | Where | Retention | Third parties |
| --- | --- | --- | --- |
| Uploaded document text | API process memory or private S3 (SSE-S3) | 1 h in memory, 1 day in S3 | none |
| Chat prompts | request only | not stored server-side | Amazon Bedrock (Coding, when enabled) |
| Search queries | request only | not stored | Tavily (when enabled) |
| Task history | browser sessionStorage | until tab closes | none |
| Access logs | CloudWatch | account default | AWS |
| User profile and auth audit events | DynamoDB (encrypted, PITR) | profile lifetime; events 90 days | AWS |

No regulatory compliance is claimed. A privacy notice, data export and deletion endpoints
are planned in Phase 7.

## Known gaps

See `docs/PRODUCTION_AUDIT.md` (Security table) and the Security Issues section of
`PROJECT_STATUS.md`.
