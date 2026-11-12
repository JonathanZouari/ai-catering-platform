from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.dishes import router as dishes_router
from app.api.orders import router as orders_router
from app.core.config import get_settings
from app.db import init_db
from app.services.orders import ApiError

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db().close()  # creates catering.db and tables if missing
    yield


app = FastAPI(title="AI Catering Platform", lifespan=lifespan)

app.include_router(dishes_router)
app.include_router(orders_router)


# Error format from docs/API_CONTRACTS.md: { "error": { code, message, details } }
@app.exception_handler(ApiError)
async def api_error(_: Request, exc: ApiError) -> JSONResponse:
    error = {"code": exc.code, "message": exc.message, "details": exc.details}
    return JSONResponse({"error": error}, status_code=exc.status)


@app.exception_handler(RequestValidationError)
async def request_invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
    error = {"code": "validation_error", "message": "הנתונים שנשלחו אינם תקינים", "details": {}}
    return JSONResponse({"error": error}, status_code=422)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": get_settings().app_env}


# Mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
