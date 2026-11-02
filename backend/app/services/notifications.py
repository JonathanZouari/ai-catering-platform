"""Email content for order events (OPEN_DECISIONS #13): owner on a new submission, customer on
approval or rejection. Built inside the request (it needs the DB), sent afterwards in the
background by core.mailer, which never raises.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.mailer import Email
from app.models.orders import Order

FULFILLMENT = {"pickup": "איסוף עצמי", "delivery": "משלוח"}


def _money(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:,.2f} ₪"


def _local(moment: datetime) -> str:
    if moment.tzinfo is None:  # stored as UTC; SQLite hands it back naive
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(clock.BUSINESS_TZ).strftime("%d.%m.%Y %H:%M")


def order_submitted(db: Session, order_id: uuid.UUID) -> Email | None:
    settings = get_settings()
    order = db.get(Order, order_id)
    if order is None or not settings.owner_email:
        return None
    e, c = order.event, order.customer
    lines = "\n".join(
        f"- {i.snapshot_name}: {i.quantity.normalize():f} × {_money(i.snapshot_unit_price)}"
        f" = {_money(i.snapshot_line_total)}"
        for i in order.items
    )
    fee_note = f" (כולל משלוח {_money(order.delivery_fee)})" if order.delivery_fee else ""
    body = f"""הזמנה חדשה ממתינה לאישור.

לקוח: {c.full_name}, טלפון {c.phone or "—"}, אימייל {c.email or "—"}
אירוע: {e.event_type}, {e.event_date:%d.%m.%Y}, {e.adults} מבוגרים ו-{e.children} ילדים
צמחונים / טבעונים / הגבלות: {e.vegetarian_guests} / {e.vegan_guests} / {e.restricted_guests}
הערות תזונה: {e.dietary_notes or "—"}
{FULFILLMENT[order.fulfillment_type]}: {_local(order.requested_at)}
{f"כתובת: {order.delivery_address}, {order.delivery_city}" if order.delivery_address else ""}

{lines}
סה"כ כולל מע"מ: {_money(order.total)}{fee_note}

לאישור או דחייה: {settings.public_base_url}/admin/orders/
"""
    subject = f"הזמנה חדשה: {e.event_type}, {e.event_date:%d.%m.%Y}, {c.full_name}"
    return Email(settings.owner_email, subject, body, kind="order_submitted")


def order_decided(db: Session, order_id: uuid.UUID) -> Email | None:
    settings = get_settings()
    order = db.get(Order, order_id)
    if order is None or order.status not in ("approved", "rejected") or not order.customer.email:
        return None
    e = order.event
    approved = order.status == "approved"
    headline = "ההזמנה שלכם אושרה" if approved else "ההזמנה שלכם לא אושרה"
    note = f"\nהודעה מבעל העסק:\n{order.decision_note}\n" if order.decision_note else ""
    body = f"""{headline}.

אירוע: {e.event_type}, {e.event_date:%d.%m.%Y}
{FULFILLMENT[order.fulfillment_type]}: {_local(order.requested_at)}
סה"כ כולל מע"מ: {_money(order.total)}
{note}
לפרטי ההזמנה: {settings.public_base_url}/customer/order/?order={order.id}
"""
    subject = f"{headline}: {e.event_type}, {e.event_date:%d.%m.%Y}"
    return Email(order.customer.email, subject, body, kind="order_decided")
