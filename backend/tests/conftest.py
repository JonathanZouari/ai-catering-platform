import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import customer_auth
from app.core.config import get_settings
from app.core.db import get_db
from app.main import app
from app.models.base import Base

TOKEN = "test-owner-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}

# Customer auth: tokens signed by a local key stand in for Supabase (ADR 0005).
SUPABASE = "https://test-project.supabase.co"
KEY = ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def supabase(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_url", SUPABASE)
    monkeypatch.setattr(get_settings(), "supabase_anon_key", "anon-public-key")
    monkeypatch.setattr(customer_auth, "signing_key", lambda _token: KEY.public_key())


def token(sub=None, email="Dana@Example.com", key=KEY, **override):
    """Authorization header with a customer access token shaped like Supabase's."""
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


@pytest.fixture
def make_session():
    """Session factory on a fresh in-memory SQLite DB (shared with `client`)."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def client(monkeypatch, make_session):
    """App client on that DB, with the owner token configured."""
    make = make_session

    def override():
        with make() as session:
            yield session

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(get_settings(), "admin_token", TOKEN)
    yield TestClient(app)
    app.dependency_overrides.clear()
