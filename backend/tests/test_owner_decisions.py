"""Owner approve/reject. Supabase Auth and PostgREST are fakes: no credentials, no network.

SQL behaviour of owner_order_decide runs in supabase/tests/owner-order-decision.mjs.
"""

import base64
import functools
import json
import logging
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.repositories import supabase_orders
from app.services import owner_auth
from tests.test_customer_orders import credentials, payload

PUBLISHABLE = "sb_publishable_unit-test-value"
SECRET = "sb_secret_unit-test-value"  # noqa: S105 - not a real credential
OWNER_TOKEN = "owner.token.value"  # noqa: S105 - opaque test token
MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


def user(**metadata):
    return {"id": "00000000-0000-0000-0000-000000000001", **metadata}


def forged_owner_jwt():
    """An unsigned JWT whose claims say owner: decoding it locally would wrongly trust it."""
    part = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")  # noqa: E731
    return f"{part({'alg': 'none'})}.{part({'app_metadata': {'role': 'catering_owner'}})}.x"


class FakeAuth:
    """GET /auth/v1/user: tokens map to responses; anything unknown is an invalid token."""

    def __init__(self):
        self.requests = []
        self.fail = None
        self.users = {
            OWNER_TOKEN: lambda r: httpx.Response(
                200, json=user(app_metadata={"role": "catering_owner", "provider": "email"})
            ),
            "manager": lambda r: httpx.Response(
                200, json=user(app_metadata={"role": "catering_manager"})
            ),
            "customer": lambda r: httpx.Response(200, json=user(app_metadata={})),
            "self-claimed": lambda r: httpx.Response(
                200, json=user(app_metadata={}, user_metadata={"role": "catering_owner"})
            ),
            "expired": lambda r: httpx.Response(403, json={"error_code": "bad_jwt"}),
        }

    def __call__(self, request):
        self.requests.append(request)
        if self.fail:
            return self.fail(request)
        assert request.url.path == "/auth/v1/user"
        token = request.headers["authorization"].removeprefix("Bearer ")
        respond = self.users.get(token, lambda r: httpx.Response(401, json={"msg": "invalid"}))
        return respond(request)


