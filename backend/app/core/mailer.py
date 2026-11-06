"""Plain-text email (OPEN_DECISIONS #13). Best effort: never raises.

Sent through Brevo's HTTPS API when BREVO_API_KEY is set (Railway blocks outbound SMTP below its
Pro plan), else over SMTP (local). Called from FastAPI background tasks after the order change is
committed, so a mail failure can't undo or block an order. Logs carry only the email's kind:
subjects and bodies hold customer PII.
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


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
    to = _one_line(email.to)
    can_send = settings.brevo_api_key or settings.smtp_host
    if not (can_send and settings.smtp_from and to):
        # warning, not info: in production this means the owner or customer was not notified
        log.warning("email not sent (sender or recipient not configured): %s", email.kind)
        return
    if settings.brevo_api_key:
        _send_brevo(settings, to, subject, email)
    else:
        _send_smtp(settings, to, subject, email)


def _send_brevo(settings, to: str, subject: str, email: Email) -> None:
    payload = {
        "sender": {"email": settings.smtp_from, "name": "Yummai"},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": email.body,
    }
    try:
        response = httpx.post(
            BREVO_URL, json=payload, headers={"api-key": settings.brevo_api_key}, timeout=15
        )
    except httpx.HTTPError as exc:
        log.error("email failed: %s (%s)", email.kind, type(exc).__name__)
        return
    if response.is_error:
        # The status only: Brevo's error body can echo the recipient's address.
        log.error("email failed: %s (HTTP %s)", email.kind, response.status_code)


def _send_smtp(settings, to: str, subject: str, email: Email) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
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
