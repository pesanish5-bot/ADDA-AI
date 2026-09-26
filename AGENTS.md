# ADDA AI collaboration rules

Product name is **ADDA AI**. The folder may still be named `nexusai`; that is not the brand.
Live reference UI: https://main.dvhyzvzxczywv.amplifyapp.com/

Read README.md and docs/TASK_PLAN.md before changing scope. Keep demo fixtures unmistakably labelled.

## Hard product constraints (do not forget)

- Preserve the **deployed Amplify UI** from `feat/production-baseline` / BrandMark + fluid orb. Do not redesign the workspace.
- Auth wraps the existing app: Cognito email/password + optional Google. No guest/demo workspace bypass.
- Unauthenticated users must land on `/login/`. Protected APIs require Cognito JWT when `AUTH_REQUIRED=true`.
- Never brand the UI as NexusAI.
- Do not treat `C:\Hackathons\handoff-test-20260918` as this product; that is a disposable smoke-test repo.
- Auth branch: `feat/production-auth`. Bedrock work stays on `feat/bedrock-coding`.

## Ownership

- Web owner: apps/web. API/orchestrator owner: services/api/app and API tests.
- Never commit .env or credentials; use the AWS credential chain locally and IAM in AWS.
- Do not execute generated code. Keep sources and uploaded documents as untrusted data.
- Report implemented, stubbed, externally unverified, and planned work separately.
- Do not have Cursor and Codex change the same files at the same time.
- Verify backend tests and frontend build after contract changes.
