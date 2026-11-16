from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import Connection

from app.repositories import leads
from app.services.lead_scoring import purchase_probability

OPEN_STATUSES = ("new", "contacted", "quoted")


def _with_probability(row: Mapping) -> dict:
    is_open = row["status"] in OPEN_STATUSES
    return {**row, "purchase_probability": purchase_probability(row) if is_open else None}


def list_leads(conn: Connection) -> list[dict]:
    """Open leads first, most likely buyer on top; closed leads after them, newest first."""
    scored = [_with_probability(row) for row in leads.list_leads(conn)]
    # The sort is stable, so closed leads keep the repository's newest-first order.
    return sorted(
        scored,
        key=lambda lead: (
            lead["purchase_probability"] is None,
            -(lead["purchase_probability"] or 0.0),
        ),
    )


def set_status(conn: Connection, lead_id: UUID, status: str) -> dict | None:
    """Change a lead's status. Returns the updated lead, or None when it does not exist."""
    row = leads.update_status(conn, lead_id, status)
    conn.commit()
    return _with_probability(row) if row is not None else None
