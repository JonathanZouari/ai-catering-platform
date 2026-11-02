"""Run the whole app on this computer, with no accounts.

    uv run python -m scripts.dev_server

Fakes Supabase login and image storage on the same address, and keeps data in yummai.db.
Any email and password logs in as the demo caterer, so it refuses to run on a deployed server.
Uploaded images last until the server stops.
"""

import os
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

PORT = int(os.environ.get("PORT", "8000"))
os.environ.setdefault("DATABASE_URL", "sqlite:///./yummai.db")
os.environ["SUPABASE_URL"] = f"http://127.0.0.1:{PORT}"
os.environ["SUPABASE_ANON_KEY"] = "local"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "local"

import jwt  # noqa: E402
import uvicorn  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi import APIRouter, Response  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import apply_migrations, get_engine  # noqa: E402
from app.core.security import get_signing_key_resolver  # noqa: E402
from app.core.storage import get_storage  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Caterer, Dish, DishCategory, TimeSlot  # noqa: E402
from app.models.enums import CategoryType, FulfillmentType, PricingUnit  # noqa: E402
from app.schemas.caterers import CatererCreate  # noqa: E402
from app.services.caterers import create_caterer  # noqa: E402

DEMO_USER = UUID("00000000-0000-4000-8000-000000000001")
KEY = ec.generate_private_key(ec.SECP256R1())
FILES: dict[str, tuple[bytes, str]] = {}


class MemoryStorage:
    def upload(self, path: str, content: bytes, content_type: str) -> None:
        FILES[path] = (content, content_type)


fake_supabase = APIRouter()


@fake_supabase.post("/auth/v1/token")
def fake_token():
    claims = {
        "sub": str(DEMO_USER),
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=8),
    }
    return {"access_token": jwt.encode(claims, KEY, algorithm="ES256"), "refresh_token": "local"}


@fake_supabase.get("/storage/v1/object/public/caterer-assets/{path:path}")
def fake_object(path: str):
    content, content_type = FILES[path]
    return Response(content, media_type=content_type)


def seed_demo_caterer() -> None:
    with Session(get_engine(), expire_on_commit=False) as session:
        if session.scalar(select(Caterer.id).where(Caterer.slug == "demo")):
            return
        data = CatererCreate(slug="demo", name="קייטרינג לדוגמה", auth_user_id=DEMO_USER)
        caterer = create_caterer(session, data)
        category = DishCategory(
            caterer_id=caterer.id, name="עיקריות", category_type=CategoryType.MAIN
        )
        session.add(category)
        session.flush()
        for name, price in (("עוף בתנור", "120.00"), ("אורז לבן", "60.00")):
            session.add(
                Dish(
                    caterer_id=caterer.id,
                    category_id=category.id,
                    name=name,
                    pricing_unit=PricingUnit.PER_TRAY,
                    unit_price=Decimal(price),
                    servings_per_unit=Decimal(10),
                )
            )
        session.add(
            TimeSlot(
                caterer_id=caterer.id,
                fulfillment_type=FulfillmentType.PICKUP,
                start_time=time(9),
                end_time=time(17),
            )
        )
        session.commit()


def main() -> None:
    if get_settings().is_deployed:
        raise SystemExit("dev_server fakes logins, so it only runs with APP_ENV=development")
    apply_migrations(get_engine())
    seed_demo_caterer()
    app.dependency_overrides[get_signing_key_resolver] = lambda: lambda _token: KEY.public_key()
    app.dependency_overrides[get_storage] = MemoryStorage
    # Before the static mount, which would otherwise swallow these paths.
    app.router.routes[:0] = fake_supabase.routes
    print(f"Dashboard: http://127.0.0.1:{PORT}/admin/  (any email and password)")
    print(f"Customers: http://127.0.0.1:{PORT}/c/demo/")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
