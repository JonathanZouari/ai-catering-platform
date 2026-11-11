"""Cloud order backend against a fake PostgREST. No credentials and no network.

SQL atomicity, grants and denial run in supabase/tests/catalog-normalization.mjs.
"""

import copy
import functools
import hashlib
import json
import logging
import re
import secrets
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import app
from app.repositories import supabase_orders
from tests.test_customer_orders import payload

SECRET = "sb_secret_unit-test-value"  # noqa: S105 - not a real credential
MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
STATUSES = [{"name": "חלב", "status": "contains"}, {"name": "דגים", "status": "unknown"}]
# metadata is what customer_catalog projects from the normalized tables; it holds no price.
CATALOG = {
    "dishes": [
        {
            "id": "d1",
            "metadata": {"id": "d1", "name": "חומוס", "unit": "tray", "allergenStatuses": STATUSES},
            "price_minor": 8500,
            "step_milli": 1000,
        },
        {
            "id": "d5",
            "metadata": {"id": "d5", "name": "עוף", "unit": "kg", "allergenStatuses": STATUSES},
            "price_minor": 7400,
            "step_milli": 500,
        },
    ],
    "zones": [{"city": "תל אביב-יפו", "fee_minor": 6000}],
}


class FakeCloud:
    """Minimal stand-in for the three RPCs. `fail` replaces every response when set."""

    def __init__(self):
        self.requests = []
        self.fail = None
        self.submit_outcome = None
        self.lose_next_submit_response = False
        self.submissions = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail:
            return self.fail(request)
        name = request.url.path.rsplit("/", 1)[-1]
        body = json.loads(request.content or b"{}")
        if name == "customer_catalog":
            return httpx.Response(200, json=CATALOG)
        if name == "customer_order_read":
            saved = self.submissions.get(body["p_token_hash"])
            if saved and body["p_order_id"] in (None, saved["order"]["id"]):
                return httpx.Response(200, json=saved)
            return httpx.Response(200, content=b"null")  # PostgREST's body for a NULL scalar
        assert name == "customer_order_submit"
        if self.submit_outcome:
            return httpx.Response(200, json=self.submit_outcome(body))
        saved = self._saved(body)
        self.submissions[body["p_token_hash"]] = saved
        if self.lose_next_submit_response:
            self.lose_next_submit_response = False
            raise httpx.ReadTimeout("committed, but the response was lost", request=request)
        return httpx.Response(200, json={"outcome": "created", "saved": saved})

    @staticmethod
    def _saved(body):
        draft = body["p_order"]
        return {
            "order": {
                "id": 41,
                "version": 1,
                "status": "pending_approval",
                "decision_note": None,
                "submitted_at": "2026-11-05T10:00:00Z",
                "subtotal_minor": draft["subtotal_minor"],
                "delivery_fee_minor": draft["delivery_fee_minor"],
                "total_minor": draft["total_minor"],
            },
            "payload": body["p_payload"],
            "items": draft["items"],
        }

    @property
    def writes(self):
        return [r for r in self.requests if r.url.path.endswith("customer_order_submit")]


