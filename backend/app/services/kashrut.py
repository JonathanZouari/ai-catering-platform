from app.models import Dish
from app.models.enums import KashrutClass, KashrutMixingRule
from app.schemas.orders import KashrutCheck


def check_order(dishes: list[Dish], rule: KashrutMixingRule) -> KashrutCheck:
    classes = [dish.dietary.kashrut_class if dish.dietary else None for dish in dishes]
    mixed = KashrutClass.MEAT in classes and KashrutClass.DAIRY in classes
    status = "ok"
    if mixed:
        status = "blocked" if rule == KashrutMixingRule.BLOCK else "warn"
    # An unknown dish could still mix, so it's reported, never treated as fine.
    return KashrutCheck(status=status, has_unknown=None in classes)
