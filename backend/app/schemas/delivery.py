import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


def normalize_city(value: str) -> str:
    """One spelling per city: trimmed, single spaces. "תל  אביב " -> "תל אביב"."""
    return " ".join(value.split())


City = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=60),
    AfterValidator(normalize_city),
]
ZoneName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
Fee = Annotated[Decimal, Field(ge=0, le=10_000, max_digits=7, decimal_places=2)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ZoneCreate(_In):
    name: ZoneName
    fee: Fee
    cities: list[City] = Field(min_length=1, max_length=300)
    is_active: bool = True


class ZoneUpdate(_In):
    name: ZoneName | None = None
    fee: Fee | None = None
    cities: list[City] | None = Field(None, min_length=1, max_length=300)  # full replacement
    is_active: bool | None = None


class ZoneOut(BaseModel):
    id: uuid.UUID
    name: str
    fee: Decimal
    is_active: bool
    cities: list[str]


class CityOut(BaseModel):
    """Public: which cities get delivery, and for how much."""

    city: str
    fee: Decimal