@pytest.fixture
def auth(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", PUBLISHABLE)
    get_settings.cache_clear()
    fake = FakeAuth()
    monkeypatch.setattr(
        owner_auth,
        "new_client",
        functools.partial(owner_auth.new_client, transport=httpx.MockTransport(fake)),
    )
    return fake


def bearer(token=OWNER_TOKEN):
    return {"Authorization": f"Bearer {token}"}


def decide(client, order_id, decision="approved", version=1, note="", token=OWNER_TOKEN):
    body = {"decision": decision, "expected_version": version, "note": note}
    return client.post(f"/api/admin/orders/{order_id}/decision", json=body, headers=bearer(token))


def submit(client):
    headers = credentials()
    response = client.post("/api/orders", json=payload(True), headers=headers)
    assert response.status_code == 201, response.text
    return response.json(), headers


def rows(db_file):
    """Everything a decision must not touch, plus the order's own columns."""
    with sqlite3.connect(db_file) as db:
        return {
            table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()  # noqa: S608
            for table in ("customers", "addresses", "events", "order_items", "order_submissions")
        } | {
            "orders": db.execute(
                "SELECT id, customer_id, event_id, fulfillment_type, requested_at, "
                "delivery_address_id, subtotal_minor, delivery_fee_minor, total_minor, "
                "submitted_at, created_at FROM orders ORDER BY id"
            ).fetchall()
        }


# ---- Who may decide ----


@pytest.mark.parametrize(
    "headers,code",
    [
        ({}, 401),
        ({"Authorization": OWNER_TOKEN}, 401),
        ({"Authorization": f"Basic {OWNER_TOKEN}"}, 401),
        ({"Authorization": "Bearer "}, 401),
        (bearer("not-a-session"), 401),
        (bearer("expired"), 401),
        (bearer(forged_owner_jwt()), 401),
        (bearer("customer"), 403),
        (bearer("manager"), 403),
        (bearer("self-claimed"), 403),
    ],
    ids=[
        "anonymous",
        "no_scheme",
        "basic",
        "empty",
        "invalid",
        "expired",
        "forged_unsigned_owner_jwt",
        "customer",
        "manager",
        "user_metadata_role",
    ],
)
def test_only_an_auth_verified_owner_may_decide(auth, isolated_settings, headers, code):
    with TestClient(app) as client:
        saved, _ = submit(client)
        before = rows(isolated_settings)
        response = client.post(
            f"/api/admin/orders/{saved['id']}/decision",
            json={"decision": "approved", "expected_version": 1, "note": ""},
            headers=headers,
        )
    assert response.status_code == code, response.text
    assert response.headers["cache-control"] == "no-store"
    assert isinstance(response.json()["detail"], str)
    if code == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert rows(isolated_settings) == before
    with sqlite3.connect(isolated_settings) as db:
        assert db.execute("SELECT status, version FROM orders").fetchall() == [
            ("pending_approval", 1)
        ]


def test_anonymous_is_refused_without_asking_auth(auth):
    with TestClient(app) as client:
        response = client.post(
            "/api/admin/orders/1/decision", json={"decision": "approved", "expected_version": 1}
        )
    assert response.status_code == 401
    assert auth.requests == []


def test_auth_lookup_sends_only_the_publishable_key_and_the_token(auth, monkeypatch):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    get_settings.cache_clear()
    with TestClient(app) as client:
        saved, _ = submit(client)
        assert decide(client, saved["id"]).status_code == 200
    [request] = auth.requests
    assert request.method == "GET"
    assert str(request.url) == "https://example.supabase.co/auth/v1/user"
    assert request.headers["apikey"] == PUBLISHABLE
    assert request.headers["authorization"] == f"Bearer {OWNER_TOKEN}"
    assert SECRET not in str(request.headers)


def raises(error):
    def respond(request):
        raise error("auth detail", request=request)

    return respond


AUTH_FAILURES = {
    "connection": raises(httpx.ConnectError),
    "timeout": raises(httpx.ReadTimeout),
    "server_500": lambda r: httpx.Response(500, json={"msg": "down"}),
    "rate_limited": lambda r: httpx.Response(429, json={"msg": "slow down"}),
    "redirect": lambda r: httpx.Response(302, headers={"Location": "https://evil.example/"}),
    "not_json": lambda r: httpx.Response(200, text="<html>gateway</html>"),
    "wrong_shape": lambda r: httpx.Response(200, json=["owner"]),
    "no_user_id": lambda r: httpx.Response(200, json={"app_metadata": {"role": "catering_owner"}}),
}


@pytest.mark.parametrize("failure", AUTH_FAILURES.values(), ids=AUTH_FAILURES.keys())
def test_unreachable_or_strange_auth_denies_with_503(auth, isolated_settings, caplog, failure):
    with TestClient(app) as client:
        saved, _ = submit(client)
        auth.fail = failure
        with caplog.at_level(logging.INFO):
            response = decide(client, saved["id"])
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert OWNER_TOKEN not in caplog.text
    with sqlite3.connect(isolated_settings) as db:
        assert db.execute("SELECT status, version FROM orders").fetchall() == [
            ("pending_approval", 1)
        ]


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"SUPABASE_URL": "https://example.supabase.co"},
        {"SUPABASE_PUBLISHABLE_KEY": PUBLISHABLE},
        {"SUPABASE_URL": "http://example.supabase.co", "SUPABASE_PUBLISHABLE_KEY": PUBLISHABLE},
        {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_PUBLISHABLE_KEY": SECRET},
    ],
    ids=["nothing", "no_key", "no_url", "plain_http", "secret_key_is_not_used"],
)
def test_missing_auth_configuration_is_503_and_sqlite_has_no_bypass(
    auth, monkeypatch, isolated_settings, env
):
    monkeypatch.delenv("SUPABASE_URL")
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    with TestClient(app) as client:
        saved, _ = submit(client)
        response = decide(client, saved["id"])
    assert response.status_code == 503
    assert auth.requests == []
    with sqlite3.connect(isolated_settings) as db:
        assert db.execute("SELECT status FROM orders").fetchone() == ("pending_approval",)


