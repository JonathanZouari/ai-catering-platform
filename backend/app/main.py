from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, orders, public
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.headers import register_security_headers

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app() -> FastAPI:
    settings = get_settings()
    settings.require_deployment_settings()
    closed = {"docs_url": None, "redoc_url": None, "openapi_url": None}

    app = FastAPI(title="AI Catering Platform", **(closed if settings.is_deployed else {}))
    register_error_handlers(app)
    register_security_headers(app)
    app.include_router(public.router)
    app.include_router(admin.router)
    app.include_router(orders.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/c/{slug}", include_in_schema=False)
    @app.get("/c/{slug}/", include_in_schema=False)
    def customer_page(slug: str) -> FileResponse:
        # One page for every caterer. It loads the caterer from the slug in its URL.
        return FileResponse(FRONTEND_DIR / "customer" / "index.html")

    # Mounted last so API routes take precedence.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()
