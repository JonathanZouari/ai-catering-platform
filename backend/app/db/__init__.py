import psycopg
from psycopg.rows import dict_row

from app.core.config import get_settings


def connect() -> psycopg.Connection:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see .env.example)")
    # autocommit: writes use an explicit `with db.transaction()`. prepare_threshold=None keeps
    # it safe behind Supabase's connection pooler.
    return psycopg.connect(url, row_factory=dict_row, autocommit=True, prepare_threshold=None)
