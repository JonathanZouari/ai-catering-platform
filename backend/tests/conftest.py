import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.db import build_engine, get_session
from app.core.security import get_signing_key_resolver
from app.main import app
from app.schemas.caterers import CatererCreate
from app.services.caterers import create_caterer

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        # In CI a skip would silently drop the isolation proof, so fail instead.
        if os.environ.get("CI"):
            pytest.fail("TEST_DATABASE_URL must be set in CI")
        pytest.skip("TEST_DATABASE_URL not set")
    # This fixture wipes the schema, so refuse anything not clearly a test database.
    if "test" not in url.rsplit("/", 1)[-1]:
        pytest.fail("TEST_DATABASE_URL database name must contain 'test'")

    test_engine = build_engine(url)
    with test_engine.begin() as conn:
        conn.execute(text("drop schema if exists public cascade"))
        conn.execute(text("drop schema if exists auth cascade"))
        conn.execute(text("create schema public"))
        # Stands in for the schema Supabase provides.
        conn.execute(text("create schema auth"))
        conn.execute(text("create table auth.users (id uuid primary key)"))
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.exec_driver_sql(migration.read_text(encoding="utf-8"))
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as db:
        yield db
    with engine.begin() as conn:
        conn.execute(text("truncate caterers, allergens, auth.users cascade"))


@pytest.fixture
def client(engine: Engine, session: Session) -> Iterator[TestClient]:
    def override_session() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_signing_key_resolver] = lambda: (
        lambda _token: SIGNING_KEY.public_key()
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_token(user_id: UUID | str, **overrides: object) -> str:
    claims = {
        "sub": str(user_id),
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(claims | overrides, SIGNING_KEY, algorithm="ES256")


@dataclass
class TenantFixture:
    id: UUID
    slug: str
    user_id: UUID
    headers: dict[str, str]


@pytest.fixture
def make_tenant(session: Session) -> Callable[[str], TenantFixture]:
    def _make(slug: str) -> TenantFixture:
        user_id = uuid4()
        session.execute(text("insert into auth.users (id) values (:id)"), {"id": user_id})
        data = CatererCreate(slug=slug, name=f"קייטרינג {slug}", auth_user_id=user_id)
        caterer = create_caterer(session, data)
        headers = {"Authorization": f"Bearer {make_token(user_id)}"}
        return TenantFixture(caterer.id, slug, user_id, headers)

    return _make
