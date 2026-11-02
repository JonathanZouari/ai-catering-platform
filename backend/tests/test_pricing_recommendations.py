"""Exact-number tests for the calculation rules (OPEN_DECISIONS #3/#4/#14/#18)."""

from decimal import Decimal as D
from types import SimpleNamespace as NS

from app.services.pricing import line_total, price_order
from app.services.recommendations import recommend, round_up

# 40 adults + 10 children, of whom 5 vegetarian and 2 vegan (separate groups).
EVENT = NS(adults=40, children=10, vegetarian_guests=5, vegan_guests=2)
CHILD = D("0.75")  # -> 40 + 7.5 = 47.5 adult portions across 50 guests


def dish(i, unit="per_tray", serves=None, vegetarian=None, vegan=None, minimum=None, known=True):
    dietary = NS(is_vegetarian=vegetarian, is_vegan=vegan) if known else None
    return NS(
        id=i,
        pricing_unit=unit,
        serves_adults=serves and D(serves),
        dietary=dietary,
        min_quantity=minimum and D(minimum),
    )


def by_id(recs):
    return {r.dish_id: (r.quantity, r.eligible_guests) for r in recs}


def test_line_total_rounds_half_up_to_the_agora():
    assert line_total(D("2.5"), D("33.33")) == D("83.33")  # 83.325 -> 83.33
    assert line_total(D("3"), D("0.335")) == D("1.01")  # 1.005 -> 1.01, not banker's 1.00
    assert line_total(D("1"), D("120")) == D("120.00")


def test_price_order_draft_uses_live_prices_and_skips_unorderable():
    cat = NS(is_active=True)
    dishes = {
        "a": NS(
            name="חומוס",
            pricing_unit="per_tray",
            unit_label=None,
            unit_price=D("120"),
            is_available=True,
            category=cat,
        ),
        "b": NS(
            name="בריסקט",
            pricing_unit="per_weight",
            unit_label='לק"ג',
            unit_price=D("219.99"),
            is_available=True,
            category=cat,
        ),
        "c": NS(
            name="טופו",
            pricing_unit="per_guest",
            unit_label=None,
            unit_price=D("48"),
            is_available=False,
            category=cat,
        ),
    }
    order = NS(
        status="draft",
        delivery_fee=None,
        items=[
            NS(dish_id="a", quantity=D("3")),
            NS(dish_id="b", quantity=D("2.5")),
            NS(dish_id="c", quantity=D("10")),
        ],
    )
    priced = price_order(order, dishes)
    totals = {line.name: (line.line_total, line.available) for line in priced.lines}
    assert totals == {
        "חומוס": (D("360.00"), True),
        "בריסקט": (D("549.98"), True),  # 549.975 -> 549.98
        "טופו": (D("480.00"), False),
    }
    assert priced.subtotal == D("909.98") and priced.total == D("909.98")  # VAT included, no add
    assert priced.delivery_fee is None


def test_round_up_units():
    assert round_up(D("4.01"), "per_tray") == D("5")
    assert round_up(D("4"), "per_item") == D("4")
    assert round_up(D("10.2125"), "per_weight") == D("10.5")
    assert round_up(D("10.5"), "per_weight") == D("10.5")


def test_recommend_counts_only_guests_who_can_eat_the_dish():
    dishes = [
        dish("meat", serves=10, vegetarian=False, vegan=False),  # 43 eligible: 40.85/10 -> 5
        dish("veg", serves=10, vegetarian=True, vegan=False),  # 48 eligible: 45.6/10 -> 5
        dish("vegan", serves=12, vegetarian=True, vegan=True),  # 50 eligible: 47.5/12 -> 4
        dish("unknown", serves=4, known=False),  # unknown = not veg (safe side): 40.85/4 -> 11
        dish("brisket", unit="per_weight", serves=4, vegetarian=False),  # 10.2125 kg -> 10.5
        dish("min", serves=10, vegetarian=False, minimum=6),  # 5 trays, but minimum is 6
        dish("no-rule"),  # no serves_adults -> no advice
    ]
    assert by_id(recommend(EVENT, dishes, CHILD)) == {
        "meat": (D("5.00"), 43),
        "veg": (D("5.00"), 48),
        "vegan": (D("4.00"), 50),
        "unknown": (D("11.00"), 43),
        "brisket": (D("10.50"), 43),
        "min": (D("6.00"), 43),
    }


def test_recommend_skips_dishes_nobody_can_eat_and_uses_child_portion():
    all_veg = NS(adults=4, children=4, vegetarian_guests=6, vegan_guests=2)
    out = by_id(
        recommend(
            all_veg,
            [dish("meat", serves=1, vegetarian=False), dish("vegan", serves=1, vegan=True)],
            CHILD,
        )
    )
    assert out == {"vegan": (D("7.00"), 8)}  # 4 + 4 x 0.75 = 7 portions, meat dish skipped
    assert by_id(recommend(all_veg, [dish("vegan", serves=1, vegan=True)], D("0.5"))) == {
        "vegan": (D("6.00"), 8)
    }
