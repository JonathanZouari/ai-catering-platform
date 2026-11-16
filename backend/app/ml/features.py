"""Feature definitions shared by training and scoring, so both build the exact same inputs.

Input rows follow the `lead_training_data` view (supabase/migrations/20261116100000_leads.sql).
Only facts known when the lead arrived are features. Anything written later, or that reveals the
outcome, is forbidden.
"""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

import pandas as pd

LABEL = "is_won"
TIME_COLUMN = "created_at"

CATEGORICAL = ["source", "utm_medium", "event_type"]
NUMERIC = ["guests", "budget_estimate", "budget_per_guest", "lead_time_days"]
BOOLEAN = [
    "missing_event_date",
    "missing_budget",  # derived in build_features
    "has_email",
    "has_message",
    "consent_marketing",
]
FEATURES = CATEGORICAL + NUMERIC + BOOLEAN

# Never features: they leak the outcome, are written after the lead arrives, or are personal data.
FORBIDDEN = {
    "status", "lost_reason", "customer_id", "order_id", "conversion_probability",
    "prediction_label",
    "prediction_model_version", "predicted_at", "full_name", "phone", "email", "message", "id",
}  # fmt: skip

RAW_COLUMNS = [c for c in FEATURES if c != "missing_budget"]
UNKNOWN = "unknown"

if FORBIDDEN & set(FEATURES):  # pragma: no cover - guards future edits
    raise RuntimeError(f"forbidden feature(s): {sorted(FORBIDDEN & set(FEATURES))}")

_TRUE = {"true", "t", "1", "yes"}


def _to_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin(_TRUE)


def load_training_frame(path: str) -> pd.DataFrame:
    """Read a CSV export of `lead_training_data` (closed leads only) and check its columns."""
    df = pd.read_csv(path)
    missing = [c for c in [*RAW_COLUMNS, LABEL, TIME_COLUMN] if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing column(s) {missing}")
    df[TIME_COLUMN] = pd.to_datetime(df[TIME_COLUMN], utc=True)
    for col in [*BOOLEAN, LABEL]:
        if col in df.columns:
            df[col] = _to_bool(df[col])
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Raw view columns -> model inputs. Pure function of the row; same code path for training and
    scoring."""
    x = pd.DataFrame(index=df.index)
    for col in CATEGORICAL:
        x[col] = df[col].where(df[col].notna(), UNKNOWN).astype(str)
    for col in NUMERIC:
        x[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    x["missing_budget"] = x["budget_estimate"].isna()
    for col in BOOLEAN:
        x[col] = (x[col] if col in x else _to_bool(df[col])).astype(int)
    return x[FEATURES]


def lead_to_row(
    lead: Mapping[str, Any], event_type_name: str | None, created_at: datetime
) -> dict[str, Any]:
    """One `leads` row (+ the event type's name) -> the same columns the training view exposes."""
    event_date: date | None = lead.get("event_date")
    guests = lead.get("approx_guests")
    budget = lead.get("budget_estimate")
    return {
        "source": lead.get("source"),
        "utm_medium": lead.get("utm_medium"),
        "event_type": event_type_name,
        "guests": guests,
        "budget_estimate": budget,
        # integer division, like the view
        "budget_per_guest": budget // guests if budget is not None and guests else None,
        "lead_time_days": (event_date - created_at.date()).days if event_date else None,
        "missing_event_date": event_date is None,
        "has_email": lead.get("email") is not None,
        "has_message": lead.get("message") is not None,
        "consent_marketing": bool(lead.get("consent_marketing", False)),
    }
