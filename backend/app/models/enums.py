from enum import StrEnum

from sqlalchemy import Enum


class PricingUnit(StrEnum):
    PER_GUEST = "per_guest"
    PER_TRAY = "per_tray"
    PER_WEIGHT = "per_weight"
    PER_ITEM = "per_item"


class KashrutClass(StrEnum):
    MEAT = "meat"
    DAIRY = "dairy"
    PAREVE = "pareve"


class FulfillmentType(StrEnum):
    PICKUP = "pickup"
    DELIVERY = "delivery"


class AllergenStatus(StrEnum):
    CONTAINS = "contains"
    FREE = "free"
    UNKNOWN = "unknown"


class KashrutMixingRule(StrEnum):
    BLOCK = "block"
    WARN = "warn"


def pg_enum(enum_class: type[StrEnum], name: str) -> Enum:
    """Map to a Postgres enum type created by the migrations."""
    return Enum(
        enum_class,
        name=name,
        create_type=False,
        values_callable=lambda members: [member.value for member in members],
    )
