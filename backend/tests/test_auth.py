import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.main import app

client = TestClient(app)


@pytest.fixture
def supabase_user(monkeypatch):
    """Replace the Supabase Auth lookup: token -> user (or None for an invalid token)."""
    users = {
        "admin-token": {
            "id": "u1",
            "email": "owner@example.com",
            "app_metadata": {"role": "admin"},
        },
        # user_metadata is user-editable and must never grant access.
        "customer-token": {
            "id": "u2",
            "email": "c@example.com",
            "app_metadata": {},
            "user_metadata": {"role": "admin"},
        },
    }

    async def fake(token):
        return users.get(token)

    monkeypatch.setattr(auth, "fetch_supabase_user", fake)


def get_me(token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/api/admin/me", headers=headers)


def test_admin_gets_profile(supabase_user):
    response = get_me("admin-token")
    assert response.status_code == 200
    assert response.json() == {"id": "u1", "email": "owner@example.com"}


def test_missing_token_is_unauthenticated(supabase_user):
    response = get_me()
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_invalid_token_is_unauthenticated(supabase_user):
    assert get_me("expired").status_code == 401


def test_non_admin_is_forbidden_even_with_user_metadata_role(supabase_user):
    response = get_me("customer-token")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_auth_config_exposes_only_public_values(monkeypatch):
    from app.core.config import Settings

    settings = Settings(
        supabase_url="https://x.supabase.co",
        supabase_publishable_key="sb_publishable_x",
        supabase_secret_key="sb_secret_never_leak",  # noqa: S106 - fake value
    )
    monkeypatch.setattr("app.api.auth.get_settings", lambda: settings)
    body = client.get("/api/auth/config").json()
    assert body == {"supabase_url": "https://x.supabase.co", "publishable_key": "sb_publishable_x"}
    assert "sb_secret" not in str(body)
