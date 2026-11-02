"""Delivery zones (OPEN_DECISIONS #19): named lists of cities, each zone with one fee.

A city belongs to at most one zone (the DB key enforces it too). Only active zones deliver.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.delivery import DeliveryZone, DeliveryZoneCity
from app.schemas import delivery as s


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


def public_cities(db: Session) -> list[s.CityOut]:
    rows = db.execute(
        select(DeliveryZoneCity.city, DeliveryZone.fee)
        .join(DeliveryZone, DeliveryZone.id == DeliveryZoneCity.zone_id)
        .where(DeliveryZone.is_active)
        .order_by(DeliveryZoneCity.city)
    )
    return [s.CityOut(city=city, fee=fee) for city, fee in rows]
