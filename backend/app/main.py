from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import availability, catalog, delivery, me, orders
from app.api.admin import availability as admin_availability
from app.api.admin import catalog as admin_catalog
from app.api.admin import delivery as admin_delivery
from app.api.admin import orders as admin_orders
from app.api.admin import settings as admin_settings
from app.core.config import get_settings
from app.core.errors import install_error_handlers

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="AI Catering Platform")
install_error_handlers(app)
app.include_router(catalog.router)
app.include_router(admin_catalog.router)
app.include_router(availability.router)
app.include_router(admin_availability.router)
app.include_router(admin_orders.router)
app.include_router(admin_settings.router)
app.include_router(me.router)
app.include_router(orders.router)
app.include_router(delivery.router)
app.include_router(admin_delivery.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
