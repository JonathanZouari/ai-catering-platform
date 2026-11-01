import logging
from dataclasses import dataclass
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.email import Mailer
from app.core.tenancy import CatererScope
from app.models import Order
from app.repositories.caterers import get_own_caterer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str


def new_order_email(session: Session, scope: CatererScope, order: Order) -> Email | None:
    """The caterer's alert. No customer details or token: those stay behind the login."""
    caterer = get_own_caterer(session, scope)
    if not caterer.notification_email:
        return None
    lines = [
        f"התקבלה בקשה חדשה להצעת מחיר ב{caterer.name}.",
        "",
        f"תאריך האירוע: {order.event.event_date:%d.%m.%Y}",
        f"מספר סועדים: {order.event.adults + order.event.children}",
        f"סכום ההזמנה: ₪{order.total}",
    ]
    # From settings, never the request's Host header, which the sender controls.
    base_url = get_settings().public_base_url
    if base_url:
        lines += ["", f"לצפייה ולאישור: {base_url.rstrip('/')}/admin/"]
    return Email(caterer.notification_email, "בקשה חדשה ממתינה לאישור", "\n".join(lines))


def deliver(mailer: Mailer, email: Email, order_id: UUID) -> None:
    """Runs after the response. The order is saved and in the dashboard, so failure is logged."""
    try:
        mailer.send(email.to, email.subject, email.text)
    except httpx.HTTPError:
        logger.warning("New-order email failed for order %s", order_id)
