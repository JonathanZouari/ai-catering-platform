from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Connection, RowMapping, text

# lead_days: days between the inquiry and the event, an input of the purchase model.
LEAD_COLUMNS = (
    "id, full_name, phone, email, event_type, event_date, guests, budget_per_guest, "
    "source, is_returning, status, created_at, "
    "event_date - CAST(created_at AS date) AS lead_days"
)


def list_leads(conn: Connection) -> Sequence[RowMapping]:
    sql = f"SELECT {LEAD_COLUMNS} FROM leads ORDER BY created_at DESC, id"  # noqa: S608
    return conn.execute(text(sql)).mappings().all()


def update_status(conn: Connection, lead_id: UUID, status: str) -> RowMapping | None:
    """Set the status and return the updated lead, or None when the lead does not exist."""
    sql = (
        "UPDATE leads SET status = CAST(:status AS lead_status), updated_at = now() "  # noqa: S608
        f"WHERE id = :id RETURNING {LEAD_COLUMNS}"
    )
    return conn.execute(text(sql), {"id": lead_id, "status": status}).mappings().first()
