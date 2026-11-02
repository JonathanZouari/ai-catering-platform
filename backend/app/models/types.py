from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import DateTime, Integer
from sqlalchemy.types import TypeDecorator

# Ten digits in all, two after the point: the most any price, quantity or total can be.
LIMIT = 10**10


class Hundredths(TypeDecorator):
    """A decimal with two places, stored as a whole number so money never passes through a float."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        stored = int((Decimal(str(value)) * 100).quantize(Decimal(1), ROUND_HALF_UP))
        if abs(stored) >= LIMIT:
            raise ValueError("Amount is too large to store")
        return stored

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value).scaleb(-2)


class UtcDateTime(TypeDecorator):
    """SQLite has no time zones, so every stored time is UTC and comes back marked as UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        aware = value if value.tzinfo else value.replace(tzinfo=UTC)
        return aware.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return None if value is None else value.replace(tzinfo=UTC)
