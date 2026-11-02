import runpy
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import catalog
from app.core.config import get_settings

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# Rebuild the course SQLite DB from schema + seed on every start, so a fresh clone or deploy works.
runpy.run_path(str(catalog.DB_PATH.parent / "build_db.py"))

app = FastAPI(title="AI Catering Platform")
app.include_router(catalog.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
