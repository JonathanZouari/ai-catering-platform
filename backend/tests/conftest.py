import os
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import customer_auth
from app.core.config import get_settings
from app.core.db import engine_args, get_db
from app.core.migrate import migrate
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


# Opt-in: TEST_DATABASE_URL=<empty Postgres> runs the suite on the real SQL migrations instead of
# SQLite + create_all. The database is wiped first, so never point it at a real one.
PG_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def pg_engine():
    # the wipe below must never reach a real database (e.g. a pasted Supabase URL)
    host = make_url(PG_URL).host
    assert host in ("localhost", "127.0.0.1", "::1"), "TEST_DATABASE_URL must be a local Postgres"
    url, connect_args = engine_args(PG_URL)
    engine = create_engine(url, connect_args=connect_args)
    with engine.begin() as conn:
        conn.execute(text("drop schema if exists public cascade; create schema public"))
        # Supabase's auth.users, which customers.auth_user_id references (migration 0004)
        conn.execute(text("drop schema if exists auth cascade; create schema auth"))
        conn.execute(text("create table auth.users (id uuid primary key)"))
    migrate(PG_URL)
    with engine.begin() as conn:  # test tokens have no auth.users row
        conn.execute(text("alter table customers drop constraint customers_auth_user_id_fkey"))
    yield engine
    engine.dispose()


@pytest.fixture
def make_session(request):
    """Session factory on a fresh DB (shared with `client`): in-memory SQLite, or the migrated
    Postgres emptied before each test."""
    if PG_URL:
        engine = request.getfixturevalue("pg_engine")
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        with engine.begin() as conn:
            conn.execute(text(f"truncate {tables} restart identity cascade"))
        return sessionmaker(engine, expire_on_commit=False)
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
