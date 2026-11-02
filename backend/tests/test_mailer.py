import smtplib

from app.core import config, mailer
from app.core.mailer import Email


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
