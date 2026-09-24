# AWS deployment

## Current demo (20 September 2026)

- Frontend: https://main.dvhyzvzxczywv.amplifyapp.com/
- API: https://pqrxb30pg5.execute-api.ap-south-1.amazonaws.com
- Region: `ap-south-1`; CloudFormation stack: `adda-ai-demo`; Amplify app: `dvhyzvzxczywv`.
- Provider: `demo` for Coding. Search uses a backend-only Tavily key. Documents and Research use real extracted evidence. The public demo API currently has **no shared access token** so visitors can use the workspace without pasting a key.
- Verified: API health, Coding response without a token, document upload/query/Research/delete, frontend root/login/register, and CORS from the Amplify origin. Login and register remain UI previews.

The static Next.js frontend can be hosted on AWS Amplify Hosting. The FastAPI backend runs in Lambda behind API Gateway HTTP API using the SAM template in `infra/template.yaml`. The backend's extracted PDF evidence is stored in a private S3 bucket with a one-day lifecycle rule. The bucket is retained if the stack is deleted, so remove it separately when retiring the demo.

## Prerequisites

- Authenticate an AWS CLI profile in the intended account and region. Check `aws sts get-caller-identity` before creating resources.
- Install AWS SAM CLI and Docker to build the Python 3.13 Lambda package in a compatible environment, or package the Python dependencies for the Lambda runtime and upload the ZIP to private S3 before deploying the template.
- Generate an optional `DemoAccessToken` only if you want a shared gate. Leave it empty for a public hackathon demo. If set, keep it outside the repository and frontend build.
- Optionally provide a backend-only Tavily key for live Search. Without it Search reports its configuration error.
- Select `Provider=demo` until Bedrock model access, model ID, permissions, and real responses are verified in this account and region. The demo Coding response is a fixture.

## API

Validate and deploy `infra/template.yaml` with SAM. The parameters are `FrontendOrigin` (the exact Amplify HTTPS origin), `Provider`, `BedrockModelId`, `DemoAccessToken`, and `TavilyApiKey`. Save the `ApiUrl` output. The template scopes the Lambda execution role to document objects under its private bucket and sets API Gateway route throttling.

```powershell
sam validate --lint --template-file infra/template.yaml
sam build --use-container --template-file infra/template.yaml
sam deploy --guided --template-file .aws-sam/build/template.yaml
```

The Lambda stores extracted chunks, not source PDFs. A document session requires the opaque document token returned by upload; S3 evidence expires after one day. The shared demo access token still permits any holder to call the API. Do not use this design for private multi-user accounts.

## Frontend

Build `apps/web` with `NEXT_PUBLIC_API_BASE_URL` set to the API output, then publish the *contents* of `apps/web/out` to a manual Amplify Hosting deployment, or configure the repository build with `amplify.yml`. On Windows, create the upload zip with POSIX paths (for example Python `zipfile` and `Path.as_posix()`). Do not use `Compress-Archive`, which can break `/_next` asset URLs. Set `FrontendOrigin` to `https://main.<Amplify default domain>` (or the configured custom domain) before testing browser requests. Never put API tokens, Tavily keys, or AWS credentials in `NEXT_PUBLIC_*` variables.

The `/login` and `/register` pages are UI previews; they do not create accounts or establish sessions. The shared access token is entered at runtime in the workspace. Add a real identity provider and per-user authorization before offering private accounts.

## Smoke test

Check `/health`, missing-token rejection, a Coding request with the token, PDF upload/query/delete across requests, Research, and Search if Tavily is configured. Verify the browser can call the API from the deployed HTTPS origin, and check the login/register and theme controls. Inspect CloudWatch logs for unexpected errors without publishing secrets or document text. Record the deployed URLs, region, revision, and verification outcome in demo notes.

For Bedrock, confirm a Converse-compatible model and permission for the actual inference profile and destination model ARNs, then switch the provider and test two distinct prompts. [Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
