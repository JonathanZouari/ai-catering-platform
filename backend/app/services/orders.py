"""Order validation, pricing and persistence. Money is integer agorot; server is authoritative."""

import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta

from app.schemas.orders import OrderCreate

LEAD_DAYS = 2  # PLACEHOLDER minimum lead time (OPEN #5)
PHONE = re.compile(r"^0\d{8,9}$")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def availability(db: sqlite3.Connection, today: date | None = None) -> dict:
    today = today or date.today()
    slots: dict[str, list[str]] = {"pickup": [], "delivery": []}
    for r in db.execute(
        "SELECT DISTINCT fulfillment_type, start_time, end_time FROM time_slots"
        " WHERE is_active = 1 ORDER BY start_time"
    ):
        slots[r["fulfillment_type"]].append(f"{r['start_time']}-{r['end_time']}")
    return {
        "min_date": (today + timedelta(days=LEAD_DAYS)).isoformat(),
        "blocked_dates": [r[0] for r in db.execute("SELECT date FROM blocked_dates ORDER BY date")],
        "zones": [
            {"city": r["name"], "fee": r["fee"]}
            for r in db.execute(
                "SELECT name, fee FROM delivery_zones WHERE is_active = 1 ORDER BY name"
            )
        ],
        "slots": slots,
    }


def _validate(db: sqlite3.Connection, p: OrderCreate, today: date) -> dict[str, str]:
    e, errors = p.event, {}
    if not e.type:
        errors["type"] = "בחרו סוג אירוע"
    try:
        day = date.fromisoformat(e.date)
    except ValueError:
        day = None
        errors["date"] = "בחרו תאריך לאירוע"
    if day and day < today + timedelta(days=LEAD_DAYS):
        errors["date"] = "התאריך קרוב מדי. נדרשים לפחות יומיים מראש."
    elif day and db.execute("SELECT 1 FROM blocked_dates WHERE date = ?", (e.date,)).fetchone():
        errors["date"] = "התאריך הזה סגור להזמנות. בחרו תאריך אחר."
    start, _, end = e.slot.partition("-")
    # strftime('%w'): Sunday = 0. A NULL weekday slot is open every day.
    slot_ok = (
        day
        and db.execute(
            "SELECT 1 FROM time_slots WHERE is_active = 1 AND fulfillment_type = ?"
            " AND start_time = ? AND end_time = ?"
            " AND (weekday IS NULL OR weekday = CAST(strftime('%w', ?) AS INTEGER))",
            (e.fulfillment, start, end, e.date),
        ).fetchone()
    )
    if not slot_ok and "date" not in errors:
        errors["slot"] = "בחרו חלון זמן"
    if e.adults < 1:
        errors["adults"] = "יש להזין לפחות מבוגר אחד"
    if e.vegetarian + e.vegan + e.restricted > e.adults + e.children:
        errors["dietary"] = "מספר האורחים עם הגבלות תזונתיות גדול ממספר האורחים הכולל"
    if e.fulfillment == "delivery":
        if not e.city:
            errors["city"] = "בחרו עיר למשלוח"
        if not e.address.strip():
            errors["address"] = "הזינו כתובת למשלוח"
    if not p.contact.name.strip():
        errors["name"] = "הזינו שם מלא"
    if not PHONE.match(re.sub(r"[-\s]", "", p.contact.phone)):
        errors["phone"] = "הזינו מספר טלפון ישראלי תקין"
    if not p.items:
        errors["items"] = "הוסיפו לפחות מנה אחת להזמנה"
    return errors


def create_order(db: sqlite3.Connection, p: OrderCreate, today: date | None = None) -> dict:
    today = today or date.today()
    errors = _validate(db, p, today)
    dishes = {}
    for it in p.items:
        row = db.execute(
            "SELECT id, name, pricing_unit, unit_price FROM dishes"
            " WHERE id = ? AND is_available = 1",
            (it.dish_id,),
        ).fetchone()
        if not row:
            errors["items"] = "אחת המנות אינה זמינה יותר"
        dishes[it.dish_id] = row
    zone = None
    if p.event.fulfillment == "delivery" and "city" not in errors:
        zone = db.execute(
            "SELECT id, fee FROM delivery_zones WHERE name = ? AND is_active = 1", (p.event.city,)
        ).fetchone()
        if not zone:
            errors["city"] = "אין משלוחים לעיר הזו"
    if errors:
        raise ApiError(422, "validation_error", "הנתונים שנשלחו אינם תקינים", errors)

    lines = [
        (it, dishes[it.dish_id], int(dishes[it.dish_id]["unit_price"] * it.quantity + 0.5))
        for it in p.items
    ]
    subtotal = sum(total for *_, total in lines)
    fee = zone["fee"] if zone else 0
    e, order_id, now = p.event, str(uuid.uuid4()), datetime.now().isoformat(timespec="seconds")
    customer_id, event_id = str(uuid.uuid4()), str(uuid.uuid4())
    with db:
        db.execute(
            "INSERT INTO customers (id, full_name, phone) VALUES (?, ?, ?)",
            (customer_id, p.contact.name.strip(), p.contact.phone.strip()),
        )
        db.execute(
            "INSERT INTO events (id, customer_id, event_type, event_date, adults, children,"
            " vegetarian_guests, vegan_guests, restricted_guests, dietary_notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                customer_id,
                e.type,
                e.date,
                e.adults,
                e.children,
                e.vegetarian,
                e.vegan,
                e.restricted,
                e.notes or None,
            ),
        )
        db.execute(
            "INSERT INTO orders (id, customer_id, event_id, status, fulfillment_type, requested_at,"
            " delivery_address, delivery_zone_id, subtotal, delivery_fee, total, submitted_at)"
            " VALUES (?, ?, ?, 'pending_approval', ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                order_id,
                customer_id,
                event_id,
                e.fulfillment,
                f"{e.date}T{e.slot.partition('-')[0]}",
                e.address.strip() or None,
                zone["id"] if zone else None,
                subtotal,
                fee,
                subtotal + fee,
                now,
            ),
        )
        for it, dish, total in lines:
            db.execute(
                "INSERT INTO order_items (id, order_id, dish_id, quantity, snapshot_name,"
                " snapshot_pricing_unit, snapshot_unit_price, snapshot_line_total)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    order_id,
                    it.dish_id,
                    it.quantity,
                    dish["name"],
                    dish["pricing_unit"],
                    dish["unit_price"],
                    total,
                ),
            )
    return get_order(db, order_id)


def get_order(db: sqlite3.Connection, order_id: str) -> dict:
    o = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not o:
        raise ApiError(404, "not_found", "ההזמנה לא נמצאה")
    return {
        "id": o["id"],
        "status": o["status"],
        "version": o["version"],
        "decision_note": o["decision_note"],
        "submitted_at": o["submitted_at"],
        "snapshot": {
            "lines": [
                {
                    "name": r["snapshot_name"],
                    "pricing_unit": r["snapshot_pricing_unit"],
                    "quantity": r["quantity"],
                    "unit_price": r["snapshot_unit_price"],
                    "line_total": r["snapshot_line_total"],
                }
                for r in db.execute(
                    "SELECT * FROM order_items WHERE order_id = ? ORDER BY rowid", (order_id,)
                )
            ],
            "subtotal": o["subtotal"],
            "delivery_fee": o["delivery_fee"],
            "total": o["total"],
        },
    }
