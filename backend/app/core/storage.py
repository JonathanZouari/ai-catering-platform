"""Supabase Storage for dish photos (ARCHITECTURE: server-side only, service-role key).

The bucket is public-read (dish photos are on the public menu); writes need the service-role
key, which never leaves the server.
"""

import httpx

from app.core.config import get_settings
from app.core.errors import AppError

BUCKET = "dish-images"


def _base() -> tuple[str, str]:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise AppError(503, "storage_unavailable", "Image storage is not configured")
    return settings.supabase_url.rstrip("/"), settings.supabase_service_role_key


def public_url(path: str) -> str | None:
    url = get_settings().supabase_url
    return f"{url.rstrip('/')}/storage/v1/object/public/{BUCKET}/{path}" if url else None


def upload(path: str, data: bytes, content_type: str) -> None:
    base, key = _base()
    try:
        response = httpx.post(
            f"{base}/storage/v1/object/{BUCKET}/{path}",
            content=data,
            headers={"Authorization": f"Bearer {key}", "apikey": key, "Content-Type": content_type},
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise AppError(502, "storage_failed", "Could not store the image") from exc
    if response.is_error:
        raise AppError(502, "storage_failed", "Could not store the image")


def delete(path: str) -> bool:
    """Best effort: a leftover file costs storage, never correctness."""
    base, key = _base()
    try:
        response = httpx.delete(
            f"{base}/storage/v1/object/{BUCKET}/{path}",
            headers={"Authorization": f"Bearer {key}", "apikey": key},
            timeout=15,
        )
    except httpx.HTTPError:
        return False
    return not response.is_error