# ---- Deciding ----


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_pending_order_is_decided_once_and_the_customer_sees_it(auth, isolated_settings, decision):
    with TestClient(app) as client:
        saved, headers = submit(client)
        before = rows(isolated_settings)
        response = decide(client, saved["id"], decision, note="  נתראה באירוע!  \n")
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        result = response.json()
        assert set(result) == {"id", "status", "version", "decision_note", "decided_at"}
        assert result["id"] == saved["id"]
        assert result["status"] == decision
        assert result["version"] == 2
        assert result["decision_note"] == "נתראה באירוע!"
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", result["decided_at"])

        for url in ("/api/orders/receipt", f"/api/orders/{saved['id']}"):
            receipt = client.get(url, headers=headers).json()
            assert receipt["status"] == decision
            assert receipt["version"] == 2
            assert receipt["ownerNote"] == "נתראה באירוע!"
            # The frozen quotation is exactly what the customer submitted.
            for key in ("snapshot", "event", "contact", "items", "id"):
                assert receipt[key] == saved[key]
    assert rows(isolated_settings) == before


def test_blank_note_is_stored_as_null_and_reads_as_empty(auth, isolated_settings):
    with TestClient(app) as client:
        saved, headers = submit(client)
        result = decide(client, saved["id"], "rejected", note="   ").json()
        assert result["decision_note"] is None
        assert client.get("/api/orders/receipt", headers=headers).json()["ownerNote"] == ""
        # Omitting the note is the same decision.
        replay = client.post(
            f"/api/admin/orders/{saved['id']}/decision",
            json={"decision": "rejected", "expected_version": 1},
            headers=bearer(),
        )
        assert replay.json() == result
    with sqlite3.connect(isolated_settings) as db:
        assert db.execute("SELECT decision_note FROM orders").fetchone() == (None,)


def test_identical_retry_returns_the_same_result_without_a_second_write(auth, isolated_settings):
    with TestClient(app) as client:
        saved, _ = submit(client)
        first = decide(client, saved["id"], note="מאושר")
        with sqlite3.connect(isolated_settings) as db:
            updated_at = db.execute("SELECT updated_at FROM orders").fetchone()
        for note in ("מאושר", "  מאושר\t"):  # same normalized note
            retry = decide(client, saved["id"], note=note)
            assert retry.status_code == 200
            assert retry.json() == first.json()
    with sqlite3.connect(isolated_settings) as db:
        assert db.execute("SELECT version, updated_at FROM orders").fetchone() == (
            2,
            updated_at[0],
        )


@pytest.mark.parametrize(
    "attempt",
    [
        {"decision": "rejected", "version": 1, "note": "מאושר"},  # other decision
        {"decision": "approved", "version": 1, "note": "אחר"},  # other note
        {"decision": "approved", "version": 1, "note": ""},  # dropped note
        {"decision": "approved", "version": 2, "note": "מאושר"},  # current version, but final
        {"decision": "rejected", "version": 2, "note": ""},  # final -> other final
    ],
)
def test_conflicting_retry_or_second_decision_is_409(auth, isolated_settings, attempt):
    with TestClient(app) as client:
        saved, headers = submit(client)
        first = decide(client, saved["id"], note="מאושר").json()
        response = decide(client, saved["id"], **attempt)
        assert response.status_code == 409
        assert response.headers["cache-control"] == "no-store"
        receipt = client.get("/api/orders/receipt", headers=headers).json()
    assert (receipt["status"], receipt["version"], receipt["ownerNote"]) == (
        "approved",
        2,
        "מאושר",
    )
    assert first["version"] == 2


@pytest.mark.parametrize("version", [2, 7])
def test_version_mismatch_on_a_pending_order_is_409_and_writes_nothing(
    auth, isolated_settings, version
):
    with TestClient(app) as client:
        saved, _ = submit(client)
        assert decide(client, saved["id"], version=version).status_code == 409
    with sqlite3.connect(isolated_settings) as db:
        assert db.execute("SELECT status, version, decided_at FROM orders").fetchone() == (
            "pending_approval",
            1,
            None,
        )


