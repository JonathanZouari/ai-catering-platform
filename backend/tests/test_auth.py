from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import text

from app.schemas.caterers import CatererCreate
from tests.conftest import make_token

URL = "/api/admin/categories"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_valid_login_is_accepted(client, make_tenant):
    tenant = make_tenant("caterer-a")
    assert client.get(URL, headers=tenant.headers).status_code == 200


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"aud": "anon"},
        {"sub": "not-a-uuid"},
    ],
)
def test_bad_claims_are_rejected(client, make_tenant, overrides):
    tenant = make_tenant("caterer-a")
    token = make_token(tenant.user_id, **overrides)
    response = client.get(URL, headers=_bearer(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_garbage_token_is_rejected(client):
    assert client.get(URL, headers=_bearer("garbage")).status_code == 401


def test_unsigned_token_is_rejected(client, make_tenant):
    tenant = make_tenant("caterer-a")
    claims = {
        "sub": str(tenant.user_id),
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    token = jwt.encode(claims, key="", algorithm="none")
    assert client.get(URL, headers=_bearer(token)).status_code == 401


def test_token_signed_with_another_key_is_rejected(client, make_tenant):
    tenant = make_tenant("caterer-a")
    claims = {
        "sub": str(tenant.user_id),
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    token = jwt.encode(claims, ec.generate_private_key(ec.SECP256R1()), algorithm="ES256")
    assert client.get(URL, headers=_bearer(token)).status_code == 401


def test_symmetric_token_is_rejected(client, make_tenant):
    tenant = make_tenant("caterer-a")
    claims = {
        "sub": str(tenant.user_id),
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    token = jwt.encode(claims, "a-secret-an-attacker-picked-long-enough!", algorithm="HS256")
    assert client.get(URL, headers=_bearer(token)).status_code == 401


def test_login_with_no_caterer_is_forbidden(client):
    response = client.get(URL, headers=_bearer(make_token(uuid4())))
    assert response.status_code == 403


def test_deactivated_caterer_loses_access(client, session, make_tenant):
    tenant = make_tenant("caterer-a")
    session.execute(text("update caterers set is_active = false where id = :i"), {"i": tenant.id})
    session.commit()

    assert client.get(URL, headers=tenant.headers).status_code == 403
    assert client.get(f"/api/c/{tenant.slug}").status_code == 404


def test_public_profile_by_slug(client, make_tenant):
    tenant = make_tenant("caterer-a")
    body = client.get(f"/api/c/{tenant.slug}").json()
    assert body["slug"] == tenant.slug
    assert "id" not in body


def test_unknown_slug_is_not_found(client):
    assert client.get("/api/c/nobody").status_code == 404


@pytest.mark.parametrize("slug", ["Upper", "with space", "-edge", "עברית", "a--b"])
def test_invalid_slugs_are_rejected(slug):
    with pytest.raises(ValueError):
        CatererCreate(slug=slug, name="x", auth_user_id=uuid4())
