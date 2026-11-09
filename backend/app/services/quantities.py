"""Recommended quantities from guest counts and stored rules. Nothing here is a guess."""

from collections import Counter
from decimal import ROUND_CEILING, Decimal

from app.models import Dish, Event, QuantityRule
from app.models.enums import CategoryType, KashrutClass, PricingUnit

WEIGHT_STEP = Decimal("0.5")


def _eligible_share(dish: Dish, event: Event) -> Decimal:
    """Share of guests who can eat this dish. Unknown counts as not suitable."""
    total = event.adults + event.children
    dietary = dish.dietary
    is_meat = dietary is not None and dietary.kashrut_class == KashrutClass.MEAT
    is_vegan = dietary is not None and dietary.is_vegan is True
    is_vegetarian = dietary is not None and dietary.is_vegetarian is True

    excluded = 0
    if is_meat or not (is_vegan or is_vegetarian):
        excluded = event.vegetarian_guests + event.vegan_guests
    elif not is_vegan:
        excluded = event.vegan_guests
    return Decimal(max(total - excluded, 0)) / Decimal(total)


def _round_up(value: Decimal, unit: PricingUnit) -> Decimal:
    if unit == PricingUnit.PER_WEIGHT:
        return (value / WEIGHT_STEP).to_integral_value(ROUND_CEILING) * WEIGHT_STEP
    return value.to_integral_value(ROUND_CEILING)


def recommend(
    dishes: list[Dish], event: Event, rules: dict[CategoryType, QuantityRule]
) -> dict[object, Decimal | None]:
    """Recommended quantity per chosen dish. None means there's no basis to recommend one."""
    per_type = Counter(dish.category.category_type for dish in dishes)
    recommendations: dict[object, Decimal | None] = {}

    for dish in dishes:
        rule = rules.get(dish.category.category_type)
        share = _eligible_share(dish, event)
        recommendations[dish.id] = None
        if rule is None:
            continue
        portions = event.adults * rule.portions_per_adult + event.children * rule.portions_per_child
        if portions == 0:
            continue

        if dish.pricing_unit == PricingUnit.PER_GUEST:
            quantity = (event.adults + event.children) * share
        elif dish.servings_per_unit:
            split = portions * share / per_type[dish.category.category_type]
            quantity = split / dish.servings_per_unit
        else:
            continue

        rounded = _round_up(quantity, dish.pricing_unit)
        recommendations[dish.id] = max(rounded, dish.min_quantity or Decimal(0))
    return recommendations
