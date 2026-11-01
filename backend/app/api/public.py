from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.errors import not_found
from app.core.storage import public_storage_url
from app.core.tenancy import CatererScope
from app.models import Caterer
from app.models.enums import KashrutClass
from app.repositories.catalog import CategoryRepository, DishRepository, list_allergens
from app.repositories.caterers import get_active_caterer_by_slug
from app.repositories.logistics import (
    BlockedDateRepository,
    DeliveryZoneRepository,
    TimeSlotRepository,
)
from app.schemas.catalog import AllergenOut, CategoryOut, DishOut
from app.schemas.caterers import CatererPublic, ClientConfig
from app.schemas.logistics import AvailabilityOut, DeliveryCity
from app.schemas.orders import OrderCreated, OrderDetails
from app.services import availability, orders

router = APIRouter(prefix="/api")


@router.get("/config", response_model=ClientConfig)
def get_client_config():
    # Only values safe for a browser. The service-role key must never appear here.
    settings = get_settings()
    return ClientConfig(
        supabase_url=settings.supabase_url,
        supabase_anon_key=settings.supabase_anon_key,
        storage_public_url=public_storage_url(),
    )


@router.get("/allergens", response_model=list[AllergenOut])
def get_allergens(session: SessionDep):
    return list_allergens(session)


def _caterer(slug: str, session: SessionDep) -> Caterer:
    caterer = get_active_caterer_by_slug(session, slug)
    if caterer is None:
        raise not_found()
    return caterer


CatererDep = Annotated[Caterer, Depends(_caterer)]


def _scope(caterer: CatererDep) -> CatererScope:
    return CatererScope(caterer.id)


ScopeDep = Annotated[CatererScope, Depends(_scope)]


@router.get("/c/{slug}", response_model=CatererPublic)
def get_caterer(caterer: CatererDep):
    return caterer


@router.get("/c/{slug}/catalog/categories", response_model=list[CategoryOut])
def list_categories(session: SessionDep, scope: ScopeDep):
    categories = CategoryRepository(session, scope).list_all()
    return [category for category in categories if category.is_active]


@router.get("/c/{slug}/catalog/dishes", response_model=list[DishOut])
def list_dishes(
    session: SessionDep,
    scope: ScopeDep,
    category_id: UUID | None = None,
    vegetarian: bool = False,
    vegan: bool = False,
    kashrut: KashrutClass | None = None,
):
    dishes = DishRepository(session, scope).list_orderable()
    # A filter only matches confirmed values: unknown never passes as vegan or vegetarian.
    if category_id:
        dishes = [dish for dish in dishes if dish.category_id == category_id]
    if vegetarian:
        dishes = [d for d in dishes if d.dietary and d.dietary.is_vegetarian is True]
    if vegan:
        dishes = [d for d in dishes if d.dietary and d.dietary.is_vegan is True]
    if kashrut:
        dishes = [d for d in dishes if d.dietary and d.dietary.kashrut_class == kashrut]
    return dishes


@router.get("/c/{slug}/availability", response_model=AvailabilityOut)
def get_availability(session: SessionDep, scope: ScopeDep):
    today = availability.today()
    slots = TimeSlotRepository(session, scope).list_all()
    blocked = BlockedDateRepository(session, scope).list_all()
    return AvailabilityOut(
        earliest_date=today,
        blocked_dates=[item.date for item in blocked if item.date >= today],
        slots=[slot for slot in slots if slot.is_active],
    )


@router.get("/c/{slug}/delivery-cities", response_model=list[DeliveryCity])
def list_delivery_cities(session: SessionDep, scope: ScopeDep):
    zones = DeliveryZoneRepository(session, scope).list_all()
    cities = [
        DeliveryCity(city=city, fee=zone.fee)
        for zone in zones
        if zone.is_active
        for city in zone.cities
    ]
    return sorted(cities, key=lambda item: item.city)


@router.post("/c/{slug}/orders", response_model=OrderCreated, status_code=201)
def create_order(data: OrderDetails, session: SessionDep, caterer: CatererDep):
    return orders.create_order(session, caterer, data)
