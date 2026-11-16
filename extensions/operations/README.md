# Optional catering operations extension

This review package preserves the employees, deliveries, payments, equipment and ingredient
work removed from MVP PR [#37](https://github.com/JonathanZouari/ai-catering-platform/pull/37).
It is intentionally outside the application's automatic migration directories. It adds no
tables, permissions or UI merely by merging this package.

**Depends on PR #37. Keep this follow-up as a draft until that baseline is merged and the
operations scope is accepted.** No hosted database has been changed by this package.

## Contents

- `database/migrations`: optional SQLite extension, applied after MVP migrations 0004/0005.
- `supabase/migrations`: optional Postgres extension, applied after the MVP owner-access migration.
- `repositories`: payment/inventory query helpers retained from the previous implementation.
- `tests`: 54 SQLite behavior tests and an isolated Postgres schema/RLS check.

The Postgres extension reuses core customer/order keys, protects ledger history, grants access
only to server-controlled owner claims and preserves existing operation rows when re-enabled.
Views use invoker security. Existing historical tables are never dropped by this package.

## Validation after the MVP baseline is available

From the repository root, with its backend environment and the same PGlite test dependency:

```powershell
$env:PYTHONPATH = "backend;."
python -m pytest extensions/operations/tests -q
node extensions/operations/tests/operations-postgres.mjs
```

The fixtures apply the optional SQLite SQL only to temporary test databases. The Postgres test
uses a disposable disk-backed database, stubs Auth/Storage, checks repeat installation and
preservation, and verifies that a forged profile claim cannot read employee rows.

Recorded validation: 54 SQLite tests passed; isolated Postgres installation, preservation,
owner access and denial checks passed. These are local checks, not hosted concurrency tests.

## Activation remains a separate decision

Once the scope is accepted, integrate the migration files into the application's migration
directories, integrate repositories, update schema expectations and build the corresponding
admin UI. Reconcile hosted migration history before deploying; never reset the hosted project.
The MVP UI intentionally does not expose these operations tables.

Original full implementation: commit `f34cb219efcb8f71007be9980cfdfa1c60a99036`.
