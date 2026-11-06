import smtplib

import httpx
import pytest

from app.core import config, mailer
from app.core.mailer import Email


@pytest.fixture(autouse=True)
def no_brevo(monkeypatch):
    # a local .env may hold a key; each test opts in explicitly
    monkeypatch.setattr(config.get_settings(), "brevo_api_key", None)


def test_skips_without_smtp(monkeypatch, caplog):
    monkeypatch.setattr(config.get_settings(), "smtp_host", None)
    called = []
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: called.append(a))
    with caplog.at_level("WARNING"):
        mailer.send(Email("dana@example.com", "הזמנה של דנה לוי", "גוף", kind="order_submitted"))
    assert called == [] and "email not sent" in caplog.text and "order_submitted" in caplog.text
    # no addresses, names or other subject text in logs (customer PII)
    assert "dana@example.com" not in caplog.text and "דנה" not in caplog.text


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout):
        assert (host, timeout) == ("smtp.example.com", 15)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_sends_and_strips_header_line_breaks(monkeypatch):
    settings = config.get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "orders@example.com")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    mailer.send(Email("dana@example.com", "שלום\r\nBcc: evil@example.com", "גוף"))
    assert len(FakeSMTP.sent) == 1
    msg = FakeSMTP.sent[0]
    assert msg["Subject"] == "שלום Bcc: evil@example.com" and msg["Bcc"] is None


def test_smtp_failure_never_raises(monkeypatch, caplog):
    settings = config.get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "orders@example.com")

    def boom(*a, **k):
        raise smtplib.SMTPRecipientsRefused({"dana@example.com": (550, b"no such user")})

    monkeypatch.setattr(smtplib, "SMTP", boom)
    mailer.send(Email("dana@example.com", "נושא", "גוף", kind="order_decided"))  # not raised
    assert "SMTPRecipientsRefused" in caplog.text and "dana@example.com" not in caplog.text


def test_brevo_api_when_key_set(monkeypatch):
    settings = config.get_settings()
    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(settings, "smtp_host", None)  # SMTP isn't needed with the API
    monkeypatch.setattr(settings, "smtp_from", "orders@example.com")
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return httpx.Response(201, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: pytest.fail("SMTP used"))
    mailer.send(Email("dana@example.com", "שלום\r\nBcc: evil@example.com", "גוף"))
    [(url, payload, headers)] = calls
    assert url == mailer.BREVO_URL and headers == {"api-key": "test-key"}
    assert payload == {
        "sender": {"email": "orders@example.com", "name": "Yummai"},
        "to": [{"email": "dana@example.com"}],
        "subject": "שלום Bcc: evil@example.com",
        "textContent": "גוף",
    }


def test_brevo_failure_never_raises(monkeypatch, caplog):
    settings = config.get_settings()
    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(settings, "smtp_from", "orders@example.com")

    def rejected(url, **kw):
        body = {"message": "invalid recipient dana@example.com"}
        return httpx.Response(400, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", rejected)
    mailer.send(Email("dana@example.com", "נושא", "גוף", kind="order_decided"))  # not raised
    assert "order_decided (HTTP 400)" in caplog.text and "dana@example.com" not in caplog.text

    def down(url, **kw):
        raise httpx.ConnectError("unreachable")

    monkeypatch.setattr(httpx, "post", down)
    mailer.send(Email("dana@example.com", "נושא", "גוף", kind="order_submitted"))
    assert "order_submitted (ConnectError)" in caplog.text
