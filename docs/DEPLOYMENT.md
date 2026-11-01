# Putting the app online

This guide is written for someone doing it for the first time. It builds a private **test site**. Production repeats the same steps with separate projects, and only happens with a pilot caterer and explicit approval.

You need three accounts: [GitHub](https://github.com) (you have this), [Supabase](https://supabase.com) (database, logins, images) and [Railway](https://railway.com) (runs the app). An [Anthropic](https://console.anthropic.com) key is optional: without it, the chat is off and ordering by hand still works.

## Keep the keys safe

- Keys go only in Railway's Variables screen and in your own `backend/.env`, which git ignores.
- Never paste a key into a chat, an issue, a commit or a screenshot.
- `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY` and `RESEND_API_KEY` can read data, spend money or send mail. If one leaks, replace it in the provider's dashboard straight away, then update Railway.
- Keep test and production keys separate.

## 1. Supabase

1. Create a project named `yummai-test`. Choose an EU region, and save the database password in a password manager.
2. **Database:** open **SQL Editor** and run each file in `database/migrations/` in filename order, one at a time. Stop if one fails. Write down the last file applied, because later updates only need the newer files.
3. **Images:** open **Storage** and create a bucket named exactly `caterer-assets`, set to **Public**. Don't add any policies: the app uploads with its server key, and without policies anonymous users can't write to the bucket.
4. **Logins:** in **Authentication → Sign In / Providers**, turn off **Allow new users to sign up**. Caterers are only added by hand (step 4).
5. Copy these values for step 2, from **Project Settings** and the **Connect** button:
   - `SUPABASE_URL`: the project URL
   - `SUPABASE_ANON_KEY`: the anon or publishable key
   - `SUPABASE_SERVICE_ROLE_KEY`: the service-role or secret key
   - `DATABASE_URL`: the **Transaction pooler** connection string, with your password filled in

## 2. Railway

1. Create a project with **Deploy from GitHub repo** and pick this repository. Railway finds `railway.json` and the `Dockerfile`.
2. Under **Settings**, deploy from the `dev` branch.
3. Under **Variables**, add:

   | Name | Value |
   |---|---|
   | `APP_ENV` | `staging` |
   | `DATABASE_URL` | from step 1 |
   | `SUPABASE_URL` | from step 1 |
   | `SUPABASE_ANON_KEY` | from step 1 |
   | `SUPABASE_SERVICE_ROLE_KEY` | from step 1 |
   | `ANTHROPIC_API_KEY` | optional |
   | `RESEND_API_KEY` | optional, turns on new-order emails |
   | `EMAIL_FROM` | needed with the Resend key; a sender on a domain verified with Resend |
   | `PUBLIC_BASE_URL` | needed with the Resend key; the site's address, for the link in emails |

4. Under **Settings → Networking**, choose **Generate Domain**.

If a setting is missing, the app refuses to start and the deploy log names it (`Missing settings: ...`). That's on purpose.

## 3. Check it is alive

Open `https://<your-domain>/health`. It should show `{"status":"ok"}`.

## 4. Add a caterer

1. In Supabase, open **Authentication → Users → Add user**, enter the caterer's email and a password, and copy the user's ID.
2. Put the Supabase values in `backend/.env` on your computer, then run from `backend/`:

   ```bash
   uv run python -m scripts.create_caterer --slug my-caterer --name "שם העסק" --auth-user-id <the user ID>
   ```

   `TEST_DATABASE_URL` must never point at Supabase, because the test suite wipes that database.

3. The caterer logs in at `/admin/`. Customers use `/c/my-caterer/`.

## 5. Check the AI (optional, costs a little)

With `ANTHROPIC_API_KEY` in `backend/.env`, run from `backend/`:

```bash
uv run python -m scripts.ai_check
```

It sends five Hebrew messages to the real model against a sample menu and doesn't touch the database. Read the replies yourself, then check the printed cost per message. The prices in the script are estimates, so confirm them against current pricing.

## Before a real caterer uses it

Run through this on the test site:

- [ ] Log in as a caterer, add a dish with a photo, and see the photo on the customer page.
- [ ] Place an order as a customer, approve it as the caterer, and see the answer on the customer's private link.
- [ ] Confirm that one caterer can't see another's orders.
- [ ] Rate limits count real visitors: submit 21 new orders in an hour from one connection and check that the last is refused, then check from another connection that orders still work. If everyone is refused together, or nobody is, Railway's forwarded address isn't what `core/rate_limit.py` expects, so fix that first. Also send a request with your own extra `X-Forwarded-For` header, on a separate line, and check that it doesn't reset your count.
- [ ] Check the browser console on the customer page and dashboard for Content Security Policy errors.
- [ ] Confirm backups on your Supabase plan, and take one by hand (below).
- [ ] Resolve the decisions still open for launch: allergen disclaimer legal review (#8), VAT, portion defaults (#3), and platform domain (#20).

## Updating the live app

1. Apply any new migration files first, using the SQL Editor. Migrations never run automatically, so a bad one can't run during a deploy.
2. Merge to the deployed branch. Railway rebuilds, and switches over only after `/health` responds.

Write a migration so the running version still works with it, because the database changes before the code does.

## Backups

Check what your Supabase plan includes under **Database → Backups**. To take your own copy, install the PostgreSQL tools and run:

```bash
pg_dump "<DATABASE_URL using the Session pooler>" --no-owner --file yummai-backup.sql
```

The file holds customers' personal details, so store it somewhere private and never commit it. Practise restoring into a separate test project at least once before the pilot. Images in Storage aren't included.

## Rolling back

- **Bad code:** in Railway, open **Deployments**, pick the last good one and choose **Redeploy**.
- **Bad migration:** there are no automatic undo scripts. Write and run a corrective SQL file, or restore from a backup, which loses anything newer than the backup.

## Limits to know about

- Rate limits are kept in the server's memory, so run **one** Railway instance. A restart resets the counts. More instances would need a shared store.
- New-order emails need a Resend account and a verified domain, and have not been tested with the real provider. Until then caterers check the dashboard. A failed email is logged and not retried (#13).
