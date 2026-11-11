"""Owner decisions on submitted quotations: one atomic, versioned, retry-safe transition."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import Field

from app.api.orders import Input, Store
from app.repositories.supabase_orders import MAX_BIGINT
from app.services.owner_auth import Owner, deny

router = APIRouter(prefix="/api/admin")
FIELDS = ("id", "status", "version", "decision_note", "decided_at")


class Decision(Input):
    decision: Literal["approved", "rejected"]
    # Bounded so the stored version + 1 always fits a 64-bit integer.
    expected_version: int = Field(ge=1, le=MAX_BIGINT - 1, strict=True)
    # Trimmed by Input; an empty note is stored as NULL.
    note: str = Field(default="", max_length=2000)


@router.post("/orders/{order_id}/decision")
def decide_order(order_id: int, body: Decision, _: Owner, store: Store, response: Response) -> dict:
    # Owner comes before Store: Auth is asked before any database work starts.
    response.headers["Cache-Control"] = "no-store"
    if not 0 < order_id <= MAX_BIGINT:
        raise deny(404, "ההזמנה לא נמצאה")
    decided, order = store.decide(order_id, body.decision, body.expected_version, body.note)
    if order is None:
        raise deny(404, "ההזמנה לא נמצאה")
    # Approved and rejected are final, so a row in exactly the state this request would have
    # produced can only be this request's earlier success.
    replay = (
        order["status"] == body.decision
        and order["version"] == body.expected_version + 1
        and (order["decision_note"] or "") == body.note
    )
    if not (decided or replay):
        raise deny(409, "ההזמנה כבר עודכנה או שאינה ממתינה לאישור. יש לטעון אותה מחדש.")
    return {key: order[key] for key in FIELDS}
