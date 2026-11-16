from collections.abc import Iterator

import httpx
from fastapi import HTTPException

from app.core.config import get_settings

TIMEOUT_SECONDS = 10


def get_supabase() -> Iterator[httpx.Client]:
    """FastAPI dependency: an HTTP client for the Supabase project's APIs.

    It carries only the publishable key. Each call adds the signed-in user's own token, so
    row level security decides what the call can read. The service-role key is never used.
    """
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_publishable_key):
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    with httpx.Client(
        base_url=settings.supabase_url,
        headers={"apikey": settings.supabase_publishable_key},
        timeout=TIMEOUT_SECONDS,
    ) as client:
        yield client
