"""Money is stored as INTEGER minor units (e.g. agorot). Convert only at the edges."""

from decimal import Decimal, InvalidOperation

MINOR_PER_MAJOR = 100
_CENT = Decimal("0.01")


def to_minor(amount: Decimal | str | int) -> int:
    """Exact conversion: ``Decimal("12.34")`` → ``1234``. Rejects floats and sub-cent values."""
    if isinstance(amount, bool) or not isinstance(amount, Decimal | str | int):
        raise TypeError("money must be a Decimal, str, or int, never a float")
    try:
        value = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError(f"not a valid amount: {amount!r}") from exc
    if not value.is_finite():
        raise ValueError(f"not a finite amount: {amount!r}")
    scaled = value * MINOR_PER_MAJOR
    if scaled != scaled.to_integral_value():
        raise ValueError(f"amount has more than two decimal places: {amount!r}")
    return int(scaled)


def from_minor(minor: int) -> Decimal:
    if isinstance(minor, bool) or not isinstance(minor, int):
        raise TypeError("minor units must be an int")
    return (Decimal(minor) / MINOR_PER_MAJOR).quantize(_CENT)
