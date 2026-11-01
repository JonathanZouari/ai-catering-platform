from app.models import BlockedDate, DeliveryZone, TimeSlot
from app.repositories.base import ScopedRepository


class DeliveryZoneRepository(ScopedRepository[DeliveryZone]):
    model = DeliveryZone
    default_order = (DeliveryZone.name,)


class TimeSlotRepository(ScopedRepository[TimeSlot]):
    model = TimeSlot
    default_order = (TimeSlot.fulfillment_type, TimeSlot.weekday, TimeSlot.start_time)


class BlockedDateRepository(ScopedRepository[BlockedDate]):
    model = BlockedDate
    default_order = (BlockedDate.date,)
