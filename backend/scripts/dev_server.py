"""Run the whole app on this computer, with no accounts.

    uv run python -m scripts.dev_server

Fakes Supabase login and image storage on the same address, and keeps data in
taam-shel-yachad.db, seeded with a sample menu for the site's caterer.
Any email and password logs in as the demo caterer, so it refuses to run on a deployed server.
Uploaded images last until the server stops.
"""

import os
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

PORT = int(os.environ.get("PORT", "8000"))
# Its own file, so an older local yummai.db is left untouched.
os.environ.setdefault("DATABASE_URL", "sqlite:///./taam-shel-yachad.db")
SLUG = "taam"
os.environ.setdefault("SITE_CATERER", SLUG)
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
from app.models import (  # noqa: E402
    Allergen,
    Caterer,
    DeliveryZone,
    Dish,
    DishAllergen,
    DishCategory,
    DishDietary,
    TimeSlot,
)
from app.models.enums import (  # noqa: E402
    AllergenStatus,
    FulfillmentType,
    PricingUnit,
)
from app.schemas.caterers import CatererCreate  # noqa: E402
from app.services.caterers import create_caterer  # noqa: E402
from scripts.demo_menu import DEMO_MENU, PHOTOS  # noqa: E402

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


BRAND = Path(__file__).resolve().parents[2] / "frontend" / "img" / "brand"


def store_photo(caterer_id: UUID, name: str) -> str:
    path = f"{caterer_id}/demo/{name}"
    FILES[path] = ((PHOTOS / name).read_bytes(), "image/jpeg")
    return path


def seed_demo_caterer() -> None:
    with Session(get_engine(), expire_on_commit=False) as session:
        caterer = session.scalar(select(Caterer).where(Caterer.slug == SLUG))
        if caterer:
            # Photos live in memory, so they are put back on every start.
            for dish in session.scalars(select(Dish).where(Dish.caterer_id == caterer.id)):
                if dish.image_path:
                    FILES[dish.image_path] = (
                        (PHOTOS / dish.image_path.rsplit("/", 1)[1]).read_bytes(),
                        "image/jpeg",
                    )
            if caterer.logo_path:
                FILES[caterer.logo_path] = ((BRAND / "logo.jpg").read_bytes(), "image/jpeg")
            return
        data = CatererCreate(slug=SLUG, name="טעם של יחד", auth_user_id=DEMO_USER)
        caterer = create_caterer(session, data)
        caterer.kashrut_status = "כשר למהדרין"
        caterer.contact_phone = "*6428"
        caterer.logo_path = f"{caterer.id}/demo/logo.jpg"
        FILES[caterer.logo_path] = ((BRAND / "logo.jpg").read_bytes(), "image/jpeg")
        gluten = session.scalar(select(Allergen.id).where(Allergen.name == "גלוטן"))
        for order, ((category_name, category_type), dishes) in enumerate(DEMO_MENU.items()):
            category = DishCategory(
                caterer_id=caterer.id,
                name=category_name,
                category_type=category_type,
                sort_order=order,
            )
            session.add(category)
            session.flush()
            for name, price, unit, description, photo, dietary, calories, gluten_status in dishes:
                dish = Dish(
                    caterer_id=caterer.id,
                    category_id=category.id,
                    name=name,
                    description=description,
                    image_path=store_photo(caterer.id, photo) if photo else None,
                    pricing_unit=PricingUnit.PER_TRAY,
                    unit_price=Decimal(price),
                    unit_label=unit,
                    servings_per_unit=Decimal(10),
                    calories_per_portion=calories,
                )
                session.add(dish)
                session.flush()
                if dietary:
                    kashrut, vegetarian, vegan = dietary
                    session.add(
                        DishDietary(
                            dish_id=dish.id,
                            kashrut_class=kashrut,
                            is_vegetarian=vegetarian,
                            is_vegan=vegan,
                        )
                    )
                if gluten_status:
                    session.add(
                        DishAllergen(
                            dish_id=dish.id,
                            allergen_id=gluten,
                            status=AllergenStatus(gluten_status),
                        )
                    )
        for kind, start, end in (
            (FulfillmentType.PICKUP, 9, 17),
            (FulfillmentType.DELIVERY, 10, 14),
            (FulfillmentType.DELIVERY, 17, 20),
        ):
            session.add(
                TimeSlot(
                    caterer_id=caterer.id,
                    fulfillment_type=kind,
                    start_time=time(start),
                    end_time=time(end),
                )
            )
        session.add(
            DeliveryZone(
                caterer_id=caterer.id,
                name="מרכז",
                fee=Decimal(50),
                definition={"cities": ["תל אביב", "רמת גן", "גבעתיים"]},
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
    print(f"Site:      http://127.0.0.1:{PORT}/")
    print(f"Dashboard: http://127.0.0.1:{PORT}/admin/  (any email and password)")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
