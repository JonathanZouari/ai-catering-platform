import datetime
import json
import math
import sqlite3
import uuid

from app.repositories import catalog, orders
from app.schemas.orders import OrderIn


class OrderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def submit_order(conn: sqlite3.Connection, order_in: OrderIn) -> dict:
    """Backend is authoritative: prices and fees come from the DB, never from the client."""
    event = order_in.event
    if event.date < datetime.date.today():
        raise OrderError("past_date", "לא ניתן להזמין לתאריך שעבר")

    dishes = {d["id"]: d for d in catalog.get_dishes(conn, list(order_in.items))}
    if any(i not in dishes or not dishes[i]["is_available"] for i in order_in.items):
        raise OrderError("unknown_dish", "אחת המנות אינה קיימת או אינה זמינה")

    for dish_id, qty in order_in.items.items():
        d = dishes[dish_id]
        step = d["step"] or (0.5 if d["unit"] == "kg" else 1)  # mirrors frontend unitStep()
        if abs(qty / step - round(qty / step)) >= 1e-9:
            raise OrderError("invalid_quantity", "אחת הכמויות אינה תקינה")

    delivery_fee = 0
    if event.fulfillment == "delivery":
        fee = catalog.get_zone_fee(conn, event.city)
        if fee is None:
            raise OrderError("unknown_zone", "אין משלוחים לעיר שנבחרה")
        delivery_fee = fee

    order_id = str(uuid.uuid4())
    lines = [
        {
            "order_id": order_id,
            "dish_id": dish_id,
            "quantity": qty,
            "snapshot_name": dishes[dish_id]["name"],
            "snapshot_unit_price": dishes[dish_id]["price"],
            # Half-up rounding is a placeholder until OPEN #14 is decided.
            "snapshot_line_total": math.floor(dishes[dish_id]["price"] * qty + 0.5),
        }
        for dish_id, qty in order_in.items.items()
    ]
    subtotal = sum(line["snapshot_line_total"] for line in lines)
    order = {
        "id": order_id,
        "status": "pending_approval",
        "customer_name": order_in.contact.name,
        "customer_phone": order_in.contact.phone,
        "event": json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": subtotal + delivery_fee,
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    with conn:
        orders.insert_order(conn, order, lines)
    return {"order": order, "lines": lines}
