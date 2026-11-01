from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.repositories.base import ScopedRepository
from app.schemas.base import PatchModel


def commit_or_conflict(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise conflict(message) from exc


def get_or_404[ModelT](repo: ScopedRepository[ModelT], entity_id: UUID) -> ModelT:
    entity = repo.get(entity_id)
    if entity is None:
        raise not_found()
    return entity


def apply_patch(entity: Any, data: PatchModel, skip: Iterable[str] = ()) -> None:
    for field, value in data.model_dump(exclude_unset=True, exclude=set(skip)).items():
        setattr(entity, field, value)
