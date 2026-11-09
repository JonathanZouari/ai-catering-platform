from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.errors import AppError

BUCKET = "caterer-assets"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

_IMAGE_SIGNATURES = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg"}
_PDF_SIGNATURE = b"%PDF-"
_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "pdf": "application/pdf",
}


class Storage(Protocol):
    def upload(self, path: str, content: bytes, content_type: str) -> None: ...


class SupabaseStorage:
    def upload(self, path: str, content: bytes, content_type: str) -> None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise AppError(503, "storage_unavailable", "העלאת קבצים אינה זמינה כרגע")
        base = settings.supabase_url.rstrip("/")
        response = httpx.post(
            f"{base}/storage/v1/object/{BUCKET}/{path}",
            content=content,
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": content_type,
            },
            timeout=30,
        )
        if response.is_error:
            raise AppError(502, "storage_failed", "העלאת הקובץ נכשלה, נסו שוב")


def get_storage() -> Storage:
    return SupabaseStorage()


def public_storage_url() -> str | None:
    supabase_url = get_settings().supabase_url
    if not supabase_url:
        return None
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/{BUCKET}"


def detect_file_type(content: bytes, *, allow_pdf: bool = False) -> str:
    """Return the file extension from its bytes. The client's claimed type isn't trusted."""
    for signature, extension in _IMAGE_SIGNATURES.items():
        if content.startswith(signature):
            return extension
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if allow_pdf and content.startswith(_PDF_SIGNATURE):
        return "pdf"
    raise AppError(422, "unsupported_file", "סוג הקובץ אינו נתמך")


def content_type_for(extension: str) -> str:
    return _CONTENT_TYPES[extension]
