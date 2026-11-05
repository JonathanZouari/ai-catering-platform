import datetime as dt
import uuid

from pydantic import BaseModel

from app.schemas.catalog import Name
from app.schemas.orders import Phone


class CustomerOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    avatar_url: str | None  # signed, expires in 5 minutes


class CustomerPatch(BaseModel):
    full_name: Name | None = None
    phone: Phone | None = None


class OrderFileOut(BaseModel):
    id: uuid.UUID
    original_name: str
    content_type: str
    size_bytes: int
    uploaded_by: str
    created_at: dt.datetime
    url: str  # signed, expires in 5 minutes
