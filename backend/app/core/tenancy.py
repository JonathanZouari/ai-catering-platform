from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CatererScope:
    """The caterer a request runs as. Only ever built server-side (ADR 0005)."""

    caterer_id: UUID
