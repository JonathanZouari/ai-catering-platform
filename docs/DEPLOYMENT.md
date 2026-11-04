# Putting the app online

This guide is written for someone doing it for the first time. It builds a private **test site**. Production repeats the same steps with separate projects, and only happens with a pilot caterer and explicit approval.

You need three accounts: [GitHub](https://github.com) (you have this), [Supabase](https://supabase.com) (logins, images) and [Railway](https://railway.com) (runs the app and holds the database file). An [Anthropic](https://console.anthropic.com) key is optional: without it, the chat is off and ordering by hand still works.

## Keep the keys safe

- Keys go only in Railway's Variables screen and in your own `backend/.env`, which git ignores.
- Never paste a key into a chat, an issue, a commit or a screenshot.
- `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY` and `RESEND_API_KEY` can read data, spend money or send mail. If one leaks, replace it in the provider's dashboard straight away, then update Railway.
- Keep test and production keys separate.

## 1. Supabase

1. Create a project named `yummai-test`. Choose an EU region, and save the database password in a password manager.
2. **Images:** open **Storage** and create a bucket named exactly `caterer-assets`, set to **Public**. Don't add any policies: the app uploads with its server key, and without policies anonymous users can't write to the bucket.
3. **Logins:** in **Authentication → Sign In / Providers**, turn off **Allow new users to sign up**. Caterers are only added by hand (step 4).
4. Copy these values for step 2, from **Project Settings** and the **Connect** button:
   - `SUPABASE_URL`: the project URL
   - `SUPABASE_ANON_KEY`: the anon or publishable key
   - `SUPABASE_SERVICE_ROLE_KEY`: the service-role or secret key

## 2. Railway

1. Create a project with **Deploy from GitHub repo** and pick this repository. Railway finds `railway.json` and the `Dockerfile`.
2. Under **Settings**, deploy from the `dev` branch, and keep **one replica**.
3. Right-click the service and choose **Attach volume**, mounted at `/data`. **Without it, every deploy erases the database.**
4. Under **Variables**, add:

   | Name | Value |
   |---|---|
   | `APP_ENV` | `staging` |
   | `DATABASE_URL` | `sqlite:////data/yummai.db` (four slashes) |
   | `SUPABASE_URL` | from step 1 |
   | `SUPABASE_ANON_KEY` | from step 1 |
   | `SUPABASE_SERVICE_ROLE_KEY` | from step 1 |
   | `SITE_CATERER` | the slug of the caterer whose site is at `/` (ADR 0008), e.g. `taam` |
   | `ANTHROPIC_API_KEY` | optional |
   | `RESEND_API_KEY` | optional, turns on new-order emails |
   | `EMAIL_FROM` | needed with the Resend key; a sender on a domain verified with Resend |
   | `PUBLIC_BASE_URL` | needed with the Resend key; the site's address, for the link in emails |

5. Under **Settings → Networking**, choose **Generate Domain**.

If a setting is missing, the app refuses to start and the deploy log names it (`Missing settings: ...`). That's on purpose.

## 3. Check it is alive

Open `https://<your-domain>/health`. It should show `{"status":"ok"}`.

## 4. Add a caterer

1. In Supabase, open **Authentication → Users → Add user**, enter the caterer's email and a password, and copy the user's ID.
2. The database is on the server, so run this there. Install the [Railway CLI](https://docs.railway.com/guides/cli), run `railway ssh` from the project, then:

   ```bash
   python -m scripts.create_caterer --slug my-caterer --name "שם העסק" --auth-user-id <the user ID>
   ```

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
- [ ] Take a backup, copy it off the server, and restore it once (below).
- [ ] Redeploy and confirm the data is still there, which proves the volume works.
- [ ] Resolve the decisions still open for launch: allergen disclaimer legal review (#8), VAT, portion defaults (#3), and platform domain (#20).

## Updating the live app

1. Take a backup (below).
2. Merge to the deployed branch. Railway rebuilds, new migration files run when the new version starts, and the app starts only if they succeed.

The site is down briefly during each deploy, because a volume attaches to one instance at a time.

## Backups

**Nothing backs the database up for you, and a lost volume loses every order.** Do this on a schedule, starting before the pilot. In `railway ssh`, run this while the app is running:

```bash
python -m scripts.backup_database /data/backups/yummai-<date>.db
```

Then copy the file off the server, because a backup on the same volume dies with it. To restore, stop the app, replace `/data/yummai.db` with the backup, delete any `yummai.db-wal` and `yummai.db-shm` beside it, and start the app.

The file holds customers' personal details, so store it somewhere private and never commit it. Images in Storage aren't included.

## Rolling back

- **Bad code:** in Railway, open **Deployments**, pick the last good one and choose **Redeploy**.
- **Bad migration:** a failed file changes nothing and the app won't start, so redeploy the last good version. One that succeeded but was wrong needs a corrective migration, or a restore from a backup, which loses anything newer than the backup.

## Limits to know about

- The database file and the rate limits both live on one server, so run **one** Railway instance. A restart resets the rate-limit counts.
- SQLite handles one write at a time. That suits a small number of caterers, but heavy traffic would need a move to a database server.
- New-order emails need a Resend account and a verified domain, and have not been tested with the real provider. Until then caterers check the dashboard. A failed email is logged and not retried (#13).
