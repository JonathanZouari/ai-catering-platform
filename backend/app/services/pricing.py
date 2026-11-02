"""Deterministic order pricing (ADR 0003, OPEN_DECISIONS #14/#17/#18, decided 2026-11-02).

- Catalog prices are in ILS and already include VAT, so no VAT is added.
- Each line = quantity x unit price, rounded half-up to the agora. Total = sum of rounded lines.
- per_weight prices are per kg; quantity is in kg.
- While draft, prices are live from the catalog; a dish that is no longer orderable is flagged and
  left out of the totals. After submission the frozen snapshot is used (later slice).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.models.catalog import Dish
from app.models.orders import Order

AGORA = Decimal("0.01")


def line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(AGORA, rounding=ROUND_HALF_UP)


def orderable(dish: Dish) -> bool:
    return dish.is_available and dish.category.is_active


@dataclass(frozen=True)
class Line:
    dish_id: object
    name: str
    pricing_unit: str
    unit_label: str | None
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    available: bool


@dataclass(frozen=True)
class Priced:
    lines: list[Line]
    subtotal: Decimal
    delivery_fee: Decimal | None  # per delivery zone, OPEN #19 slice
    total: Decimal


def price_order(order: Order, dishes: dict) -> Priced:
    lines = []
    for item in order.items:
        if order.status == "draft":
            dish = dishes[item.dish_id]  # dishes in orders can't be deleted (dish_in_orders)
            ok, name, unit, label = orderable(dish), dish.name, dish.pricing_unit, dish.unit_label
            price = dish.unit_price
        else:
            ok, name, unit, label = True, item.snapshot_name, item.snapshot_pricing_unit, None
            price = item.snapshot_unit_price
        lines.append(
            Line(
                item.dish_id,
                name,
                unit,
                label,
                item.quantity,
                price,
                line_total(item.quantity, price),
                ok,
            )
        )
    lines.sort(key=lambda line: line.name)
    subtotal = sum((line.line_total for line in lines if line.available), Decimal("0.00"))
    fee = order.delivery_fee
    return Priced(lines, subtotal, fee, subtotal + (fee or 0))
