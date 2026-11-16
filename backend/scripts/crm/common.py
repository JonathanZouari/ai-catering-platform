"""Shared constants and DB access for the CRM lead scripts (local SQLite stand-in)."""

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "crm_dev.sqlite"
MODEL_PATH = DATA_DIR / "lead_model.joblib"

NUMERIC = [
    "days_until_event",
    "guest_count",
    "dishes_selected",
    "quote_submitted",
    "ai_chat_messages",
    "visits_last_7d",
    "days_since_last_activity",
    "has_phone",
    "has_email",
]
CATEGORICAL = ["source", "event_type"]

# SQLite mirror of database/migrations/0001_crm_leads.sql (enums become TEXT).
SCHEMA = """
create table if not exists leads (
    id integer primary key autoincrement,
    source text not null,
    event_type text not null,
    days_until_event integer not null,
    guest_count integer not null,
    dishes_selected integer not null,
    quote_submitted integer not null,
    ai_chat_messages integer not null,
    visits_last_7d integer not null,
    days_since_last_activity integer not null,
    has_phone integer not null,
    has_email integer not null,
    stage text not null,
    is_buyer integer,
    score real
)
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)
