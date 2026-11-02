import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.db import apply_migrations, build_engine, get_session, read_only
from app.core.security import get_signing_key_resolver
from app.core.storage import get_storage
from app.main import app
from app.schemas.caterers import CatererCreate
from app.services.caterers import create_caterer

SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())
# Raw SQL in tests binds ids directly; stored ids are 32 hex characters.
sqlite3.register_adapter(UUID, lambda value: value.hex)


@pytest.fixture(scope="session")
def engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    test_engine = build_engine(f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}")
    apply_migrations(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    # Read-only start: a test's own reads must not hold the lock the app's requests need.
    with Session(read_only(engine), expire_on_commit=False) as db:
        yield db
    with engine.begin() as conn:
        # Not everything: this must keep the seeded platform quantity rules.
        conn.execute(text("delete from orders"))
        conn.execute(text("delete from events"))
        conn.execute(text("delete from customers"))
        conn.execute(text("delete from caterers"))


class FakeStorage:
    def __init__(self) -> None:
        self.uploads: dict[str, tuple[bytes, str]] = {}

    def upload(self, path: str, content: bytes, content_type: str) -> None:
        self.uploads[path] = (content, content_type)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def client(engine: Engine, session: Session, storage: FakeStorage) -> Iterator[TestClient]:
    def override_session() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as db:
            yield db

    rate_limit.reset()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_signing_key_resolver] = lambda: (
        lambda _token: SIGNING_KEY.public_key()
    )
    app.dependency_overrides[get_storage] = lambda: storage
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
        data = CatererCreate(slug=slug, name=f"קייטרינג {slug}", auth_user_id=user_id)
        caterer = create_caterer(session, data)
        headers = {"Authorization": f"Bearer {make_token(user_id)}"}
        return TenantFixture(caterer.id, slug, user_id, headers)

    return _make
