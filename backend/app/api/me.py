"""Signed-in customer: profile and own orders. Plus the public auth config for the browser."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.customer_auth import CustomerIdentity, require_customer
from app.core.db import get_db
from app.core.errors import AppError
from app.schemas import customers as s
from app.services import customers as svc

router = APIRouter(prefix="/api", tags=["customer"])


@router.get("/auth/config", response_model=s.AuthConfigOut)
def auth_config():
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_anon_key):
        raise AppError(503, "auth_unavailable", "Customer login is not configured")
    return s.AuthConfigOut(
        supabase_url=settings.supabase_url, supabase_anon_key=settings.supabase_anon_key
    )


@router.get("/me", response_model=s.MeOut)
def me(who: CustomerIdentity = Depends(require_customer), db: Session = Depends(get_db)):
    return svc.me(db, who)


@router.put("/me", response_model=s.MeOut)
def save_profile(
    data: s.ProfileIn,
    who: CustomerIdentity = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return svc.save_profile(db, who, data)


@router.get("/me/orders", response_model=list[s.MyOrderOut])
def my_orders(who: CustomerIdentity = Depends(require_customer), db: Session = Depends(get_db)):
    return svc.my_orders(db, who)
