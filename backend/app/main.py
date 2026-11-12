from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.catalog import router as catalog_router
from app.api.config import router as config_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="AI Catering Platform")
install_error_handlers(app)
app.include_router(catalog_router)
app.include_router(admin_router)
app.include_router(config_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
