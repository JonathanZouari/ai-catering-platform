import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core import auth
from app.core.config import get_settings
from app.main import app

ISSUER_BASE = "https://example.supabase.co"
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


class _FakeJwks:
    def get_signing_key_from_jwt(self, _token):
        return type("Key", (), {"key": PRIVATE_KEY.public_key()})()


@pytest.fixture(autouse=True)
def _fake_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", ISSUER_BASE)
    get_settings.cache_clear()
    monkeypatch.setattr(auth, "_jwks_client", lambda: _FakeJwks())
    yield
    get_settings.cache_clear()


def make_token(role=None, key=PRIVATE_KEY, **overrides):
    claims = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "a@example.com",
        "aud": "authenticated",
        "iss": f"{ISSUER_BASE}/auth/v1",
        "exp": int(time.time()) + 600,
        "app_metadata": {"role": role} if role else {},
        **overrides,
    }
    return jwt.encode(claims, key, algorithm="ES256")


client = TestClient(app)


def get(path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(path, headers=headers)


def test_me_requires_token():
    r = get("/api/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


def test_me_customer():
    r = get("/api/me", make_token())
    assert r.status_code == 200
    assert r.json()["role"] == "customer"


def test_admin_endpoint_rejects_customer():
    r = get("/api/admin/me", make_token())
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_admin_endpoint_accepts_admin():
    assert get("/api/admin/me", make_token(role="admin")).status_code == 200


def test_user_metadata_role_is_ignored():
    token = make_token(user_metadata={"role": "admin"})
    assert get("/api/admin/me", token).status_code == 403


@pytest.mark.parametrize(
    "token",
    [
        make_token(exp=int(time.time()) - 10),
        make_token(aud="anon"),
        make_token(iss="https://evil.example/auth/v1"),
        make_token(key=ec.generate_private_key(ec.SECP256R1())),
        "not-a-jwt",
    ],
    ids=["expired", "wrong-aud", "wrong-iss", "wrong-key", "garbage"],
)
def test_invalid_tokens_rejected(token):
    assert get("/api/me", token).status_code == 401
