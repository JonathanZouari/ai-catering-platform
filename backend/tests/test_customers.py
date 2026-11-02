import time
import uuid
from datetime import date

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core import customer_auth
from app.core.config import get_settings
from app.models.orders import Customer
from tests.test_orders import add_order

SUPABASE = "https://test-project.supabase.co"
KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(autouse=True)
def supabase(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_url", SUPABASE)
    monkeypatch.setattr(get_settings(), "supabase_anon_key", "anon-public-key")
    monkeypatch.setattr(customer_auth, "signing_key", lambda _token: KEY.public_key())


def token(sub=None, email="Dana@Example.com", key=KEY, **override):
    claims = {
        "sub": str(sub or uuid.uuid4()),
        "email": email,
        "aud": "authenticated",
        "iss": f"{SUPABASE}/auth/v1",
        "exp": int(time.time()) + 3600,
        "role": "authenticated",
        **override,
    }
    return {"Authorization": f"Bearer {jwt.encode(claims, key, algorithm='ES256')}"}


def test_auth_config_is_public(client):
    res = client.get("/api/auth/config")
    assert res.json() == {"supabase_url": SUPABASE, "supabase_anon_key": "anon-public-key"}


def test_auth_config_unavailable_without_supabase(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_url", None)
    assert client.get("/api/auth/config").status_code == 503
    # and customer routes fail closed
    assert client.get("/api/me", headers=token()).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-jwt"},
        token(key=OTHER_KEY),  # signed by someone else
        token(exp=int(time.time()) - 10),  # expired
        token(aud="anon"),
        token(iss="https://evil.supabase.co/auth/v1"),
        token(email=None),
        token(sub="not-a-uuid"),
    ],
)
def test_rejects_bad_tokens(client, headers):
    res = client.get("/api/me", headers=headers)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthenticated"


def test_alg_none_is_rejected(client):
    claims = {
        "sub": str(uuid.uuid4()),
        "email": "a@b.co",
        "aud": "authenticated",
        "iss": f"{SUPABASE}/auth/v1",
        "exp": int(time.time()) + 60,
    }
    unsigned = jwt.encode(claims, key=None, algorithm="none")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


def test_profile_created_on_first_save(client, make_session):
    user = uuid.uuid4()
    first = client.get("/api/me", headers=token(user)).json()
    assert first == {"email": "dana@example.com", "profile": None}

    res = client.put(
        "/api/me", json={"full_name": " דנה לוי ", "phone": "050-1234567"}, headers=token(user)
    )
    assert res.status_code == 200, res.text
    assert res.json()["profile"] == {"full_name": "דנה לוי", "phone": "050-1234567"}
    # second save updates the same customer
    client.put("/api/me", json={"full_name": "דנה", "phone": "+972501234567"}, headers=token(user))
    with make_session() as db:
        rows = db.query(Customer).filter_by(auth_user_id=user).all()
        assert len(rows) == 1 and rows[0].full_name == "דנה" and rows[0].email == "dana@example.com"


def test_profile_validation(client):
    headers = token()
    for body in (
        {"full_name": "ד", "phone": "050-1234567"},  # too short
        {"full_name": "דנה", "phone": "abc"},
        {"full_name": "דנה", "phone": "050-1234567", "email": "x@y.z"},  # email comes from token
        {"full_name": "דנה", "phone": "050-1234567", "auth_user_id": str(uuid.uuid4())},
    ):
        assert client.put("/api/me", json=body, headers=headers).status_code == 422, body


def test_my_orders_only_mine(client, make_session):
    me, stranger = uuid.uuid4(), uuid.uuid4()
    mine, _ = add_order(make_session, name="דנה", event_date=date(2026, 12, 3))
    theirs, _ = add_order(make_session, name="אחר", event_date=date(2026, 12, 4))
    with make_session() as db:  # link each sample customer to an auth user
        for name, user in (("דנה", me), ("אחר", stranger)):
            db.query(Customer).filter_by(full_name=name).one().auth_user_id = user
        db.commit()

    orders = client.get("/api/me/orders", headers=token(me)).json()
    assert [o["id"] for o in orders] == [mine]
    assert orders[0]["guests"] == 50 and orders[0]["status"] == "pending_approval"
    assert theirs not in {o["id"] for o in orders}
    # a signed-in user with no profile yet simply has no orders
    assert client.get("/api/me/orders", headers=token()).json() == []
