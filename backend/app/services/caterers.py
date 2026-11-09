from sqlalchemy.orm import Session

from app.models import Caterer, CatererUser
from app.schemas.caterers import CatererCreate


def create_caterer(session: Session, data: CatererCreate) -> Caterer:
    """Create a caterer and link its first login. Used by the onboarding script."""
    caterer = Caterer(slug=data.slug, name=data.name)
    session.add(caterer)
    session.flush()
    session.add(CatererUser(caterer_id=caterer.id, auth_user_id=data.auth_user_id))
    session.commit()
    return caterer
