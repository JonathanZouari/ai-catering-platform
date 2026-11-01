from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_orders import ADMIN, EVENT_DAY, Shop, customer_details

from app.core.config import Settings, get_settings
from app.core.headers import content_security_policy
from app.main import app, create_app
from scripts import ai_check


@pytest.fixture
def shop(client, make_tenant):
    return Shop(client, make_tenant("caterer-a"))


@pytest.fixture
def other_shop(client, make_tenant):
    return Shop(client, make_tenant("caterer-b"))


@pytest.fixture
def deployed(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "database_url", settings.database_url or "postgresql://x/y")
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "anon")
    monkeypatch.setattr(settings, "supabase_service_role_key", "service")
    return settings


# Rate limits


def test_order_creation_is_limited_per_address(shop):
    details = customer_details(shop.slot["id"])
    for _ in range(20):
        assert shop.create(details).status_code == 201

    response = shop.create(details)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert "נסו שוב" in response.json()["error"]["message"]


def test_public_reads_are_not_limited(shop):
    for _ in range(150):
        assert shop.client.get(f"/api/c/{shop.tenant.slug}").status_code == 200


def test_order_writes_are_limited(shop):
    order = shop.order()
    url = f"{order.url}/items/{shop.meat['id']}"
    body = {"quantity": "1", "version": order.data["version"]}
    codes = [
        order.client.put(url, json=body, headers=order.headers).status_code for _ in range(125)
    ]
    assert codes[-1] == 429
    assert order.client.get(order.url, headers=order.headers).status_code == 200


def test_forwarded_header_is_ignored_in_development(shop):
    details = customer_details(shop.slot["id"])
    for number in range(20):
        headers = {"X-Forwarded-For": f"10.0.0.{number}"}
        assert (
            shop.client.post(
                f"/api/c/{shop.tenant.slug}/orders", json=details, headers=headers
            ).status_code
            == 201
        )
    assert shop.create(details).status_code == 429


def test_deployed_limit_uses_the_address_railway_appended(shop, deployed):
    details = customer_details(shop.slot["id"])
    url = f"/api/c/{shop.tenant.slug}/orders"
    # A client changing the part it controls still counts as the same address.
    for number in range(20):
        headers = {"X-Forwarded-For": f"10.0.0.{number}, 203.0.113.9"}
        assert shop.client.post(url, json=details, headers=headers).status_code == 201
    spoofed = {"X-Forwarded-For": "1.2.3.4, 203.0.113.9"}
    assert shop.client.post(url, json=details, headers=spoofed).status_code == 429
    other = {"X-Forwarded-For": "203.0.113.10"}
    assert shop.client.post(url, json=details, headers=other).status_code == 201


def test_a_duplicate_forwarded_header_does_not_change_the_address(shop, deployed):
    details = customer_details(shop.slot["id"])
    url = f"/api/c/{shop.tenant.slug}/orders"
    for number in range(20):
        headers = [("X-Forwarded-For", f"10.0.0.{number}"), ("X-Forwarded-For", "203.0.113.9")]
        assert shop.client.post(url, json=details, headers=headers).status_code == 201
    headers = [("X-Forwarded-For", "1.2.3.4"), ("X-Forwarded-For", "203.0.113.9")]
    assert shop.client.post(url, json=details, headers=headers).status_code == 429


# Security headers


@pytest.mark.parametrize("path", ["/health", "/admin/", "/c/any/", "/api/allergens"])
def test_security_headers_are_on_every_response(client, path):
    headers = client.get(path).headers
    policy = headers["Content-Security-Policy"]
    assert "script-src 'self'" in policy
    assert "default-src 'none'" in policy
    assert "unsafe" not in policy
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"


@pytest.mark.parametrize("path", ["/c/any/", "/js/customer/main.js", "/css/base.css"])
def test_browsers_recheck_frontend_files(client, path):
    assert client.get(path).headers["Cache-Control"] == "no-cache"


def test_policy_allows_only_the_project_supabase():
    policy = content_security_policy("https://project.supabase.co/")
    assert "img-src 'self' https://project.supabase.co;" in policy
    assert "connect-src 'self' https://project.supabase.co;" in policy


def test_hsts_only_when_deployed(client, monkeypatch):
    assert "Strict-Transport-Security" not in client.get("/health").headers
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert "Strict-Transport-Security" in client.get("/health").headers


# Production settings


