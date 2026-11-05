# Scoped CLI access and migration reconciliation

Completed 5 November 2026 for `yumm.ai` (`vbechymjcdlztoissafv`, Frankfurt), using Supabase CLI 3.0.0.

## Connection

The user approved a seven-day project-scoped token, expiring **12 November 2026**. Permissions are Project Settings read, Projects list read, Connection Pooling read and Database read-write. No branch, API key secret, organization administration or billing permissions were granted. Linking succeeded; optional service-version checks were skipped because secret API-key access was intentionally omitted.

The token is encrypted using Windows DPAPI for the current Windows user at `supabase/.temp/cli-token.dpapi`, which is git-ignored. The temporary plaintext transfer file was removed. The helper loads it only into the child command environment and restores the previous environment afterward. It does not configure an unrestricted account-wide login. A fresh PowerShell process successfully used the saved connection.

From the repository root:

```powershell
./scripts/cloud-cli.ps1 -CliArguments @('migration', 'list', '--remote=vbechymjcdlztoissafv')
./scripts/cloud-cli.ps1 -CliArguments @('db', 'push', '--remote=vbechymjcdlztoissafv', '--dry-run', '--skip-vault')
```

The helper defaults to the existing CLI installation under the user's temporary directory; pass `-CliPath` if that binary is moved. The encrypted token is machine/user-specific and will require renewal after expiry. It is not included in the repository.

## History reconciliation

Before repair, CLI migration history was absent, while the private deployment manifest proved these four migrations had already run. All four local file SHA-256 hashes, with normalized line endings, exactly matched that manifest.

| Version | Migration | Final state |
| --- | --- | --- |
| 20261105182903 | mvp_core_baseline | Local = remote |
| 20261105183115 | mvp_ai_availability | Local = remote |
| 20261105184337 | catalog_normalization | Local = remote |
| 20261105185136 | mvp_owner_access | Local = remote |

Only `migration repair --status applied` was executed for these versions. No migration SQL was replayed, no reset was performed, and no historical business tables were removed. The baseline represents the current managed migration sequence; earlier manual installation evidence remains in the private snapshots and original implementation history.

The final `db push --dry-run --skip-vault` returned `upToDate: true`, with empty migrations, seeds and roles. This checks migration bookkeeping, not the absence of every possible manual schema change.

## Data verification

A private local snapshot was taken before repair. After repair all rows in customers, addresses, events, orders, order_items, order_submissions, dishes and delivery_zones were exactly equal to that snapshot. Counts remained 6 customers, 3 addresses, 6 events, **6 orders**, 8 order items, 3 submissions, 17 dishes and 6 delivery zones.

The order aggregate fingerprint stayed identical and the total remained **162700 minor currency units**. Existing receipt/replay tests for orders 8 and 10 passed; wrong tokens were still rejected. No new test order was created during reconciliation.

Claude Code independently reviewed the migration-history procedure. The previously verified application restart checks remain documented in [cloud upgrade verification](CLOUD_UPGRADE_VERIFICATION.md).

Reference: [Supabase CLI migration repair](https://supabase.com/docs/reference/cli/supabase-migration-repair), [scoped personal access tokens](https://supabase.com/docs/guides/platform/personal-access-tokens).