def test_draft_order_cannot_be_decided(auth, isolated_settings, make, conn):
    order_id = make.order()  # a draft has no submission and no prices
    conn.commit()
    with TestClient(app) as client:
        assert decide(client, order_id).status_code == 409
    with sqlite3.connect(isolated_settings) as db:
        assert db.execute("SELECT status, version FROM orders").fetchone() == ("draft", 1)


def test_legacy_pending_order_without_a_submission_can_be_decided(auth, make, conn):
    order_id = make.priced_order()
    conn.commit()
    with TestClient(app) as client:
        result = decide(client, order_id, "rejected", note="תאריך תפוס").json()
    assert (result["status"], result["version"], result["decision_note"]) == (
        "rejected",
        2,
        "תאריך תפוס",
    )


@pytest.mark.parametrize("order_id", ["999", str(2**63), "0", "-1"])
def test_missing_order_is_404(auth, order_id):
    with TestClient(app) as client:
        submit(client)
        response = client.post(
            f"/api/admin/orders/{order_id}/decision",
            json={"decision": "approved", "expected_version": 1},
            headers=bearer(),
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "pending_approval", "expected_version": 1},
        {"decision": "APPROVED", "expected_version": 1},
        {"decision": "approved"},
        {"decision": "approved", "expected_version": 0},
        {"decision": "approved", "expected_version": "1"},
        {"decision": "approved", "expected_version": True},
        {"decision": "approved", "expected_version": 1.0},
        {"decision": "approved", "expected_version": 2**63},
        {"decision": "approved", "expected_version": 1, "note": "x" * 2001},
        {"decision": "approved", "expected_version": 1, "note": None},
        {"decision": "approved", "expected_version": 1, "note": "nul\x00"},
        {"decision": "approved", "expected_version": 1, "status": "approved"},
        {"decision": "approved", "expected_version": 1, "total_minor": 1},
    ],
)
def test_invalid_body_is_422_and_writes_nothing(auth, isolated_settings, body):
    with TestClient(app) as client:
        saved, _ = submit(client)
        before = rows(isolated_settings)
        response = client.post(
            f"/api/admin/orders/{saved['id']}/decision", json=body, headers=bearer()
        )
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert rows(isolated_settings) == before


def test_note_of_2000_characters_after_trimming_is_accepted(auth):
    with TestClient(app) as client:
        saved, _ = submit(client)
        response = decide(client, saved["id"], note=" " + "א" * 2000 + " ")
    assert response.status_code == 200
    assert response.json()["decision_note"] == "א" * 2000


@pytest.mark.parametrize(
    "decisions,codes",
    [(["approved", "rejected"], [200, 409]), (["approved", "approved"], [200, 200])],
    ids=["conflicting", "identical"],
)
def test_concurrent_decisions_move_the_version_once(auth, isolated_settings, decisions, codes):
    with TestClient(app) as client:
        saved, _ = submit(client)
        start = threading.Barrier(len(decisions))

        def run(decision):
            start.wait()
            return decide(client, saved["id"], decision)

        with ThreadPoolExecutor(max_workers=len(decisions)) as pool:
            results = list(pool.map(run, decisions))
    assert sorted(r.status_code for r in results) == codes
    winners = [r.json() for r in results if r.status_code == 200]
    assert all(w == winners[0] for w in winners)
    with sqlite3.connect(isolated_settings) as db:
        assert db.execute("SELECT status, version FROM orders").fetchone() == (
            winners[0]["status"],
            2,
        )


def test_decision_survives_a_reopened_database(auth, isolated_settings):
    with TestClient(app) as client:
        saved, headers = submit(client)
        result = decide(client, saved["id"], note="מאושר").json()
    with TestClient(app) as client:  # a new app lifespan opens the same file again
        receipt = client.get("/api/orders/receipt", headers=headers).json()
        assert decide(client, saved["id"], note="מאושר").json() == result
    assert (receipt["status"], receipt["version"], receipt["ownerNote"]) == ("approved", 2, "מאושר")
    assert receipt["snapshot"] == saved["snapshot"]


# ---- Cloud backend: one service-only RPC, the owner's token never reaches PostgREST ----


