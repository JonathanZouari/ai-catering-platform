# Importing the models registers every table on Base.metadata.
from app.models.customer import Customer
from app.models.event import Event
from app.models.menu import Dish, DishCategory, PricingUnit
from app.models.order import FulfillmentType, Order, OrderItem, OrderStatus

__all__ = [
    "Customer",
    "Dish",
    "DishCategory",
    "Event",
    "FulfillmentType",
    "Order",
    "OrderItem",
    "OrderStatus",
    "PricingUnit",
]
