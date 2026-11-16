from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="AI Catering Platform")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


@app.get("/api/public-config")
def public_config() -> dict[str, str]:
    """Values the browser needs. Only the publishable key belongs here, never a secret."""
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_publishable_key):
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    return {
        "supabaseUrl": settings.supabase_url,
        "supabasePublishableKey": settings.supabase_publishable_key,
    }


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
