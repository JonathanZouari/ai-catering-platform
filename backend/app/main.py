import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.orders import router as orders_router
from app.api.owner_orders import router as owner_orders_router
from app.core.config import get_settings
from app.db import get_db, migrate
from app.db.migrations import applied_versions
from app.repositories import supabase_orders

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.order_database_backend == "supabase":
        app.state.cloud_orders = supabase_orders.SupabaseOrders(
            supabase_orders.new_client(settings)
        )
        yield
        app.state.cloud_orders.close()
        return
    if settings.db_auto_migrate:
        migrate(settings.sqlite_file)
    yield


app = FastAPI(title="AI Catering Platform", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_request(_: Request, __: RequestValidationError) -> JSONResponse:
    # Do not echo submitted personal data or invalid Unicode into the error response.
    return JSONResponse(
        status_code=422,
        content={"detail": "פרטי הבקשה אינם תקינים. יש לבדוק את השדות ולנסות שוב."},
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/cloud-config")
def cloud_config() -> JSONResponse:
    """Expose only an explicitly configured publishable key, never server credentials."""
    settings = get_settings()
    key = settings.supabase_publishable_key or ""
    url = (settings.supabase_url or "").rstrip("/")
    configured = url.startswith("https://") and key.startswith("sb_publishable_")
    return JSONResponse(
        {
            "configured": configured,
            "url": url if configured else None,
            "publishableKey": key if configured else None,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health")
def health(request: Request) -> Any:
    settings = get_settings()
    env = settings.app_env
    if settings.order_database_backend == "supabase":
        database = {"engine": "supabase"}
        try:
            request.app.state.cloud_orders.catalog()
        except supabase_orders.CloudUnavailable:
            return JSONResponse(
                status_code=503, content={"status": "error", "env": env, "database": database}
            )
        return {"status": "ok", "env": env, "database": database}
    with contextmanager(get_db)() as conn:
        try:
            versions = applied_versions(conn)
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        except sqlite3.Error:
            versions, foreign_keys = [], False
    database = {
        "engine": "sqlite",
        "schema_version": versions[-1] if versions else None,
        "foreign_keys": foreign_keys,
    }
    if not versions or not foreign_keys:
        return JSONResponse(
            status_code=503, content={"status": "error", "env": env, "database": database}
        )
    return {"status": "ok", "env": env, "database": database}


# Mounted last so API routes take precedence.
app.include_router(orders_router)
app.include_router(owner_orders_router)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
