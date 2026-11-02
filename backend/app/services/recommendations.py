"""Quantity recommendations from the guest composition (OPEN_DECISIONS #3/#4, decided 2026-11-02).

- The owner sets, per dish, how many adult portions one unit serves (`serves_adults`); dishes
  without it get no recommendation.
- A child eats `child_portion` of an adult (settings, default 0.75).
- Only guests who can eat the dish count: vegan dish -> everyone; vegetarian dish -> everyone but
  vegans; any other dish, including unknown dietary data -> everyone but vegetarians and vegans.
  Vegetarian and vegan are separate groups within adults + children.
- We don't know how the dietary groups split between adults and children, so excluded guests
  are removed proportionally: portions = (adults + children x child_portion) x eligible / total.
- Round up: per_weight to 0.5 kg, everything else to whole units; never below the dish minimum.
The customer always decides; this is advice only.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from app.models.catalog import Dish
from app.models.orders import Event

HALF = Decimal("0.5")


def eligible_guests(event: Event, dish: Dish) -> int:
    total = event.adults + event.children
    diet = dish.dietary
    if diet is not None and diet.is_vegan is True:
        return total
    if diet is not None and diet.is_vegetarian is True:
        return total - event.vegan_guests
    return total - event.vegetarian_guests - event.vegan_guests


def round_up(quantity: Decimal, pricing_unit: str) -> Decimal:
    if pricing_unit == "per_weight":
        return (quantity / HALF).to_integral_value(rounding=ROUND_CEILING) * HALF
    return quantity.to_integral_value(rounding=ROUND_CEILING)


@dataclass(frozen=True)
class Recommendation:
    dish_id: object
    quantity: Decimal
    eligible_guests: int


def recommend(event: Event, dishes: list[Dish], child_portion: Decimal) -> list[Recommendation]:
    total = event.adults + event.children
    if total == 0:
        return []
    portions = Decimal(event.adults) + Decimal(event.children) * child_portion
    out = []
    for dish in dishes:
        eligible = eligible_guests(event, dish)
        if not dish.serves_adults or eligible <= 0:
            continue
        needed = portions * eligible / total / dish.serves_adults
        quantity = max(round_up(needed, dish.pricing_unit), dish.min_quantity or Decimal(0))
        out.append(Recommendation(dish.id, quantity.quantize(Decimal("0.01")), eligible))
    return out
