from typing import BinaryIO
from uuid import UUID, uuid4

from app.core.errors import AppError
from app.core.storage import MAX_UPLOAD_BYTES, Storage, content_type_for, detect_file_type
from app.core.tenancy import CatererScope


def store_upload(
    storage: Storage,
    scope: CatererScope,
    folder: str,
    file: BinaryIO,
    *,
    allow_pdf: bool = False,
) -> str:
    """Validate and store a file under the caterer's own prefix. Returns its object path."""
    content = file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise AppError(413, "file_too_large", "הקובץ גדול מדי (עד 5MB)")
    extension = detect_file_type(content, allow_pdf=allow_pdf)
    path = _object_path(scope.caterer_id, folder, extension)
    storage.upload(path, content, content_type_for(extension))
    return path


def _object_path(caterer_id: UUID, folder: str, extension: str) -> str:
    return f"{caterer_id}/{folder}/{uuid4()}.{extension}"
