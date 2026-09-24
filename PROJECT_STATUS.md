# ADDA AI project status

**ADDA AI**. Live site: https://main.dvhyzvzxczywv.amplifyapp.com/

## Current focus

Production Cognito authentication on branch `feat/production-auth`, preserving the deployed workspace UI.

## Auth

- Email register → `/verify-email` → login
- Google via Cognito Hosted UI (needs `NEXT_PUBLIC_COGNITO_DOMAIN` + IdP)
- Forgot password → `/forgot-password`
- Workspace gated by `AuthGate`; API gated by Cognito JWT when `AUTH_REQUIRED=true`
- Registered users: Cognito Users console is source of truth

## UI parity

Local must use the BrandMark / fluid-orb workspace (production-baseline), not the simplified letter-A tree that landed on `origin/main`.
