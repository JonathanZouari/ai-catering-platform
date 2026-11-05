"""Submitted quotations: server prices, atomic writes, private reads and safe retries."""

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal, Protocol
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.db import get_db

router = APIRouter(prefix="/api")
Token = Annotated[str, Header(alias="X-Order-Token", pattern=r"^[a-f0-9]{64}$")]
LOCAL_ZONE = ZoneInfo("Asia/Jerusalem")
SLOTS = {
    "pickup": ["10:00-12:00", "12:00-14:00", "15:00-17:00"],
    "delivery": ["09:00-11:00", "11:00-13:00", "14:00-16:00"],
}
PRICE_CHANGED = "המחיר השתנה. יש לרענן את הדף ולבדוק את הסכום לפני שליחה חוזרת."
DIFFERENT_DETAILS = "הבקשה כבר נשמרה עם פרטים אחרים. יש לטעון מחדש את ההזמנה."


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def no_nul(cls, value: Any) -> Any:
        # Postgres text cannot hold NUL; reject it the same way on every backend.
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Text contains a NUL character")
        return value


class Contact(Input):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(max_length=30)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str) -> str:
        value = re.sub(r"[-\s]", "", value)
        if not re.fullmatch(r"0\d{8,9}", value):
            raise ValueError("Invalid Israeli telephone number")
        return value


class Event(Input):
    type: str = Field(min_length=1, max_length=100)
    date: date
    slot: str = Field(max_length=20)
    fulfillment: Literal["pickup", "delivery"]
    city: str = Field(default="", max_length=100)
    address: str = Field(default="", max_length=500)
    adults: int = Field(ge=1, le=10000, strict=True)
    children: int = Field(ge=0, le=10000, strict=True)
    vegetarian: int = Field(ge=0, le=10000, strict=True)
    vegan: int = Field(ge=0, le=10000, strict=True)
    restricted: int = Field(ge=0, le=10000, strict=True)
    notes: str = Field(default="", max_length=2000)


class Submission(Input):
    contact: Contact
    event: Event
    items: dict[str, Decimal] = Field(min_length=1, max_length=100)
    expected_total_minor: int = Field(ge=0, strict=True)


def fail(message: str, status: int = 422) -> None:
    raise HTTPException(status_code=status, detail=message)


class OrderStore(Protocol):
    def catalog(self) -> dict: ...
    def lock_submissions(self) -> None: ...
    def find(self, token_hash: str, order_id: int | None = None) -> dict | None: ...
    def create(self, token_hash: str, payload: str, draft: dict) -> tuple[str, dict | None]: ...


