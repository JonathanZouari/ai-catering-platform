"""Fill a Supabase project with a demo caterer, a demo login, and synthetic orders.

    .venv/Scripts/python -m scripts.seed_supabase ../.env.supabase-dev [--reset]

The env file needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY. The demo login's password
is generated once and saved back to the same file as DEMO_PASSWORD, never printed.
All people, phones and orders are made up. --reset deletes the demo caterer first.
"""

import argparse
import hashlib
import random
import secrets
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import httpx

from scripts.demo_menu import DEMO_MENU, PHOTOS

SLUG = "taam"
DEMO_EMAIL = "demo@yummai.test"
BUCKET = "caterer-assets"
LOGO = Path(__file__).resolve().parents[2] / "frontend" / "img" / "brand" / "logo.jpg"

FIRST = ["נועה", "יוסי", "מיכל", "אבי", "שירה", "דניאל", "רותם", "עומר", "טל", "הילה"]
LAST = ["כהן", "לוי", "מזרחי", "פרץ", "ביטון", "אברהם", "פרידמן", "שושן", "דהן", "אזולאי"]
EVENTS = ["חתונה", "בר מצווה", "בת מצווה", "ברית", "יום הולדת", "אירוע חברה", "שבת חתן"]
CITIES = ["תל אביב", "רמת גן", "גבעתיים"]
STATUSES = ["draft", "pending_approval", "pending_approval", "approved", "approved", "rejected"]


def read_env(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)


