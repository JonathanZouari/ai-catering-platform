from fastapi import APIRouter

from app.api.deps import ScopeDep, SessionDep
from app.models.enums import CategoryType
from app.schemas.catalog import QuantityRuleOut, QuantityRuleSet
from app.services import quantity_rules

router = APIRouter(prefix="/quantity-rules")


@router.get("", response_model=list[QuantityRuleOut])
def list_rules(session: SessionDep, scope: ScopeDep):
    return quantity_rules.list_rules(session, scope)


@router.put("/{category_type}", response_model=list[QuantityRuleOut])
def set_rule(
    category_type: CategoryType, data: QuantityRuleSet, session: SessionDep, scope: ScopeDep
):
    quantity_rules.set_rule(session, scope, category_type, data)
    return quantity_rules.list_rules(session, scope)


@router.delete("/{category_type}", response_model=list[QuantityRuleOut])
def revert_rule(category_type: CategoryType, session: SessionDep, scope: ScopeDep):
    quantity_rules.revert_rule(session, scope, category_type)
    return quantity_rules.list_rules(session, scope)