class SqliteOrders:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def catalog(self) -> dict:
        return {
            "dishes": [
                {
                    "id": row["id"],
                    "metadata": json.loads(row["metadata"]),
                    "price_minor": row["price_minor"],
                    "step_milli": row["step_milli"],
                }
                for row in self.conn.execute("SELECT * FROM dishes ORDER BY rowid")
            ],
            "zones": [
                {"city": row["city"], "fee_minor": row["fee_minor"]}
                for row in self.conn.execute("SELECT * FROM delivery_zones ORDER BY rowid")
            ],
        }

    def lock_submissions(self) -> None:
        # Acquire the write lock before checking the retry key, including concurrent requests.
        self.conn.execute("UPDATE order_submissions SET token_hash=token_hash WHERE 0")

    def find(self, token_hash: str, order_id: int | None = None) -> dict | None:
        row = self.conn.execute(
            "SELECT o.*, s.payload FROM orders o JOIN order_submissions s ON s.order_id=o.id "
            "WHERE s.token_hash=? AND (? IS NULL OR o.id=?)",
            (token_hash, order_id, order_id),
        ).fetchone()
        if row is None:
            return None
        items = self.conn.execute(
            "SELECT * FROM order_items WHERE order_id=? ORDER BY rowid", (row["id"],)
        )
        return {"order": dict(row), "payload": row["payload"], "items": [dict(i) for i in items]}

    def create(self, token_hash: str, payload: str, draft: dict) -> tuple[str, dict | None]:
        conn = self.conn
        customer_id = conn.execute(
            "INSERT INTO customers(full_name, phone) VALUES (?, ?)",
            (draft["full_name"], draft["phone"]),
        ).lastrowid
        address_id = None
        if draft["fulfillment_type"] == "delivery":
            address_id = conn.execute(
                "INSERT INTO addresses(customer_id, street, city) VALUES (?, ?, ?)",
                (customer_id, draft["street"], draft["city"]),
            ).lastrowid
        event_id = conn.execute(
            "INSERT INTO events(customer_id, event_type, event_date, adults, children, "
            "vegetarian_guests, vegan_guests, restricted_guests, dietary_notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                customer_id,
                draft["event_type"],
                draft["event_date"],
                draft["adults"],
                draft["children"],
                draft["vegetarian_guests"],
                draft["vegan_guests"],
                draft["restricted_guests"],
                draft["dietary_notes"],
            ),
        ).lastrowid
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        order_id = conn.execute(
            "INSERT INTO orders(customer_id, event_id, status, fulfillment_type, requested_at, "
            "delivery_address_id, subtotal_minor, delivery_fee_minor, total_minor, submitted_at) "
            "VALUES (?, ?, 'pending_approval', ?, ?, ?, ?, ?, ?, ?)",
            (
                customer_id,
                event_id,
                draft["fulfillment_type"],
                draft["requested_at"],
                address_id,
                draft["subtotal_minor"],
                draft["delivery_fee_minor"],
                draft["total_minor"],
                now,
            ),
        ).lastrowid
        conn.executemany(
            "INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    order_id,
                    line["dish_id"],
                    line["name"],
                    line["unit"],
                    line["quantity_milli"],
                    line["unit_price_minor"],
                    line["line_total_minor"],
                )
                for line in draft["items"]
            ],
        )
        conn.execute(
            "INSERT INTO order_submissions VALUES (?, ?, ?)", (token_hash, order_id, payload)
        )
        saved = self.find(token_hash)
        conn.commit()  # Never return success before persistence succeeds.
        return "created", saved


def get_order_store(request: Request) -> Iterator[OrderStore]:
    """The configured backend only: a cloud failure must never reach SQLite."""
    if get_settings().order_database_backend == "supabase":
        yield request.app.state.cloud_orders
        return
    with contextmanager(get_db)() as conn:
        yield SqliteOrders(conn)


Store = Annotated[OrderStore, Depends(get_order_store)]


@router.get("/catalog")
def catalog(store: Store) -> dict:
    rows = store.catalog()
    return {
        "dishes": [
            row["metadata"] | {"price": row["price_minor"] / 100, "step": row["step_milli"] / 1000}
            for row in rows["dishes"]
        ],
        "zones": [{"city": row["city"], "fee": row["fee_minor"] / 100} for row in rows["zones"]],
    }


def receipt(saved: dict) -> dict:
    order = saved["order"]
    submitted = json.loads(saved["payload"])
    labels = {"tray": "מגש", "kg": "ק״ג", "item": "יחידה", "guest": "לאורח"}
    lines = []
    for item in saved["items"]:
        qty = item["quantity_milli"] / 1000
        lines.append(
            {
                "name": item["name"],
                "qty": f"{qty:g} {labels[item['unit']]}",
                "unitPrice": item["unit_price_minor"] / 100,
                "lineTotal": item["line_total_minor"] / 100,
            }
        )
    return {
        "id": order["id"],
        "version": order["version"],
        "status": order["status"],
        "event": submitted["event"],
        "contact": submitted["contact"],
        "items": {key: float(value) for key, value in submitted["items"].items()},
        "ownerNote": order["decision_note"] or "",
        "snapshot": {
            "submittedAt": order["submitted_at"],
            "lines": lines,
            "subtotal": order["subtotal_minor"] / 100,
            "deliveryFee": order["delivery_fee_minor"] / 100,
            "total": order["total_minor"] / 100,
        },
    }


@router.get("/orders/receipt")
def recover_order(store: Store, x_order_token: Token, response: Response) -> dict:
    """Recover a receipt even when the original HTTP response was lost."""
    response.headers["Cache-Control"] = "no-store"
    saved = store.find(hashlib.sha256(x_order_token.encode()).hexdigest())
    if saved is None:
        fail("הבקשה טרם נשמרה", 404)
    return receipt(saved)