class FakeDecisionRpc:
    def __init__(self):
        self.requests = []
        self.answer = None

    def __call__(self, request):
        self.requests.append(request)
        assert request.url.path == "/rest/v1/rpc/owner_order_decide"
        return self.answer(json.loads(request.content))


ROW = {
    "id": 41,
    "status": "approved",
    "version": 2,
    "decision_note": "מאושר",
    "decided_at": "2026-11-08T10:00:00Z",
}


@pytest.fixture
def cloud(auth, monkeypatch):
    monkeypatch.setenv("ORDER_DATABASE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    get_settings.cache_clear()
    fake = FakeDecisionRpc()
    monkeypatch.setattr(
        supabase_orders,
        "new_client",
        functools.partial(supabase_orders.new_client, transport=httpx.MockTransport(fake)),
    )
    return fake


@pytest.mark.parametrize(
    "answer,code",
    [
        ({"decided": True, "order": ROW}, 200),
        ({"decided": False, "order": ROW}, 200),  # identical replay
        ({"decided": False, "order": ROW | {"status": "rejected"}}, 409),
        ({"decided": False, "order": ROW | {"status": "pending_approval", "version": 1}}, 409),
        ({"decided": False, "order": None}, 404),
    ],
    ids=["decided", "replay", "other_decision", "stale_version", "missing"],
)
def test_cloud_decision_outcomes(cloud, isolated_settings, answer, code):
    cloud.answer = lambda body: httpx.Response(200, json=answer)
    with TestClient(app) as client:
        response = decide(client, 41, note=" מאושר ")
    assert response.status_code == code, response.text
    if code == 200:
        assert response.json() == ROW
    [request] = cloud.requests
    assert json.loads(request.content) == {
        "p_order_id": 41,
        "p_decision": "approved",
        "p_expected_version": 1,
        "p_note": "מאושר",
    }
    assert request.headers["apikey"] == SECRET
    assert "authorization" not in request.headers
    assert OWNER_TOKEN.encode() not in request.content
    assert not isolated_settings.exists(), "cloud mode never opens SQLite"


def test_cloud_is_not_called_for_a_non_owner(cloud):
    with TestClient(app) as client:
        for session, code in (("manager", 403), ("bad", 401)):
            assert decide(client, 41, token=session).status_code == code
    assert cloud.requests == []


@pytest.mark.parametrize(
    "respond",
    [
        lambda b: httpx.Response(500, json={"code": "XX000"}),
        lambda b: httpx.Response(404, json={"code": "PGRST202"}),  # migration not applied
        lambda b: httpx.Response(200, json={"decided": True}),
        lambda b: httpx.Response(200, json={"decided": True, "order": {"id": 41}}),
    ],
    ids=["server_500", "missing_rpc", "no_order_key", "partial_order"],
)
def test_cloud_failure_is_503(cloud, respond):
    cloud.answer = respond
    with TestClient(app) as client:
        response = decide(client, 41)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


# ---- Migration contract; behaviour is proven in supabase/tests/owner-order-decision.mjs ----


@pytest.fixture
def migration():
    files = list(MIGRATIONS.glob("*_owner_order_decision.sql"))
    assert len(files) == 1
    return re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", files[0].read_text(encoding="utf-8")))


def test_migration_adds_only_a_service_role_rpc_and_four_updatable_columns(migration):
    lowered = migration.lower()
    assert "security definer" not in lowered
    assert "user_metadata" not in migration
    assert "security invoker set search_path = ''" in lowered
    assert not re.search(r"\b(alter|drop|create) (table|policy)\b", lowered)
    assert "row level security" not in lowered
    grants = re.findall(r"grant [^;]*;", lowered)
    assert grants == [
        "grant update (status, version, decided_at, decision_note) on public.orders "
        "to service_role;",
        "grant execute on function public.owner_order_decide(bigint, text, bigint, text) "
        "to service_role;",
    ]
    assert (
        "revoke all on function public.owner_order_decide(bigint, text, bigint, text) "
        "from public, anon, authenticated;"
    ) in lowered
    # The compare is in the UPDATE itself, not a separate read before it.
    assert (
        "where o.id = p_order_id and o.status = 'pending_approval' "
        "and o.version = p_expected_version"
    ) in lowered
