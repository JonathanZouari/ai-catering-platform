"""Delivery zones (OPEN_DECISIONS #19): named lists of cities, each zone with one fee.

A city belongs to at most one zone (the DB key enforces it too). Only active zones deliver.
Any other Israeli locality (the CBS list in frontend/data/cities.json) gets the owner's default
fee, when one is set.
"""

import json
import re
import uuid
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.delivery import DeliveryZone, DeliveryZoneCity
from app.schemas import delivery as s
from app.services import settings as settings_svc

LOCALITIES = Path(__file__).resolve().parents[3] / "frontend" / "data" / "cities.json"


def city_key(name: str) -> str:
    """Compare names like the city field does (event.js key()): spaces, hyphens and quote marks
    don't matter, nor doubled yod/vav ("קריית אונו" is the CBS "קרית אונו")."""
    flat = " ".join(re.sub(r"[-\u05be'\"\u05f3\u05f4]", " ", name).split())
    return flat.replace("יי", "י").replace("וו", "ו")


@lru_cache
def _localities() -> dict[str, str]:
    """city_key -> the CBS spelling, for every Israeli locality."""
    names = json.loads(LOCALITIES.read_text(encoding="utf-8"))
    return {city_key(n): n for n in names}


def to_out(zone: DeliveryZone) -> s.ZoneOut:
    return s.ZoneOut(
        id=zone.id,
        name=zone.name,
        fee=zone.fee,
        is_active=zone.is_active,
        cities=[c.city for c in zone.cities],
    )


def list_zones(db: Session) -> list[s.ZoneOut]:
    return [to_out(z) for z in db.scalars(select(DeliveryZone).order_by(DeliveryZone.name))]


def _check_cities(db: Session, cities: list[str], zone_id: uuid.UUID | None) -> list[str]:
    unique = list(dict.fromkeys(cities))  # drop repeats within the request, keep order
    q = (
        select(DeliveryZoneCity.city, DeliveryZone.name)
        .join(DeliveryZone, DeliveryZone.id == DeliveryZoneCity.zone_id)
        .where(DeliveryZoneCity.city.in_(unique))
    )
    if zone_id:  # editing: the zone's own cities are fine
        q = q.where(DeliveryZoneCity.zone_id != zone_id)
    taken = db.execute(q).first()
    if taken:
        raise AppError(
            409,
            "city_taken",
            "This city already belongs to another zone",
            {"city": taken[0], "zone": taken[1]},
        )
    return unique


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:  # duplicate zone name, or a city taken concurrently
        db.rollback()
        raise AppError(409, "conflict", "A zone with this name or city already exists") from exc


def create_zone(db: Session, data: s.ZoneCreate) -> s.ZoneOut:
    cities = _check_cities(db, data.cities, None)
    zone = DeliveryZone(name=data.name, fee=data.fee, is_active=data.is_active)
    zone.cities = [DeliveryZoneCity(city=c) for c in cities]
    db.add(zone)
    _commit(db)
    db.refresh(zone)
    return to_out(zone)


def update_zone(db: Session, zone_id: uuid.UUID, data: s.ZoneUpdate) -> s.ZoneOut:
    zone = db.get(DeliveryZone, zone_id)
    if zone is None:
        raise AppError(404, "not_found", "Zone not found")
    changes = data.model_dump(exclude_unset=True)
    for key in ("name", "fee", "is_active", "cities"):
        if key in changes and changes[key] is None:
            raise AppError(422, "validation_error", f"{key} cannot be null", {"field": key})
    if "cities" in changes:
        cities = _check_cities(db, data.cities, zone.id)
        zone.cities.clear()
        db.flush()  # free the keys before re-adding the cities that stay
        zone.cities.extend(DeliveryZoneCity(city=c) for c in cities)
    for key in ("name", "fee", "is_active"):
        if key in changes:
            setattr(zone, key, changes[key])
    _commit(db)
    db.refresh(zone)
    return to_out(zone)


def delete_zone(db: Session, zone_id: uuid.UUID) -> None:
    zone = db.get(DeliveryZone, zone_id)
    if zone is None:
        raise AppError(404, "not_found", "Zone not found")
    db.delete(zone)  # orders keep their frozen fee; drafts lose the zone (on delete set null)
    db.commit()


def zone_for_city(db: Session, city: str) -> DeliveryZone | None:
    """The active zone that delivers to this city, if any."""
    zone = db.scalar(
        select(DeliveryZone)
        .join(DeliveryZoneCity, DeliveryZoneCity.zone_id == DeliveryZone.id)
        .where(DeliveryZoneCity.city == s.normalize_city(city))
    )
    return zone if zone is not None and zone.is_active else None


def delivery_for(db: Session, city: str) -> tuple[str, Decimal] | None:
    """(the city as stored, its fee) when we deliver there: an active zone's city at the zone fee,
    else any Israeli locality at the default fee (stored in the CBS spelling); None otherwise."""
    zone = zone_for_city(db, city)
    if zone is not None:
        return s.normalize_city(city), zone.fee
    default = settings_svc.get(db).default_delivery_fee
    official = _localities().get(city_key(city))
    if default is not None and official is not None:
        return official, default
    return None


def public_cities(db: Session) -> list[s.CityOut]:
    """Every city we deliver to: zone cities at their fee, then (with a default fee) every other
    locality at that fee."""
    rows = db.execute(
        select(DeliveryZoneCity.city, DeliveryZone.fee)
        .join(DeliveryZone, DeliveryZone.id == DeliveryZoneCity.zone_id)
        .where(DeliveryZone.is_active)
        .order_by(DeliveryZoneCity.city)
    )
    cities = [s.CityOut(city=city, fee=fee) for city, fee in rows]
    default = settings_svc.get(db).default_delivery_fee
    if default is not None:
        zoned = {city_key(c.city) for c in cities}
        cities += [
            s.CityOut(city=name, fee=default)
            for k, name in sorted(_localities().items(), key=lambda kv: kv[1])
            if k not in zoned
        ]
    return cities
