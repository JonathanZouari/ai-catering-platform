from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, orders, public
from app.core.config import get_settings
from app.core.errors import register_error_handlers

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="AI Catering Platform")
register_error_handlers(app)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(orders.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


@app.get("/c/{slug}", include_in_schema=False)
@app.get("/c/{slug}/", include_in_schema=False)
def customer_page(slug: str) -> FileResponse:
    # One page for every caterer. It loads the caterer from the slug in its URL.
    return FileResponse(FRONTEND_DIR / "customer" / "index.html")


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
