from enum import StrEnum

from sqlalchemy import Enum


class CategoryType(StrEnum):
    SALAD = "salad"
    MAIN = "main"
    SIDE = "side"
    DESSERT = "dessert"
    DRINK = "drink"
    OTHER = "other"


class OrderStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


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


def db_enum(enum_class: type[StrEnum]) -> Enum:
    """Stored as text. The schema's CHECK constraints hold the allowed values."""
    return Enum(
        enum_class,
        native_enum=False,
        create_constraint=False,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )
