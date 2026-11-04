"""Submitted quotations: server prices, atomic writes, private reads and safe retries."""

import hashlib
import json
import re
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db import get_db

router = APIRouter(prefix="/api")
Connection = Annotated[sqlite3.Connection, Depends(get_db)]
Token = Annotated[str, Header(alias="X-Order-Token", pattern=r"^[a-f0-9]{64}$")]
LOCAL_ZONE = ZoneInfo("Asia/Jerusalem")
SLOTS = {
    "pickup": ["10:00-12:00", "12:00-14:00", "15:00-17:00"],
    "delivery": ["09:00-11:00", "11:00-13:00", "14:00-16:00"],
}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


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


@router.get("/catalog")
def catalog(conn: Connection) -> dict:
    return {
        "dishes": [
            json.loads(row["metadata"])
            | {"price": row["price_minor"] / 100, "step": row["step_milli"] / 1000}
            for row in conn.execute("SELECT * FROM dishes ORDER BY rowid")
        ],
        "zones": [
            {"city": row["city"], "fee": row["fee_minor"] / 100}
            for row in conn.execute("SELECT * FROM delivery_zones ORDER BY rowid")
        ],
    }


def read_order(conn: sqlite3.Connection, order_id: int, token_hash: str) -> dict:
    row = conn.execute(
        "SELECT o.*, s.payload FROM orders o JOIN order_submissions s ON s.order_id=o.id "
        "WHERE o.id=? AND s.token_hash=?",
        (order_id, token_hash),
    ).fetchone()
    if row is None:
        fail("ההזמנה לא נמצאה או שאין הרשאה לצפות בה", 404)
    saved = json.loads(row["payload"])
    labels = {"tray": "מגש", "kg": "ק״ג", "item": "יחידה", "guest": "לאורח"}
    lines = []
    for item in conn.execute(
        "SELECT * FROM order_items WHERE order_id=? ORDER BY rowid", (order_id,)
    ):
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
        "id": row["id"],
        "version": row["version"],
        "status": row["status"],
        "event": saved["event"],
        "contact": saved["contact"],
        "items": {key: float(value) for key, value in saved["items"].items()},
        "ownerNote": row["decision_note"] or "",
        "snapshot": {
            "submittedAt": row["submitted_at"],
            "lines": lines,
            "subtotal": row["subtotal_minor"] / 100,
            "deliveryFee": row["delivery_fee_minor"] / 100,
            "total": row["total_minor"] / 100,
        },
    }


@router.get("/orders/receipt")
def recover_order(conn: Connection, x_order_token: Token, response: Response) -> dict:
    """Recover a receipt even when the original HTTP response was lost."""
    response.headers["Cache-Control"] = "no-store"
    token_hash = hashlib.sha256(x_order_token.encode()).hexdigest()
    row = conn.execute(
        "SELECT order_id FROM order_submissions WHERE token_hash=?", (token_hash,)
    ).fetchone()
    if row is None:
        fail("הבקשה טרם נשמרה", 404)
    return read_order(conn, row[0], token_hash)


@router.get("/orders/{order_id}")
def get_order(order_id: int, conn: Connection, x_order_token: Token, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return read_order(conn, order_id, hashlib.sha256(x_order_token.encode()).hexdigest())


@router.post("/orders", status_code=201)
def submit_order(
    body: Submission, conn: Connection, x_order_token: Token, response: Response
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    token_hash = hashlib.sha256(x_order_token.encode()).hexdigest()
    payload = json.dumps(body.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    # Acquire the write lock before checking the retry key, including concurrent requests.
    conn.execute("UPDATE order_submissions SET token_hash=token_hash WHERE 0")
    existing = conn.execute(
        "SELECT order_id, payload FROM order_submissions WHERE token_hash=?", (token_hash,)
    ).fetchone()
    if existing:
        if existing["payload"] != payload:
            fail("הבקשה כבר נשמרה עם פרטים אחרים. יש לטעון מחדש את ההזמנה.", 409)
        response.status_code = 200
        return read_order(conn, existing["order_id"], token_hash)

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
        zone = conn.execute(
            "SELECT fee_minor FROM delivery_zones WHERE city=?", (event.city,)
        ).fetchone()
        if not zone or not event.address:
            fail("יש לבחור עיר נתמכת ולמלא כתובת למשלוח")
        fee = zone[0]
    lines = []
    for dish_id, quantity in body.items.items():
        dish = conn.execute("SELECT * FROM dishes WHERE id=?", (dish_id,)).fetchone()
        if not dish or not quantity.is_finite() or quantity <= 0 or quantity > 10000:
            fail("מנה או כמות לא תקינה")
        milli = quantity * 1000
        if milli != int(milli) or int(milli) % dish["step_milli"]:
            fail("הכמות אינה מתאימה ליחידת המנה")
        metadata = json.loads(dish["metadata"])
        total = (dish["price_minor"] * int(milli) + 500) // 1000
        lines.append(
            (dish_id, metadata["name"], metadata["unit"], int(milli), dish["price_minor"], total)
        )
    subtotal = sum(line[-1] for line in lines)
    if body.expected_total_minor != subtotal + fee:
        fail("המחיר השתנה. יש לרענן את הדף ולבדוק את הסכום לפני שליחה חוזרת.", 409)

    customer_id = conn.execute(
        "INSERT INTO customers(full_name, phone) VALUES (?, ?)",
        (body.contact.name, body.contact.phone),
    ).lastrowid
    address_id = None
    if event.fulfillment == "delivery":
        address_id = conn.execute(
            "INSERT INTO addresses(customer_id, street, city) VALUES (?, ?, ?)",
            (customer_id, event.address, event.city),
        ).lastrowid
    event_id = conn.execute(
        "INSERT INTO events(customer_id, event_type, event_date, adults, children, "
        "vegetarian_guests, vegan_guests, restricted_guests, dietary_notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            customer_id,
            event.type,
            event.date.isoformat(),
            event.adults,
            event.children,
            event.vegetarian,
            event.vegan,
            event.restricted,
            event.notes,
        ),
    ).lastrowid
    requested = datetime.fromisoformat(f"{event.date}T{event.slot.split('-')[0]}")
    requested = requested.replace(tzinfo=LOCAL_ZONE).astimezone(UTC)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    order_id = conn.execute(
        "INSERT INTO orders(customer_id, event_id, status, fulfillment_type, requested_at, "
        "delivery_address_id, subtotal_minor, delivery_fee_minor, total_minor, submitted_at) "
        "VALUES (?, ?, 'pending_approval', ?, ?, ?, ?, ?, ?, ?)",
        (
            customer_id,
            event_id,
            event.fulfillment,
            requested.strftime("%Y-%m-%dT%H:%M:%SZ"),
            address_id,
            subtotal,
            fee,
            subtotal + fee,
            now,
        ),
    ).lastrowid
    conn.executemany(
        "INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(order_id, *line) for line in lines],
    )
    conn.execute("INSERT INTO order_submissions VALUES (?, ?, ?)", (token_hash, order_id, payload))
    result = read_order(conn, order_id, token_hash)
    conn.commit()  # Never return success before persistence succeeds.
    return result
