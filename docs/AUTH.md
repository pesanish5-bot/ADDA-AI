# Authentication (Amazon Cognito)

ADDA AI uses Amazon Cognito for email/password and optional Google sign-in.
The deployed workspace UI is preserved; auth wraps it.

Live UI reference: https://main.dvhyzvzxczywv.amplifyapp.com/

## Frontend env (`apps/web/.env.local`)

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_COGNITO_USER_POOL_ID=ap-south-1_xxxxx
NEXT_PUBLIC_COGNITO_CLIENT_ID=xxxxxxxx
NEXT_PUBLIC_COGNITO_DOMAIN=your-prefix.auth.ap-south-1.amazoncognito.com
```

## API env (`services/api/.env`)

```env
COGNITO_USER_POOL_ID=ap-south-1_xxxxx
COGNITO_CLIENT_ID=xxxxxxxx
COGNITO_REGION=ap-south-1
AUTH_REQUIRED=true
```

## Cognito console checklist (email codes)

1. User pool → **Sign-in** → Email
2. **Self-registration** enabled
3. **Attributes** → email required; auto-verify **email**
4. **Messaging** → Cognito default email (or SES with production access / verified recipients)
5. App client: public, **no client secret**, ALLOW_USER_SRP_AUTH + ALLOW_USER_PASSWORD_AUTH + refresh
6. After signup, user status must be **UNCONFIRMED** until the code is entered
7. Check spam; Cognito default sender is often `verificationemail@amazoncognito.com`

If email never arrives while users show as UNCONFIRMED:

- If using **SES**: leave sandbox or verify the recipient; confirm SES region matches Cognito
- If Cognito default email: wait for rate limits (50/day) and check spam
- Do **not** manually confirm users to “fix” delivery — fix messaging instead

## Google federation

1. Google Cloud Console → OAuth client (Web) with redirects:
   - `https://<cognito-domain>/oauth2/idpresponse`
2. Cognito → Federated identity provider → Google (client id + secret stored in Cognito only)
3. App client → Hosted UI: enable Cognito + Google; scopes `openid email profile`
4. Callback URLs:
   - `http://127.0.0.1:3000/`
   - `https://main.dvhyzvzxczywv.amplifyapp.com/`
5. Sign-out URLs:
   - `http://127.0.0.1:3000/login/`
   - `https://main.dvhyzvzxczywv.amplifyapp.com/login/`
6. Set `NEXT_PUBLIC_COGNITO_DOMAIN` (no `https://`)

Never put the Google client secret in `NEXT_PUBLIC_*`.

## Password policy (frontend must match Cognito)

Default ADDA AI pool policy displayed in the UI:

- Minimum length 8
- Require lowercase
- Require number
- Uppercase / symbol not required

If you change the pool policy, update `PASSWORD_RULES` in `apps/web/lib/cognito.ts`.

## Routes

| Path | Access |
|------|--------|
| `/login/` `/register/` `/verify-email/` `/forgot-password/` | Public |
| `/` (workspace) | Authenticated only |
| `/api/chat`, `/api/documents*` | Bearer Cognito ID token when `AUTH_REQUIRED=true` |
| `/health` | Public |

## Amplify

Set the same `NEXT_PUBLIC_COGNITO_*` and `NEXT_PUBLIC_API_BASE_URL` in Amplify env, then rebuild.