def test_health_does_not_show_the_environment(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_api_docs_are_off_when_deployed(deployed):
    closed = TestClient(create_app())
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert closed.get(path).status_code in (404, 405)
    assert closed.get("/health").status_code == 200


def test_server_refuses_to_start_with_missing_settings(deployed, monkeypatch):
    monkeypatch.setattr(deployed, "supabase_service_role_key", None)
    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
        create_app()


def test_a_misspelled_environment_is_refused():
    with pytest.raises(ValidationError):
        Settings(app_env="prod", _env_file=None)


def test_development_starts_without_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "supabase_url", None)
    assert create_app()


def test_unexpected_error_returns_a_plain_hebrew_500(client, monkeypatch):
    def explode(*_):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("app.api.public.get_active_caterer_by_slug", explode)
    response = TestClient(app, raise_server_exceptions=False).get("/api/c/anything")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "secret" not in response.text
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert error["message"].startswith("משהו")


# Quantity rules


def rules(shop):
    response = shop.client.get(f"{ADMIN}/quantity-rules", headers=shop.headers)
    assert response.status_code == 200
    return {rule["category_type"]: rule for rule in response.json()}


def put_rule(shop, adult="2.50", child="1.25", kind="main"):
    url = f"{ADMIN}/quantity-rules/{kind}"
    body = {"portions_per_adult": adult, "portions_per_child": child}
    return shop.client.put(url, json=body, headers=shop.headers)


def test_rules_start_from_the_platform_defaults(shop):
    main = rules(shop)["main"]
    assert main["is_default"] is True
    assert Decimal(main["portions_per_adult"]) == 1


def test_caterer_rule_drives_recommendations(shop):
    assert put_rule(shop, "2", "0").status_code == 200
    order = shop.order()

    line = order.add(shop.meat)["lines"][0]

    # 20 adults x 2 portions, 80% of guests eligible for meat, 10 per tray.
    assert Decimal(line["recommended_quantity"]) == 4
    assert rules(shop)["main"]["is_default"] is False


def test_saving_twice_updates_the_same_rule(shop):
    put_rule(shop, "2")
    put_rule(shop, "3")
    assert Decimal(rules(shop)["main"]["portions_per_adult"]) == 3


def test_revert_restores_the_default(shop):
    put_rule(shop)
    url = f"{ADMIN}/quantity-rules/main"

    assert shop.client.delete(url, headers=shop.headers).status_code == 200
    assert shop.client.delete(url, headers=shop.headers).status_code == 200

    assert rules(shop)["main"]["is_default"] is True


def test_one_caterers_rule_does_not_reach_another(shop, other_shop):
    put_rule(shop, "9")
    assert rules(other_shop)["main"]["is_default"] is True
    other_shop.client.delete(f"{ADMIN}/quantity-rules/main", headers=other_shop.headers)
    assert rules(shop)["main"]["is_default"] is False


@pytest.mark.parametrize("adult", ["-1", "1000", "abc"])
def test_rule_values_are_checked(shop, adult):
    assert put_rule(shop, adult).status_code == 422


def test_rule_body_can_not_name_a_caterer(shop):
    url = f"{ADMIN}/quantity-rules/main"
    body = {"portions_per_adult": "1", "portions_per_child": "1", "caterer_id": str(shop.tenant.id)}
    assert shop.client.put(url, json=body, headers=shop.headers).status_code == 422


def test_rules_need_a_login(client):
    assert client.get(f"{ADMIN}/quantity-rules").status_code == 401


def test_event_day_helper_stays_in_the_future():
    assert EVENT_DAY.year > 2030


# Live AI check, with a fake client: this proves the script, not the model.


def test_ai_check_runs_tools_and_counts_tokens():
    usage = SimpleNamespace(input_tokens=100, output_tokens=10)
    tool = SimpleNamespace(type="tool_use", id="1", name="get_dish_details", input={})
    text_block = SimpleNamespace(type="text", text="שלום")
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[tool], usage=usage),
        SimpleNamespace(stop_reason="end_turn", content=[text_block], usage=usage),
    ]
    llm = SimpleNamespace(create=lambda *_: responses.pop(0))

    reply, tokens_in, tokens_out = ai_check.converse(llm, "שאלה")

    assert (reply, tokens_in, tokens_out) == ("שלום", 200, 20)
    assert ai_check.cost(1_000_000, 0) == ai_check.INPUT_PRICE
