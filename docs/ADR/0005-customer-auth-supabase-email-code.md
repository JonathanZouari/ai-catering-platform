# ADR 0005 — Customer accounts with a passwordless email code (Supabase Auth)

Status: Accepted (Phase 3) · Date: 2026-11-02 · Resolves OPEN_DECISIONS #1

## Context
Customers need to come back to their drafts and quotes, and later to their AI chat history. The business decided customers must have an account, signing in with email only and no password.

## Decision
- Customers sign in with a **6-digit code sent by email** through **Supabase Auth**. A code was chosen over a magic link because it keeps working when the email opens on another device or in a mail app's built-in browser.
- The browser uses supabase-js (pinned version, loaded from a CDN, configured from `GET /api/auth/config`). Supabase stores and refreshes the session.
- The browser sends the access token as `Authorization: Bearer`. The backend (`core/customer_auth.py`) verifies:
  - the signature against the project's JWKS (`/auth/v1/.well-known/jwks.json`, ES256/RS256),
  - `aud = authenticated`, `iss = <SUPABASE_URL>/auth/v1`, `exp`, and the presence of `sub` and `email`.

  It fails closed, with 401, on any problem.
- Ownership comes only from the token's `sub`, mapped to `customers.auth_user_id`, and never from request data. The stored email is the verified login email.
- The first `PUT /api/me` creates the customer row (name and phone). Customers created without an account (sample data, for example) keep `auth_user_id` null.

## Consequences
+ We write no code that issues, stores or expires login codes. Sessions and refresh tokens are handled by Supabase.
+ The verification is unit-tested with locally signed tokens. No Supabase is needed in CI.
− Every environment, including local manual testing, needs a Supabase project. That project must use **asymmetric JWT signing keys**: the legacy shared secret publishes no JWKS, so logins would fail closed. Its email template must include `{{ .Token }}`.
− Supabase's built-in mailer is rate-limited. Real customer volume needs a custom SMTP sender, tied to OPEN_DECISIONS #13.
− The owner still uses the temporary `ADMIN_TOKEN`. The next step is the same sign-in plus an admin role check.
