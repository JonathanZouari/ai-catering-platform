"""Retired one-shot generator. Refuses to run so it cannot overwrite the reviewed migration.

The foundation migration was generated once from SQLite migrations 0001-0003 and then fixed by hand
(runner-owned transactions, text payload, TRUNCATE guards, lock modes, fail-closed checks). Change
supabase/migrations/20261105103436_catering_postgres_foundation.sql directly while it is unapplied,
and add a new migration once it has been applied anywhere.
"""

import sys

sys.exit(
    "REFUSED: build_foundation.py is retired and writes nothing. "
    "Edit the foundation migration by hand or add a new migration."
)
