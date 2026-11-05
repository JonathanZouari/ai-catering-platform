import re
import uuid
from typing import NamedTuple

import httpx
from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import AppError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024  # order files (images or PDF)
SIGNED_URL_SECONDS = 300
# Detected from magic bytes, never from the client's filename or content type.
_EXT = {"jpeg": "jpg", "png": "png", "webp": "webp", "pdf": "pdf"}
_TYPES = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "pdf": "application/pdf",
}


def detect_image(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def detect_file(data: bytes) -> str | None:
    return "pdf" if data.startswith(b"%PDF-") else detect_image(data)


def content_type(kind: str) -> str:
    return _TYPES[kind]


def read_upload(file: UploadFile, *, pdf: bool = False) -> tuple[bytes, str]:
    """Bounded read plus magic-byte check; returns (data, kind). SVG/HTML/empty are rejected."""
    limit = MAX_FILE_BYTES if pdf else MAX_IMAGE_BYTES
    data = file.file.read(limit + 1)  # never buffer more than the cap
    if len(data) > limit:
        raise AppError(413, f"File must be {limit // 1024 // 1024} MB or smaller")
    kind = (detect_file if pdf else detect_image)(data)
    if kind is None:  # also covers empty files
        raise AppError(
            415, "Only JPEG, PNG, WebP" + (" or PDF" if pdf else "") + " files are accepted"
        )
    return data, kind


def clean_name(name: str | None) -> str:
    """Display-only name: no path, no control characters, at most 100 characters."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = "".join(c for c in base if c.isprintable()).strip()
    return base[:100] or "file"


def _headers() -> dict:
    key = get_settings().supabase_service_role_key
    # New sb_secret_ keys go in apikey only; legacy JWT service-role keys also need Bearer.
    return {"apikey": key, **({"Authorization": f"Bearer {key}"} if key.startswith("eyJ") else {})}


def _configured():
    s = get_settings()
    if not (s.supabase_url and s.supabase_service_role_key):
        raise AppError(503, "Storage is not configured")
    return s


def upload_to_supabase(data: bytes, kind: str, bucket: str | None = None, prefix: str = "") -> str:
    """Upload with a server-generated name (prefix is a server-side folder); returns the path."""
    s = _configured()
    bucket = bucket or s.storage_bucket
    name = f"{prefix}{uuid.uuid4()}.{_EXT[kind]}"
    response = httpx.post(
        f"{s.supabase_url}/storage/v1/object/{bucket}/{name}",
        content=data,
        headers={**_headers(), "Content-Type": _TYPES[kind]},
        timeout=20,
    )
    if response.status_code >= 400:
        raise AppError(502, "File upload failed")
    return name


def _already_gone(response: httpx.Response) -> bool:
    """Storage reports a missing object as 404, or as 400 with statusCode 404 in the body."""
    if response.status_code == 404:
        return True
    try:
        return str(response.json().get("statusCode")) == "404"
    except (ValueError, AttributeError):
        return False


def delete_from_supabase(bucket: str, path: str) -> None:
    s = _configured()
    response = httpx.delete(
        f"{s.supabase_url}/storage/v1/object/{bucket}/{path}", headers=_headers(), timeout=20
    )
    if response.status_code >= 400 and not _already_gone(response):
        raise AppError(502, "File delete failed")


def sign_url(bucket: str, path: str) -> str:
    """Short-lived link to a private object; generated here so the browser never holds a key."""
    s = _configured()
    response = httpx.post(
        f"{s.supabase_url}/storage/v1/object/sign/{bucket}/{path}",
        json={"expiresIn": SIGNED_URL_SECONDS},
        headers=_headers(),
        timeout=20,
    )
    if response.status_code >= 400:
        raise AppError(502, "Could not create a file link")
    return f"{s.supabase_url}/storage/v1{response.json()['signedURL']}"


class Storage(NamedTuple):
    upload: object
    delete: object
    sign: object


def quiet_delete(storage: Storage, bucket: str, path: str) -> None:
    try:
        storage.delete(bucket, path)
    except AppError:
        pass  # shortcut: an unreachable private orphan is leaked; add a sweep job if it matters


def safe_sign(storage: Storage, bucket: str, path: str | None) -> str | None:
    """A signing failure must not turn a saved change into an error: the link is just absent."""
    if not path:
        return None
    try:
        return storage.sign(bucket, path)
    except AppError:
        return None


def get_uploader():
    return upload_to_supabase


def get_storage() -> Storage:
    return Storage(upload_to_supabase, delete_from_supabase, sign_url)
