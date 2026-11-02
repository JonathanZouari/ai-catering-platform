from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.db import Base, engine
from app.models.customer import Customer  # noqa: F401  registers the table on Base

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# shortcut: create_all only adds missing tables; use migrations once tables hold real data.
Base.metadata.create_all(engine)

app = FastAPI(title="AI Catering Platform")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
