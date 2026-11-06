# Deploy (Phase 6)

How the `development` environment goes live: the `dev` branch → Railway `development` → Supabase `ai-catering-dev`. Production (`main`) follows the same steps with its own projects, only after explicit approval (ARCHITECTURE §6).

## How a deploy works

1. A push to `dev` (a merged PR) makes Railway build the `Dockerfile`.
2. **Pre-deploy:** Railway runs `python -m app.core.migrate` (the service's pre-deploy command). It applies every file in `database/migrations/` that isn't listed in `schema_migrations` yet. Each file runs once, in name order, in its own transaction. If one fails, the deploy stops and the running version stays up.
3. Railway starts the new version and waits for `/health` to answer 200.

The app never creates or alters tables on Postgres. Only the migrations do. `create_all` runs on SQLite only.

## One-time setup

### 1. Supabase project `ai-catering-dev`
- Pick a region near Israel, for example `eu-central-1` (Frankfurt).
- **Asymmetric JWT keys:** Project Settings → JWT Keys. The project must sign with an asymmetric key (ES256 or RS256). If it still uses the legacy shared secret, migrate to signing keys there. Without them, every customer login fails closed (ADR 0005).
- **Email templates:** Authentication → Emails. In both **Magic Link** and **Confirm signup**, put the code `{{ .Token }}` in the body. New customers get "Confirm signup" and returning customers get "Magic Link". Hebrew example: `קוד הכניסה שלכם ל-Yummai: {{ .Token }}`.
- **SMTP:** Authentication → Emails → SMTP Settings. Use a real sender, for example Gmail with an app password (dev), Resend, Brevo or Postmark. The built-in mailer only sends a few emails an hour. Supabase sends these login emails from its own servers, so Railway's SMTP block doesn't affect them. Custom SMTP must be on before the templates can be edited.
- **URL Configuration:** set the Site URL to the Railway domain from step 2. Login uses a code, not a link, so no redirect URLs are needed.
- **Data API:** Integrations → Data API → turn off. The app never uses it, and every table also has RLS on with no policies (migration 0014), so the public anon key can't reach the data either way.
- **Connection string:** Connect → Connection string. Use the **Session pooler** (port 5432, IPv4). The transaction pooler (6543) works too, because the app turns off prepared statements. The direct connection is IPv6-only, which Railway doesn't support by default.

### 2. Railway
- New Project → Deploy from GitHub repo → `idanss0/ai-catering-platform`.
- Environment `development` → service settings → Source branch `dev`. Railway no longer reads `railway.json` for new services (Config as Code is deprecated), so set these in the service settings: Deploy → Pre-deploy command `python -m app.core.migrate`, Healthcheck Path `/health`; Scale → Region EU West. The Dockerfile is detected automatically. `railway.json` stays in the repo as a record of these values.
- Settings → Networking → Generate Domain. Put this address in `PUBLIC_BASE_URL` and in the Supabase Site URL.
- Variables (Railway sets `PORT` itself):

| Variable | Value |
|---|---|
| `APP_ENV` | `development` |
| `DATABASE_URL` | Session pooler string from Supabase (with the database password) |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | Project Settings → API Keys → publishable or anon key |
| `ADMIN_TOKEN` | a new long random value, not the local one: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `BREVO_API_KEY` | Brevo → SMTP & API → API Keys. Railway blocks outbound SMTP below its Pro plan, so the app sends through Brevo's HTTPS API |
| `SMTP_FROM` | the sender address; verify it in Brevo → Senders first |
| `OWNER_EMAIL` | where new orders are sent |
| `PUBLIC_BASE_URL` | `https://<railway-domain>` |

Leave `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` unset. The chat panel then stays hidden and the API answers 503 (the assistant is tested locally against a fake Claude). Never set `SUPABASE_SERVICE_ROLE_KEY` unless code needs it, which none does yet.

## After the first deploy
1. Deploy logs should show `13 migration(s) applied: ...`. Later deploys show `0 migration(s) applied`.
2. `https://<domain>/health` returns 200.
3. Owner: `/admin/` with the new `ADMIN_TOKEN`. Add categories, dishes, time slots and delivery zones, and set the order rules and kashrut certificate.
4. Customer: `/customer/` → email → 6-digit code → profile → an event and an order → submit. The owner gets an email.

## Checking migrations locally
Before merging a new migration, run the suite on a real Postgres. It wipes that database, so use an empty one:

```bash
cd backend
TEST_DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/yummai_check uv run pytest
```

Without `TEST_DATABASE_URL`, the tests run on SQLite as before.
