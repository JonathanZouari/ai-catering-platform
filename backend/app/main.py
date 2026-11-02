from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  registers all tables on Base
from app.core.config import get_settings
from app.core.db import Base, engine

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# shortcut: create_all only adds missing tables; use migrations once tables hold real data.
Base.metadata.create_all(engine)

app = FastAPI(title="AI Catering Platform")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