@pytest.fixture
def cloud(monkeypatch):
    monkeypatch.setenv("ORDER_DATABASE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    get_settings.cache_clear()
    fake = FakeCloud()
    monkeypatch.setattr(
        supabase_orders,
        "new_client",
        functools.partial(supabase_orders.new_client, transport=httpx.MockTransport(fake)),
    )
    return fake


def token_headers():
    return {"X-Order-Token": secrets.token_hex(32)}


# ---- Choosing the backend ----


def test_default_backend_is_sqlite(isolated_settings, monkeypatch):
    monkeypatch.delenv("ORDER_DATABASE_BACKEND")
    assert Settings(_env_file=None).order_database_backend == "sqlite"
    get_settings.cache_clear()
    with TestClient(app) as client:
        assert client.get("/health").json()["database"]["engine"] == "sqlite"
    assert isolated_settings.exists()


def test_credentials_alone_do_not_select_the_cloud(isolated_settings, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    get_settings.cache_clear()
    with TestClient(app) as client:
        assert client.get("/api/catalog").status_code == 200
    assert isolated_settings.exists()


@pytest.mark.parametrize(
    "env",
    [
        {"ORDER_DATABASE_BACKEND": "postgres"},
        {"ORDER_DATABASE_BACKEND": "supabase"},
        {"ORDER_DATABASE_BACKEND": "supabase", "SUPABASE_URL": "https://example.supabase.co"},
        {
            "ORDER_DATABASE_BACKEND": "supabase",
            "SUPABASE_URL": "http://example.supabase.co",
            "SUPABASE_SECRET_KEY": SECRET,
        },
        {
            "ORDER_DATABASE_BACKEND": "supabase",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SECRET_KEY": "sb_publishable_wrong-kind",
        },
    ],
)
def test_bad_configuration_stops_startup_without_printing_the_key(monkeypatch, env):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError) as failure:
        Settings(_env_file=None)
    assert "sb_secret_unit" not in str(failure.value)
    assert "sb_publishable_wrong" not in str(failure.value)


def test_cloud_mode_uses_only_rpcs_and_never_opens_sqlite(cloud, isolated_settings):
    with TestClient(app) as client:
        assert client.get("/health").json()["database"] == {"engine": "supabase"}
        assert client.get("/api/catalog").status_code == 200
        response = client.post("/api/orders", json=payload(True), headers=token_headers())
        assert response.status_code == 201, response.text
    assert not isolated_settings.exists()
    assert cloud.requests
    assert {r.url.host for r in cloud.requests} == {"example.supabase.co"}
    assert all(r.url.path.startswith("/rest/v1/rpc/customer_") for r in cloud.requests)


# ---- Same API shape ----


def test_catalog_has_the_public_shape(cloud):
    with TestClient(app) as client:
        body = client.get("/api/catalog").json()
    assert body["zones"] == [{"city": "תל אביב-יפו", "fee": 60.0}]
    assert body["dishes"][1] == {
        "id": "d5",
        "name": "עוף",
        "unit": "kg",
        "allergenStatuses": STATUSES,
        "price": 74.0,
        "step": 0.5,
    }


def test_catalog_keys_match_sqlite(cloud, monkeypatch, isolated_settings):
    with TestClient(app) as client:
        from_cloud = client.get("/api/catalog").json()
    monkeypatch.setenv("ORDER_DATABASE_BACKEND", "sqlite")
    get_settings.cache_clear()
    with TestClient(app) as client:
        from_sqlite = client.get("/api/catalog").json()
    assert from_cloud.keys() == from_sqlite.keys()
    assert from_cloud["zones"][0].keys() == from_sqlite["zones"][0].keys()
    assert from_cloud["dishes"][0].keys() <= from_sqlite["dishes"][0].keys()


@pytest.mark.parametrize("delivery", [False, True])
def test_submit_read_retry_and_privacy_match_the_sqlite_contract(cloud, delivery):
    headers = token_headers()
    body = payload(delivery)
    with TestClient(app) as client:
        created = client.post("/api/orders", json=body, headers=headers)
        assert created.status_code == 201, created.text
        assert created.headers["cache-control"] == "no-store"
        saved = created.json()
        assert saved["status"] == "pending_approval"
        assert saved["event"] == body["event"]
        assert saved["snapshot"]["total"] == body["expected_total_minor"] / 100
        retry = client.post("/api/orders", json=body, headers=headers)
        assert retry.status_code == 200
        assert retry.json() == saved
        assert len(cloud.writes) == 1
        assert client.get("/api/orders/receipt", headers=headers).json() == saved
        assert client.get(f"/api/orders/{saved['id']}", headers=headers).json() == saved
        other = token_headers()
        assert client.get("/api/orders/receipt", headers=other).status_code == 404
        assert client.get(f"/api/orders/{saved['id']}", headers=other).status_code == 404
        assert client.get(f"/api/orders/{10**30}", headers=headers).status_code == 404
        changed = copy.deepcopy(body)
        changed["contact"]["name"] = "different"
        assert client.post("/api/orders", json=changed, headers=headers).status_code == 409
    assert len(cloud.writes) == 1


# ---- Atomicity and server-side secrets ----


def test_submit_is_one_write_call_carrying_server_prices(cloud):
    headers = token_headers()
    body = payload(True)
    with TestClient(app) as client:
        assert client.post("/api/orders", json=body, headers=headers).status_code == 201
    assert len(cloud.writes) == 1
    params = json.loads(cloud.writes[0].content)
    assert set(params) == {"p_token_hash", "p_payload", "p_order"}
    draft = params["p_order"]
    assert (draft["subtotal_minor"], draft["delivery_fee_minor"], draft["total_minor"]) == (
        28100,
        6000,
        34100,
    )
    assert {i["dish_id"]: i["line_total_minor"] for i in draft["items"]} == {
        "d1": 17000,
        "d5": 11100,
    }


def test_token_is_hashed_here_and_key_is_only_in_the_apikey_header(cloud):
    headers = token_headers()
    token = headers["X-Order-Token"]
    with TestClient(app) as client:
        assert client.post("/api/orders", json=payload(), headers=headers).status_code == 201
        assert client.get("/api/orders/receipt", headers=headers).status_code == 200
    for request in cloud.requests:
        assert token.encode() not in request.content
        assert token not in str(request.url)
        assert token not in request.headers.values()
        assert request.headers["apikey"] == SECRET
        assert SECRET.encode() not in request.content
        assert "authorization" not in request.headers
    sent = json.loads(cloud.writes[0].content)
    assert sent["p_token_hash"] == hashlib.sha256(token.encode()).hexdigest()


def test_secret_key_is_never_returned_to_the_browser(cloud):
    with TestClient(app) as client:
        for path in ("/api/cloud-config", "/health", "/api/catalog"):
            assert SECRET not in client.get(path).text


def test_rejected_input_makes_no_write(cloud):
    with TestClient(app) as client:
        for mutate in (
            lambda p: p.update(expected_total_minor=1),
            lambda p: p.update(items={"missing": 1}),
            lambda p: p.update(items={"d5": 0.7}),
            lambda p: p["event"].update(date="2000-01-01"),
            lambda p: p["contact"].update(name="nul\x00byte"),
            lambda p: p["contact"].update(name="\ud800"),
        ):
            body = payload()
            mutate(body)
            response = client.post(
                "/api/orders", content=json.dumps(body, ensure_ascii=True),
                headers=token_headers() | {"Content-Type": "application/json"},
            )
            assert response.status_code in (409, 422), body
    assert cloud.writes == []


# ---- Races resolved inside the transaction ----


def test_losing_a_race_with_the_same_payload_returns_the_saved_order(cloud):
    cloud.submit_outcome = lambda body: {"outcome": "existing", "saved": cloud._saved(body)}
    with TestClient(app) as client:
        response = client.post("/api/orders", json=payload(), headers=token_headers())
    assert response.status_code == 200
    assert response.json()["id"] == 41


@pytest.mark.parametrize("outcome", ["conflict", "price_changed"])
def test_race_outcomes_found_at_write_time_are_409(cloud, outcome):
    cloud.submit_outcome = lambda body: {"outcome": outcome}
    with TestClient(app) as client:
        response = client.post("/api/orders", json=payload(), headers=token_headers())
    assert response.status_code == 409


def test_retry_after_a_lost_response_finds_the_committed_order(cloud):
    cloud.lose_next_submit_response = True
    headers = token_headers()
    body = payload()
    with TestClient(app) as client:
        assert client.post("/api/orders", json=body, headers=headers).status_code == 503
        retry = client.post("/api/orders", json=body, headers=headers)
    assert retry.status_code == 200
    assert retry.json()["id"] == 41
    assert len(cloud.writes) == 1


# ---- Unavailable or denied cloud ----


def raises(error):
    def respond(request):
        raise error("example.supabase.co refused secret detail", request=request)

    return respond


LEAK = {"message": "permission denied for table orders", "hint": "row 0501234567", "code": "42501"}
FAILURES = {
    "connection": raises(httpx.ConnectError),
    "timeout": raises(httpx.ReadTimeout),
    "denied_403": lambda r: httpx.Response(403, json=LEAK),
    "denied_401": lambda r: httpx.Response(401, json={"message": "Invalid API key"}),
    "missing_rpc_404": lambda r: httpx.Response(404, json={"code": "PGRST202", "message": "x"}),
    "server_500": lambda r: httpx.Response(500, json=LEAK),
    "redirect": lambda r: httpx.Response(302, headers={"Location": "https://evil.example/"}),
    "not_json": lambda r: httpx.Response(200, text="<html>gateway</html>"),
    "wrong_shape": lambda r: httpx.Response(200, json={"unexpected": True}),
}


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
def test_cloud_failure_is_a_generic_503_and_never_falls_back(
    cloud, isolated_settings, caplog, failure
):
    cloud.fail = failure
    headers = token_headers()
    expected = supabase_orders.CloudUnavailable().detail
    with caplog.at_level(logging.INFO), TestClient(app) as client:
        responses = [
            client.get("/api/catalog"),
            client.get("/api/orders/receipt", headers=headers),
            client.get("/api/orders/1", headers=headers),
            client.post("/api/orders", json=payload(), headers=headers),
        ]
        health = client.get("/health")
    for response in responses:
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": expected}
        assert response.headers["cache-control"] == "no-store"
    assert health.status_code == 503
    assert health.json()["database"] == {"engine": "supabase"}
    assert not isolated_settings.exists(), "a cloud failure must not touch SQLite"
    assert all(r.url.host == "example.supabase.co" for r in cloud.requests)
    assert SECRET not in caplog.text
    assert "0501234567" not in caplog.text
    assert headers["X-Order-Token"] not in caplog.text


def test_denied_call_logs_only_the_sqlstate(cloud, caplog):
    cloud.fail = FAILURES["denied_403"]
    with caplog.at_level(logging.ERROR, logger=supabase_orders.__name__), TestClient(app) as client:
        client.get("/api/catalog")
    assert "customer_catalog returned HTTP 403 (42501)" in caplog.text
    assert "permission denied" not in caplog.text


# ---- Migration contract; behaviour is proven in supabase/tests/catalog-normalization.mjs ----


@pytest.fixture
def migration():
    files = list(MIGRATIONS.glob("*_catalog_normalization.sql"))
    assert len(files) == 1
    return re.sub(r"--[^\n]*", "", files[0].read_text(encoding="utf-8"))


SIGNATURES = (
    "public.customer_catalog()",
    "public.customer_order_read(text, bigint)",
    "public.customer_order_submit(text, text, jsonb)",
)


def test_migration_keeps_rpcs_invoker_and_service_role_only(migration):
    assert "security definer" not in migration.lower()
    assert "user_metadata" not in migration
    # The three RPCs and the dish code trigger.
    assert migration.lower().count("security invoker set search_path = ''") == 4
    for signature in SIGNATURES:
        assert f"revoke all on function {signature} from public, anon, authenticated" in migration
        assert f"grant execute on function {signature} to service_role" in migration
    roles = re.findall(r"grant execute on function [^;]* to (\w+);", migration)
    assert roles == ["service_role"] * 3


def test_migration_gives_the_backend_read_only_catalog_access(migration):
    grants = re.sub(r"\s+", " ", migration)
    assert (
        "grant select on public.dish_categories, public.dish_dietary, public.allergens, "
        "public.dish_allergens to service_role"
    ) in grants
    assert not re.search(r"grant[^;]*\b(insert|update|delete)\b[^;]*\bto service_role\b", grants)
    assert not re.search(r"grant[^;]*\bto\b[^;]*\b(anon|public)\b", grants)


def test_migration_stores_no_metadata_or_second_price(migration):
    assert "drop column metadata" in migration
    assert "add column metadata" not in migration
    assert "'price'" not in migration
    assert "where d.is_available" in migration
    assert "and d.is_available" in migration


def test_migration_serializes_a_token_before_checking_it(migration):
    body = migration[migration.index("function public.customer_order_submit") :]
    assert body.index("pg_advisory_xact_lock") < body.index("from public.order_submissions")
    assert body.index("from public.order_submissions") < body.index("insert into public.customers")
    assert not re.search(r"^\s*(begin\s*;|commit\s*;|rollback\s*;)", migration, re.I | re.M)
