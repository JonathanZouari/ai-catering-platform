"""Retired one-shot generator. Refuses to run so it cannot overwrite the reviewed migration.

The foundation migration was generated once from SQLite migrations 0001-0003 and then fixed by hand
(runner-owned transactions, text payload, TRUNCATE guards, lock modes, fail-closed checks). Change
supabase/migrations through new forward migrations. The MVP baseline and normalization
now replace the original bootstrap for new installations; existing data is preserved.
"""

import sys

sys.exit(
    "REFUSED: build_foundation.py is retired and writes nothing. "
    "Edit the foundation migration by hand or add a new migration."
)
