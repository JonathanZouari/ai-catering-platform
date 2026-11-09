from typing import Protocol

import httpx

from app.core.config import get_settings

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10


class Mailer(Protocol):
    def send(self, to: str, subject: str, text: str) -> None: ...


class ResendMailer:
    def __init__(self, api_key: str, sender: str) -> None:
        self.api_key = api_key
        self.sender = sender

    def send(self, to: str, subject: str, text: str) -> None:
        response = httpx.post(
            RESEND_URL,
            json={"from": self.sender, "to": [to], "subject": subject, "text": text},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()


def get_mailer() -> Mailer | None:
    """None until a key and sender are set, so local runs and tests never send real email."""
    settings = get_settings()
    if not settings.resend_api_key or not settings.email_from:
        return None
    return ResendMailer(settings.resend_api_key, settings.email_from)
