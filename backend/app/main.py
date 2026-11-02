from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.inquiries import router as inquiries_router
from app.core.config import get_settings

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="AI Catering Platform")
app.include_router(inquiries_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
