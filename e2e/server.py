"""Runs the real app on real Postgres, faking only Supabase Auth and Storage on the same origin."""

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
PORT = int(sys.argv[1])
os.environ.update(
    DATABASE_URL=os.environ["E2E_DATABASE_URL"],
    SUPABASE_URL=f"http://127.0.0.1:{PORT}",
    SUPABASE_ANON_KEY="anon",
    SUPABASE_SERVICE_ROLE_KEY="service",
    AI_MONTHLY_MESSAGE_LIMIT="9",
)

import jwt  # noqa: E402
import uvicorn  # noqa: E402
from app.agents.client import get_llm  # noqa: E402
from app.core.db import get_engine  # noqa: E402
from app.core.security import get_signing_key_resolver  # noqa: E402
from app.core.storage import get_storage  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.caterers import CatererCreate  # noqa: E402
from app.services.caterers import create_caterer  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi import APIRouter, Request  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

USER_ID = uuid4()
KEY = ec.generate_private_key(ec.SECP256R1())
FILES: dict[str, tuple[bytes, str]] = {}


def reset_database() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("drop schema if exists public cascade"))
        conn.execute(text("drop schema if exists auth cascade"))
        conn.execute(text("create schema public"))
        conn.execute(text("create schema auth"))
        conn.execute(text("create table auth.users (id uuid primary key)"))
        for migration in sorted((BACKEND.parent / "database" / "migrations").glob("*.sql")):
            conn.exec_driver_sql(migration.read_text(encoding="utf-8"))
        conn.execute(text("insert into auth.users (id) values (:id)"), {"id": USER_ID})
    with Session(engine) as session:
        data = CatererCreate(slug="taamim", name="טעמים קייטרינג", auth_user_id=USER_ID)
        create_caterer(session, data)


class ScriptedModel:
    """Stands in for the provider: asks for the menu, then proposes the first dish."""

    @staticmethod
    def _say(text_value: str) -> SimpleNamespace:
        block = SimpleNamespace(type="text", text=text_value)
        return SimpleNamespace(stop_reason="end_turn", content=[block])

    @staticmethod
    def _use(name: str, arguments: dict) -> SimpleNamespace:
        block = SimpleNamespace(type="tool_use", id=uuid4().hex, name=name, input=arguments)
        return SimpleNamespace(stop_reason="tool_use", content=[block])

    def create(self, system, tools, messages):
        last = messages[-1]["content"]
        if isinstance(last, str):
            if "הוסיפו" in last:
                return self._use("get_available_dishes", {})
            return self._say(f"קיבלתי: {last}")
        result = json.loads(last[0]["content"])
        if "dishes" in result:
            change = {
                "type": "add_item",
                "dish_id": result["dishes"][0]["dish_id"],
                "quantity": "2",
            }
            return self._use(
                "propose_order_change", {"changes": [change], "rationale": "מתאים לאירוע"}
            )
        return self._say("הכנתי הצעה. אשרו אותה בכרטיס")


class MemoryStorage:
    def upload(self, path: str, content: bytes, content_type: str) -> None:
        FILES[path] = (content, content_type)


fake_supabase = APIRouter()


@fake_supabase.post("/auth/v1/token")
async def fake_token(request: Request):
    body = await request.json()
    if body.get("password") == "wrong":
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    claims = {
        "sub": str(USER_ID),
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return {"access_token": jwt.encode(claims, KEY, algorithm="ES256"), "refresh_token": "r"}


@fake_supabase.get("/storage/v1/object/public/caterer-assets/{path:path}")
def fake_object(path: str):
    content, content_type = FILES[path]
    return Response(content, media_type=content_type)


reset_database()
app.dependency_overrides[get_signing_key_resolver] = lambda: lambda _token: KEY.public_key()
app.dependency_overrides[get_storage] = MemoryStorage
app.dependency_overrides[get_llm] = ScriptedModel
# Before the static mount, which would otherwise swallow these paths.
app.router.routes[:0] = fake_supabase.routes
uvicorn.run(app, port=PORT, log_level="warning")
