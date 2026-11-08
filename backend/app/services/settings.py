"""Business settings (single row). Missing row = defaults, created on first read."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.settings import BusinessSettings
from app.schemas.settings import SettingsIn


def get(db: Session) -> BusinessSettings:
    row = db.get(BusinessSettings, 1)
    if row is None:
        row = BusinessSettings(id=1)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:  # created concurrently
            db.rollback()
            row = db.get(BusinessSettings, 1)
    return row


def update(db: Session, data: SettingsIn) -> BusinessSettings:
    row = get(db)
    row.child_portion = data.child_portion
    row.lead_days = data.lead_days
    row.assistant_daily_limit = data.assistant_daily_limit
    row.kashrut_certificate = data.kashrut_certificate or None
    row.default_delivery_fee = data.default_delivery_fee
    db.commit()
    db.refresh(row)  # return what was stored (numeric(3,2)), not the request's Decimal
    return row
