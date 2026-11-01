from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import CatererScope
from app.models import QuantityRule
from app.models.enums import CategoryType
from app.repositories.orders import get_quantity_rules
from app.schemas.catalog import QuantityRuleOut, QuantityRuleSet


def list_rules(session: Session, scope: CatererScope) -> list[QuantityRuleOut]:
    rules = get_quantity_rules(session, scope.caterer_id)
    return [
        QuantityRuleOut(
            category_type=category_type,
            portions_per_adult=rule.portions_per_adult,
            portions_per_child=rule.portions_per_child,
            is_default=rule.caterer_id is None,
        )
        for category_type, rule in rules.items()
    ]


def _own_rule(
    session: Session, scope: CatererScope, category_type: CategoryType
) -> QuantityRule | None:
    return session.scalar(
        select(QuantityRule).where(
            QuantityRule.caterer_id == scope.caterer_id,
            QuantityRule.category_type == category_type,
        )
    )


def set_rule(
    session: Session, scope: CatererScope, category_type: CategoryType, data: QuantityRuleSet
) -> None:
    rule = _own_rule(session, scope, category_type)
    if rule is None:
        rule = QuantityRule(caterer_id=scope.caterer_id, category_type=category_type)
        session.add(rule)
    rule.portions_per_adult = data.portions_per_adult
    rule.portions_per_child = data.portions_per_child
    session.commit()


def revert_rule(session: Session, scope: CatererScope, category_type: CategoryType) -> None:
    """The platform default applies again once the caterer's own rule is gone."""
    rule = _own_rule(session, scope, category_type)
    if rule is not None:
        session.delete(rule)
        session.commit()
