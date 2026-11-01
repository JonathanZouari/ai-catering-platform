"""All money math lives here. Catalog prices include VAT, so no VAT line is added."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(unit_price: Decimal, quantity: Decimal) -> Decimal:
    return money(unit_price * quantity)


def order_total(line_totals: list[Decimal], delivery_fee: Decimal) -> tuple[Decimal, Decimal]:
    """Return (subtotal, total)."""
    subtotal = money(sum(line_totals, Decimal(0)))
    return subtotal, money(subtotal + delivery_fee)