class Supabase:
    def __init__(self, url: str, service_key: str) -> None:
        self.http = httpx.Client(
            base_url=url.rstrip("/"),
            headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
            timeout=30,
        )

    def _check(self, response: httpx.Response) -> httpx.Response:
        if response.is_error:
            raise SystemExit(
                f"{response.request.method} {response.request.url.path}: "
                f"{response.status_code} {response.text[:300]}"
            )
        return response

    def select(self, table: str, **params: str) -> list[dict]:
        return self._check(self.http.get(f"/rest/v1/{table}", params=params)).json()

    def insert(self, table: str, rows: list[dict] | dict) -> list[dict]:
        response = self.http.post(
            f"/rest/v1/{table}", json=rows, headers={"Prefer": "return=representation"}
        )
        return self._check(response).json()

    def delete(self, table: str, **params: str) -> None:
        self._check(self.http.delete(f"/rest/v1/{table}", params=params))

    def upload(self, path: str, content: bytes, content_type: str) -> None:
        response = self.http.post(
            f"/storage/v1/object/{BUCKET}/{path}",
            content=content,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
        self._check(response)

    def demo_user(self, password: str) -> str:
        """Creates the confirmed demo login, or resets its password if it exists."""
        users = self._check(self.http.get("/auth/v1/admin/users", params={"per_page": "1000"}))
        for user in users.json()["users"]:
            if user["email"] == DEMO_EMAIL:
                self._check(
                    self.http.put(f"/auth/v1/admin/users/{user['id']}", json={"password": password})
                )
                return user["id"]
        response = self.http.post(
            "/auth/v1/admin/users",
            json={"email": DEMO_EMAIL, "password": password, "email_confirm": True},
        )
        return self._check(response).json()["id"]


def reset(db: Supabase) -> None:
    for caterer in db.select("caterers", slug=f"eq.{SLUG}", select="id"):
        scope = f"eq.{caterer['id']}"
        # Orders, events and customers are protected by "on delete restrict".
        db.delete("orders", caterer_id=scope)
        db.delete("events", caterer_id=scope)
        db.delete("customers", caterer_id=scope)
        db.delete("caterers", id=scope)


def seed_menu(db: Supabase, caterer_id: str) -> list[dict]:
    gluten = db.select("allergens", name="eq.גלוטן", select="id")[0]["id"]
    dishes = []
    for order, ((category_name, category_type), items) in enumerate(DEMO_MENU.items()):
        category = db.insert(
            "dish_categories",
            {
                "caterer_id": caterer_id,
                "name": category_name,
                "category_type": category_type.value,
                "sort_order": order,
            },
        )[0]
        for name, price, unit, description, photo, dietary, calories, gluten_status in items:
            image_path = None
            if photo:
                image_path = f"{caterer_id}/dishes/{photo}"
                db.upload(image_path, (PHOTOS / photo).read_bytes(), "image/jpeg")
            dish = db.insert(
                "dishes",
                {
                    "caterer_id": caterer_id,
                    "category_id": category["id"],
                    "name": name,
                    "description": description,
                    "image_path": image_path,
                    "pricing_unit": "per_tray",
                    "unit_price": price,
                    "unit_label": unit,
                    "servings_per_unit": 10,
                    "calories_per_portion": calories,
                },
            )[0]
            dishes.append(dish)
            if dietary:
                kashrut, vegetarian, vegan = dietary
                db.insert(
                    "dish_dietary",
                    {
                        "dish_id": dish["id"],
                        "kashrut_class": kashrut.value,
                        "is_vegetarian": vegetarian,
                        "is_vegan": vegan,
                    },
                )
            if gluten_status:
                db.insert(
                    "dish_allergens",
                    {
                        "dish_id": dish["id"],
                        "allergen_id": gluten,
                        "status": gluten_status,
                    },
                )
    return dishes


def seed_orders(db: Supabase, caterer_id: str, dishes: list[dict]) -> int:
    rng = random.Random(7)  # noqa: S311  # Fake data only, the same on every run.
    zone = db.insert(
        "delivery_zones",
        {
            "caterer_id": caterer_id,
            "name": "מרכז",
            "fee": 50,
            "definition": {"cities": CITIES},
        },
    )[0]
    slots = db.insert(
        "time_slots",
        [
            {
                "caterer_id": caterer_id,
                "fulfillment_type": kind,
                "start_time": time(start).isoformat(),
                "end_time": time(end).isoformat(),
            }
            for kind, start, end in (("pickup", 9, 17), ("delivery", 10, 14), ("delivery", 17, 20))
        ],
    )
    db.insert(
        "blocked_dates",
        {
            "caterer_id": caterer_id,
            "date": (date.today() + timedelta(days=30)).isoformat(),
            "reason": "חופשה",
        },
    )
    now = datetime.now(UTC)
    for i in range(10):
        customer = db.insert(
            "customers",
            {
                "caterer_id": caterer_id,
                "full_name": f"{FIRST[i]} {LAST[i]}",
                "phone": f"050-555-{i:04d}",  # 555 numbers are fictional.
                "email": f"customer{i + 1}@example.com",
            },
        )[0]
        adults, children = rng.randint(20, 150), rng.randint(0, 40)
        event_date = date.today() + timedelta(days=rng.randint(5, 90))
        event = db.insert(
            "events",
            {
                "caterer_id": caterer_id,
                "customer_id": customer["id"],
                "event_type": rng.choice(EVENTS),
                "event_date": event_date.isoformat(),
                "adults": adults,
                "children": children,
                "vegetarian_guests": rng.randint(0, 10),
                "vegan_guests": rng.randint(0, 5),
            },
        )[0]

        status = STATUSES[i % len(STATUSES)]
        delivery = rng.random() < 0.6
        slot = next(
            s for s in slots if s["fulfillment_type"] == ("delivery" if delivery else "pickup")
        )
        lines = []
        for dish in rng.sample(dishes, rng.randint(3, 6)):
            trays = Decimal(max(1, round((adults + children) / 10 * rng.uniform(0.3, 1.0))))
            lines.append((dish, trays, Decimal(str(dish["unit_price"])) * trays))
        subtotal = sum(total for _, _, total in lines)
        fee = Decimal(50) if delivery else Decimal(0)
        submitted = status != "draft"
        created = now - timedelta(days=rng.randint(1, 20), hours=rng.randint(0, 23))
        order = db.insert(
            "orders",
            {
                "caterer_id": caterer_id,
                # A hash of a random token nobody keeps: these synthetic orders have no
                # working customer link.
                "access_token_hash": hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
                "customer_id": customer["id"],
                "event_id": event["id"],
                "status": status,
                "fulfillment_type": "delivery" if delivery else "pickup",
                "requested_at": datetime.combine(event_date, time(12), UTC).isoformat(),
                "time_slot_id": slot["id"],
                "delivery_city": rng.choice(CITIES) if delivery else None,
                "delivery_address": f"רחוב הדוגמה {rng.randint(1, 99)}" if delivery else None,
                "delivery_zone_id": zone["id"] if delivery else None,
                "subtotal": str(subtotal),
                "delivery_fee": str(fee),
                "total": str(subtotal + fee),
                "submitted_at": (created + timedelta(hours=1)).isoformat() if submitted else None,
                "decided_at": (created + timedelta(days=1)).isoformat()
                if status in ("approved", "rejected")
                else None,
                "decision_note": "התאריך תפוס, מצטערים" if status == "rejected" else None,
                "created_at": created.isoformat(),
                "updated_at": created.isoformat(),
            },
        )[0]
        db.insert(
            "order_items",
            [
                {
                    "caterer_id": caterer_id,
                    "order_id": order["id"],
                    "dish_id": dish["id"],
                    "quantity": str(trays),
                    **(
                        {
                            "snapshot_name": dish["name"],
                            "snapshot_pricing_unit": "per_tray",
                            "snapshot_unit_price": str(dish["unit_price"]),
                            "snapshot_line_total": str(total),
                        }
                        if submitted
                        else {}
                    ),
                }
                for dish, trays, total in lines
            ],
        )
    return 10


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("env_file", type=Path)
    parser.add_argument("--reset", action="store_true", help="delete the demo caterer first")
    args = parser.parse_args()
    env = read_env(args.env_file)
    db = Supabase(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    if args.reset:
        reset(db)
    if db.select("caterers", slug=f"eq.{SLUG}", select="id"):
        raise SystemExit(f"Caterer '{SLUG}' already exists. Run with --reset to rebuild it.")

    password = env.get("DEMO_PASSWORD")
    if not password:
        password = secrets.token_urlsafe(18)
        with args.env_file.open("a", encoding="utf-8") as f:
            f.write(f"DEMO_EMAIL={DEMO_EMAIL}\nDEMO_PASSWORD={password}\n")
    user_id = db.demo_user(password)

    caterer = db.insert(
        "caterers",
        {
            "slug": SLUG,
            "name": "טעם של יחד",
            "kashrut_status": "כשר למהדרין",
            "contact_phone": "*6428",
        },
    )[0]
    logo = f"{caterer['id']}/brand/logo.jpg"
    db.upload(logo, LOGO.read_bytes(), "image/jpeg")
    db.http.patch(f"/rest/v1/caterers?id=eq.{caterer['id']}", json={"logo_path": logo})
    db.insert("caterer_users", {"caterer_id": caterer["id"], "auth_user_id": user_id})

    dishes = seed_menu(db, caterer["id"])
    orders = seed_orders(db, caterer["id"], dishes)
    print(f"Seeded caterer '{SLUG}' with {len(dishes)} dishes and {orders} orders.")
    print(f"Demo login: {DEMO_EMAIL} (password saved as DEMO_PASSWORD in {args.env_file})")


if __name__ == "__main__":
    main()
