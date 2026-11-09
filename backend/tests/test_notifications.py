import logging

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.core.email import ResendMailer, get_mailer
from app.main import app
from tests.test_orders import ADMIN, Shop

ALERT_ADDRESS = "owner@example.com"


class FakeMailer:
    def __init__(self):
        self.sent = []
        self.error = None

    def send(self, to, subject, text):
        if self.error:
            raise self.error
        self.sent.append((to, subject, text))


@pytest.fixture
def mailer(client):
    fake = FakeMailer()
    app.dependency_overrides[get_mailer] = lambda: fake
    return fake


@pytest.fixture
def shop(client, make_tenant):
    shop = Shop(client, make_tenant("caterer-a"))
    shop.patch("profile", {"notification_email": ALERT_ADDRESS})
    return shop


def filled_order(shop):
    order = shop.order()
    order.add(shop.meat)
    return order


def test_submit_emails_the_caterer_once_without_customer_details(shop, mailer):
    order = filled_order(shop)
    assert order.submit().status_code == 200

    [(to, subject, text)] = mailer.sent
    assert to == ALERT_ADDRESS
    assert subject == "בקשה חדשה ממתינה לאישור"
    assert "07.01.2031" in text
    assert "מספר סועדים: 25" in text
    assert "₪200.00" in text
    for private in ("דנה לוי", "050-1234567", order.token, order.data["id"]):
        assert private not in text


def test_submitting_twice_sends_one_email(shop, mailer):
    order = filled_order(shop)
    assert order.submit().status_code == 200
    assert order.submit().status_code == 409
    assert len(mailer.sent) == 1


def test_a_failed_submit_sends_nothing(shop, mailer):
    assert shop.order().submit().status_code == 422
    assert mailer.sent == []


def test_no_address_means_no_email(shop, mailer):
    shop.patch("profile", {"notification_email": None})
    assert filled_order(shop).submit().status_code == 200
    assert mailer.sent == []


def test_no_provider_means_no_email_and_submit_works(shop):
    assert filled_order(shop).submit().status_code == 200


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectTimeout("slow"), httpx.ConnectError("down")],
    ids=["timeout", "refused"],
)
def test_a_provider_failure_still_saves_the_order(shop, mailer, error, caplog):
    mailer.error = error
    order = filled_order(shop)
    with caplog.at_level(logging.WARNING):
        response = order.submit()
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"
    assert order.data["id"] in caplog.text
    assert order.token not in caplog.text


def test_customers_never_see_the_alert_address(client, shop):
    assert ALERT_ADDRESS not in client.get(f"/api/c/{shop.tenant.slug}").text


def test_a_caterer_sees_only_their_own_address(client, shop, make_tenant):
    other = make_tenant("caterer-b")
    response = client.get(f"{ADMIN}/profile", headers=other.headers)
    assert response.json()["notification_email"] is None


def test_alert_goes_to_the_order_caterer_only(client, shop, make_tenant, mailer):
    other = make_tenant("caterer-b")
    body = {"notification_email": "b@example.com"}
    client.patch(f"{ADMIN}/profile", json=body, headers=other.headers)
    assert filled_order(shop).submit().status_code == 200
    assert [sent[0] for sent in mailer.sent] == [ALERT_ADDRESS]


@pytest.mark.parametrize("value", ["not-an-address", "a@b", "a b@example.com", "a@example.com\nx"])
def test_bad_addresses_are_rejected(client, shop, value):
    body = {"notification_email": value}
    response = client.patch(f"{ADMIN}/profile", json=body, headers=shop.headers)
    assert response.status_code == 422


def test_mailer_is_off_without_key_and_sender(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "key")
    monkeypatch.delenv("EMAIL_FROM", raising=False)
    get_settings.cache_clear()
    try:
        assert get_mailer() is None
        monkeypatch.setenv("EMAIL_FROM", "Yummai <orders@example.com>")
        get_settings.cache_clear()
        assert isinstance(get_mailer(), ResendMailer)
    finally:
        get_settings.cache_clear()


def test_deployment_with_a_key_needs_sender_and_address():
    settings = Settings(
        _env_file=None,
        app_env="staging",
        database_url="x",
        supabase_url="x",
        supabase_anon_key="x",
        supabase_service_role_key="x",
        resend_api_key="x",
    )
    with pytest.raises(RuntimeError, match="EMAIL_FROM, PUBLIC_BASE_URL"):
        settings.require_deployment_settings()


def test_resend_receives_the_message(monkeypatch):
    seen = {}

    def fake_post(url, **fields):
        seen.update(fields, url=url)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    ResendMailer("key", "orders@example.com").send("a@example.com", "נושא", "גוף")
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"]["Authorization"] == "Bearer key"
    assert seen["json"]["to"] == ["a@example.com"]
    assert seen["json"]["text"] == "גוף"
