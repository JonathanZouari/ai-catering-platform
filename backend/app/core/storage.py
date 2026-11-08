"""Supabase Storage over its REST API, with the secret key (server-side only)."""

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.http import client

DISH_IMAGES = "dish-images"
SIGNED_QUOTES = "signed-quotes"


def _base() -> tuple[str, dict[str, str]]:
    s = get_settings()
    if not (s.supabase_url and s.supabase_secret_key):
        raise HTTPException(status_code=503, detail="Supabase Storage is not configured")
    key = s.supabase_secret_key
    return f"{s.supabase_url}/storage/v1", {"apikey": key, "Authorization": f"Bearer {key}"}


def upload(bucket: str, path: str, data: bytes, content_type: str) -> None:
    base, headers = _base()
    response = client().post(
        f"{base}/object/{bucket}/{path}",
        headers={**headers, "Content-Type": content_type},
        content=data,
        timeout=60,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Upload to storage failed")


def remove(bucket: str, paths: list[str]) -> None:
    """Best effort: a leftover object costs storage, never correctness."""
    if not paths:
        return
    base, headers = _base()
    try:
        client().request(
            "DELETE",
            f"{base}/object/{bucket}",
            headers=headers,
            json={"prefixes": paths},
            timeout=30,
        )
    except httpx.HTTPError:
        pass


def public_url(bucket: str, path: str | None) -> str | None:
    url = get_settings().supabase_url
    if not (path and url):
        return None
    return f"{url}/storage/v1/object/public/{bucket}/{path}"
