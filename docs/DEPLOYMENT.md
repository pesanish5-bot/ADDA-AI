# AWS deployment

## Current demo (20 September 2026)

- Frontend: https://main.dvhyzvzxczywv.amplifyapp.com/
- API: https://pqrxb30pg5.execute-api.ap-south-1.amazonaws.com
- Region: `ap-south-1`; CloudFormation stack: `adda-ai-demo`; Amplify app: `dvhyzvzxczywv`.
- Provider: `bedrock` for Coding using `apac.amazon.nova-lite-v1:0`. Search uses a backend-only Tavily key. Documents and
  Research use real extracted evidence. Cognito authentication is mandatory for workspace
  API routes; no shared demo token is configured.
- Verified on the published revision (Amplify job 14): health/readiness, anonymous 401,
  frontend root/login/register/recovery routes, adaptive appearance controls, embedded
  Cognito configuration and CORS.
  A full real-recipient signup/login/recovery smoke test is still required.

The static Next.js frontend can be hosted on AWS Amplify Hosting. The FastAPI backend runs in Lambda behind API Gateway HTTP API using the SAM template in `infra/template.yaml`. The backend's extracted PDF evidence is stored in a private S3 bucket with a one-day lifecycle rule. The bucket is retained if the stack is deleted, so remove it separately when retiring the demo.

## Prerequisites

- Authenticate an AWS CLI profile in the intended account and region. Check `aws sts get-caller-identity` before creating resources.
- Install AWS SAM CLI and Docker to build the Python 3.13 Lambda package in a compatible environment, or package the Python dependencies for the Lambda runtime and upload the ZIP to private S3 before deploying the template.
- Generate an optional `DemoAccessToken` only if you want a shared gate. Leave it empty for a public hackathon demo. If set, keep it outside the repository and frontend build.
- Optionally provide a backend-only Tavily key for live Search. Without it Search reports its configuration error.
- Keep `Provider=demo` only for deliberate non-production smoke stacks. This staging stack
  uses the live APAC Nova Lite inference profile after two bounded verification calls.

## API

Validate and deploy `infra/template.yaml` with SAM. The stack provisions Cognito,
DynamoDB profiles, the protected API, private document storage and optional Bedrock/cost
alerts. Save `ApiUrl`, `CognitoUserPoolId`, `CognitoUserPoolClientId` and
`CognitoDomain` from the outputs. `AuthRequired` is intentionally restricted to `true`.
After deploying, check `GET /ready` and verify an unauthenticated API call returns 401.

```powershell
sam validate --lint --template-file infra/template.yaml
sam build --use-container --template-file infra/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml
```

### Enabling real Bedrock Coding

1. Check the intended model/profile is active in the target account and region.
2. Run two bounded local calls: `python -m app.check_bedrock --profile nexusai --model apac.amazon.nova-lite-v1:0 --invoke` from `services/api`.
3. Deploy with `Provider=bedrock BedrockModelId=apac.amazon.nova-lite-v1:0 AlertEmail=<ops email> MonthlyBudgetUsd=<amount>`. `AlertEmail` creates the SNS topic, AWS Budget (50/80/100 % actual, 100 % forecast) and the Lambda/Bedrock alarms; confirm the SNS subscription email.
4. Verify through the application: `/health` shows `provider: bedrock` and the model; a browser Coding request returns `provider: bedrock` with `usage.input_tokens/output_tokens`; CloudWatch access log shows `model`, token counts and `provider_latency_ms`.

Model choice: APAC Amazon Nova Lite is the verified cost-conscious default. Claude Haiku
4.5 reported entitlement but returned access denied during live verification, so it is not
used. Add other models only through a tested server-side allowlist with separate cost and
latency limits. APAC profiles may route within their listed APAC regions.

Per-request limits: `BEDROCK_MAX_TOKENS` (default 1500), read timeout 20 s, at most 2 attempts (retry only on throttling/transient errors), 12,000-character prompt cap, per-client rate limit 20 chat requests/min, API Gateway throttle 2 rps.

The Lambda stores extracted chunks, not source PDFs. A document session requires the opaque document token returned by upload; S3 evidence expires after one day. The shared demo access token still permits any holder to call the API. Do not use this design for private multi-user accounts.

## Frontend

Build `apps/web` with `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_COGNITO_USER_POOL_ID`
and `NEXT_PUBLIC_COGNITO_CLIENT_ID` set from stack outputs, then publish the *contents*
of `apps/web/out`. Set the domain and explicit Google flag only after Google federation
is configured. Never put API tokens, provider keys or AWS credentials in public variables.

Email registration sends a Cognito verification code and establishes a real session after
confirmation and login. The workspace redirects unauthenticated visitors to `/login/`.

## Smoke test

Create and verify a new account, sign in, confirm missing/expired-token rejection, run a
Coding request, upload/query/delete a document, sign out, and verify another account
cannot access the first account's document. Also test password recovery, throttling and
disabled-account rejection. Inspect CloudWatch logs without publishing secrets or text.

For Bedrock, confirm a Converse-compatible model and permission for the actual inference profile and destination model ARNs, then switch the provider and test two distinct prompts. [Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
