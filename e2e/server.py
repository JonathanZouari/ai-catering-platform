"""Runs the real app on a real Postgres test database, faking only Supabase Auth and Storage."""

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
    SITE_CATERER="taamim",
)

import jwt  # noqa: E402
import uvicorn  # noqa: E402
from app.agents.client import get_llm  # noqa: E402
from app.core.db import get_engine  # noqa: E402
from app.core.email import get_mailer  # noqa: E402
from app.core.security import get_signing_key_resolver  # noqa: E402
from app.core.storage import get_storage  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.caterers import CatererCreate  # noqa: E402
from app.services.caterers import create_caterer  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402
from scripts import test_database  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

USER_ID = uuid4()
KEY = ec.generate_private_key(ec.SECP256R1())
FILES: dict[str, tuple[bytes, str]] = {}
SENT: list[dict[str, str]] = []
SOCKETS: list[WebSocket] = []


def reset_database() -> None:
    engine = get_engine()
    test_database.reset(engine)
    with Session(engine) as session:
        test_database.add_auth_user(session, USER_ID)
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


class MemoryMailer:
    def send(self, to: str, subject: str, text_value: str) -> None:
        SENT.append({"to": to, "subject": subject, "text": text_value})


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


@fake_supabase.get("/test-only/sent-emails")
def fake_outbox():
    return SENT


@fake_supabase.websocket("/realtime/v1/websocket")
async def fake_realtime(socket: WebSocket):
    """Enough of Supabase Realtime for the dashboard: join, heartbeat, then changes."""
    await socket.accept()
    try:
        while True:
            message = await socket.receive_json()
            reply = {"topic": message["topic"], "ref": message["ref"], "event": "phx_reply"}
            await socket.send_json(reply | {"payload": {"status": "ok", "response": {}}})
            if message["event"] == "phx_join":
                SOCKETS.append(socket)
    except WebSocketDisconnect:
        if socket in SOCKETS:
            SOCKETS.remove(socket)


@fake_supabase.post("/test-only/realtime-change")
async def fake_change():
    """What Supabase sends when an order row changes."""
    change = {"data": {"type": "UPDATE", "schema": "public", "table": "orders"}}
    message = {"topic": "realtime:orders", "event": "postgres_changes", "payload": change}
    for socket in list(SOCKETS):
        await socket.send_json(message | {"ref": None})
    return {"sockets": len(SOCKETS)}


reset_database()
app.dependency_overrides[get_signing_key_resolver] = lambda: lambda _token: KEY.public_key()
app.dependency_overrides[get_storage] = MemoryStorage
app.dependency_overrides[get_mailer] = MemoryMailer
app.dependency_overrides[get_llm] = ScriptedModel
# Before the static mount, which would otherwise swallow these paths.
app.router.routes[:0] = fake_supabase.routes
uvicorn.run(app, port=PORT, log_level="warning")