@router.get("/orders/{order_id}")
def get_order(order_id: int, store: Store, x_order_token: Token, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    saved = store.find(hashlib.sha256(x_order_token.encode()).hexdigest(), order_id)
    if saved is None:
        fail("ההזמנה לא נמצאה או שאין הרשאה לצפות בה", 404)
    return receipt(saved)


def quote(body: Submission, catalog_rows: dict) -> dict:
    """Validate a new submission and price it on the server into the row values to persist."""
    event = body.event
    today = datetime.now(LOCAL_ZONE).date()
    if event.date < today + timedelta(days=2) or event.date in {
        today + timedelta(days=5),
        today + timedelta(days=11),
    }:
        fail("התאריך אינו זמין להזמנה")
    if event.slot not in SLOTS[event.fulfillment]:
        fail("חלון הזמן אינו תקין")
    if event.vegetarian + event.vegan + event.restricted > event.adults + event.children:
        fail("מספר האורחים עם הגבלות גדול ממספר האורחים הכולל")

    fee = 0
    if event.fulfillment == "delivery":
        zones = {zone["city"]: zone["fee_minor"] for zone in catalog_rows["zones"]}
        if event.city not in zones or not event.address:
            fail("יש לבחור עיר נתמכת ולמלא כתובת למשלוח")
        fee = zones[event.city]
    dishes = {dish["id"]: dish for dish in catalog_rows["dishes"]}
    lines = []
    for dish_id, quantity in body.items.items():
        dish = dishes.get(dish_id)
        if not dish or not quantity.is_finite() or quantity <= 0 or quantity > 10000:
            fail("מנה או כמות לא תקינה")
        milli = quantity * 1000
        if milli != int(milli) or int(milli) % dish["step_milli"]:
            fail("הכמות אינה מתאימה ליחידת המנה")
        lines.append(
            {
                "dish_id": dish_id,
                "name": dish["metadata"]["name"],
                "unit": dish["metadata"]["unit"],
                "quantity_milli": int(milli),
                "unit_price_minor": dish["price_minor"],
                "line_total_minor": (dish["price_minor"] * int(milli) + 500) // 1000,
            }
        )
    subtotal = sum(line["line_total_minor"] for line in lines)
    if body.expected_total_minor != subtotal + fee:
        fail(PRICE_CHANGED, 409)

    requested = datetime.fromisoformat(f"{event.date}T{event.slot.split('-')[0]}")
    requested = requested.replace(tzinfo=LOCAL_ZONE).astimezone(UTC)
    return {
        "full_name": body.contact.name,
        "phone": body.contact.phone,
        "street": event.address,
        "city": event.city,
        "event_type": event.type,
        "event_date": event.date.isoformat(),
        "adults": event.adults,
        "children": event.children,
        "vegetarian_guests": event.vegetarian,
        "vegan_guests": event.vegan,
        "restricted_guests": event.restricted,
        "dietary_notes": event.notes,
        "fulfillment_type": event.fulfillment,
        "requested_at": requested.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "subtotal_minor": subtotal,
        "delivery_fee_minor": fee,
        "total_minor": subtotal + fee,
        "items": lines,
    }


@router.post("/orders", status_code=201)
def submit_order(body: Submission, store: Store, x_order_token: Token, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    token_hash = hashlib.sha256(x_order_token.encode()).hexdigest()
    payload = json.dumps(body.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    store.lock_submissions()
    # A retry is answered before validation: its date or price may no longer be quotable.
    existing = store.find(token_hash)
    if existing:
        if existing["payload"] != payload:
            fail(DIFFERENT_DETAILS, 409)
        response.status_code = 200
        return receipt(existing)

    outcome, saved = store.create(token_hash, payload, quote(body, store.catalog()))
    # Only the cloud reports these: its write is a later transaction than the checks above.
    if outcome == "conflict":
        fail(DIFFERENT_DETAILS, 409)
    if outcome == "price_changed":
        fail(PRICE_CHANGED, 409)
    if outcome == "existing":
        response.status_code = 200
    return receipt(saved)
