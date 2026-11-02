"""Plain-text email over SMTP (OPEN_DECISIONS #13). Best effort: never raises.

Called from FastAPI background tasks after the order change is committed, so a mail failure can't
undo or block an order. Logs carry only the email's kind: subjects and bodies hold customer PII.
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str
    kind: str = "email"  # safe to log, e.g. "order_submitted"


def _one_line(text: str) -> str:
    # Header values must not contain line breaks (header injection via customer text).
    return " ".join(text.split())


def send(email: Email) -> None:
    settings = get_settings()
    subject = _one_line(email.subject)
    if not (settings.smtp_host and settings.smtp_from and email.to):
        # warning, not info: in production this means the owner or customer was not notified
        log.warning("email not sent (SMTP or recipient not configured): %s", email.kind)
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = _one_line(email.to)
    msg["Subject"] = subject
    msg.set_content(email.body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        # The error type only: smtplib messages can include the recipient's address.
        log.error("email failed: %s (%s)", email.kind, type(exc).__name__)
