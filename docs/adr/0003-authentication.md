# ADR-0003: Authentication and authorization

Status: Accepted 2026-09-24. Implementation: Phase 2.

## Context

There is no identity. `/login` and `/register` are static previews and an optional shared
`X-Demo-Token` gates the API. The frontend is a static export (no server), so anything
requiring server-side session handling (Auth.js in its default mode) would force a
Node runtime we do not otherwise need.

## Options

- Amazon Cognito user pool + Hosted UI (or Amplify Auth UI) with PKCE; API verifies RS256
  JWTs against the pool JWKS. Stays inside the existing AWS account and IAM model; free
  tier covers the foreseeable user count.
- Clerk / Supabase Auth: faster UI, but a new vendor, new billing and a second identity
  store outside AWS.
- Auth.js: needs a server runtime for the frontend.

## Decision

Cognito. Frontend obtains ID/access tokens with PKCE and sends `Authorization: Bearer`.
FastAPI dependency validates signature, issuer, audience and expiry with a cached JWKS
and yields `user_id = sub`. `X-Demo-Token` remains only for `APP_ENV=development`.

## Consequences

- Authorization is enforced in the API on every user-owned resource; the frontend is not a
  security boundary.
- Account deletion must cascade: Cognito user, Postgres rows, S3 objects.
- Email verification and password policy configured in the pool; MFA optional initially.
