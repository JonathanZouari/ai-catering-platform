from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.tenancy import CatererScope
from app.models.base import TenantMixin


class ScopedRepository[ModelT: TenantMixin]:
    """Data access for tenant tables. The scope is required, so no query can skip it."""

    model: type[ModelT]
    default_order: tuple = ()

    def __init__(self, session: Session, scope: CatererScope) -> None:
        self.session = session
        self.scope = scope

    def _select(self) -> Select[tuple[ModelT]]:
        return select(self.model).where(self.model.caterer_id == self.scope.caterer_id)

    def get(self, entity_id: UUID) -> ModelT | None:
        return self.session.scalar(self._select().where(self.model.id == entity_id))

    def list_all(self) -> Sequence[ModelT]:
        return self.session.scalars(self._select().order_by(*self.default_order)).all()

    def add(self, entity: ModelT) -> ModelT:
        entity.caterer_id = self.scope.caterer_id
        self.session.add(entity)
        return entity

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)
