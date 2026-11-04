import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.orders import router as orders_router
from app.core.config import get_settings
from app.db import get_db, migrate
from app.db.migrations import applied_versions

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.db_auto_migrate:
        migrate(settings.sqlite_file)
    yield


app = FastAPI(title="AI Catering Platform", lifespan=lifespan)


@app.get("/health")
def health(conn: Annotated[sqlite3.Connection, Depends(get_db)]) -> Any:
    env = get_settings().app_env
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
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
