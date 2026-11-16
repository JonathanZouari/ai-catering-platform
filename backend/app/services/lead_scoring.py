"""Purchase probability of a lead, from a logistic-regression model.

The model file is written by scripts/train_lead_model.py. It was trained on synthetic
leads, so the probabilities are demo values until it is retrained on real outcomes.
"""

import json
from collections.abc import Mapping
from functools import lru_cache
from math import exp
from pathlib import Path

MODEL_FILE = Path(__file__).with_name("lead_model.json")


@lru_cache
def load_model() -> dict:
    return json.loads(MODEL_FILE.read_text(encoding="utf-8"))


def features(lead: Mapping) -> dict[str, float]:
    """The model inputs of a lead. Training and scoring both go through here.

    `lead_days` is the number of days between the inquiry and the event.
    """
    return {
        "guests": float(lead["guests"]),
        "lead_days": float(lead["lead_days"]),
        "budget_per_guest": float(lead["budget_per_guest"]),
        "is_returning": 1.0 if lead["is_returning"] else 0.0,
        f"event_type={lead['event_type']}": 1.0,
        f"source={lead['source']}": 1.0,
    }


def purchase_probability(lead: Mapping, model: Mapping | None = None) -> float:
    """Estimated chance, between 0 and 1, that the lead ends in a purchase.

    A category the model never saw in training adds nothing to the score.
    """
    model = model or load_model()
    coefficients = model["coefficients"]
    score = model["intercept"] + sum(
        coefficients.get(name, 0.0) * value for name, value in features(lead).items()
    )
    # Two forms of the same function, so exp never overflows on an extreme score.
    if score >= 0:
        return 1 / (1 + exp(-score))
    return exp(score) / (1 + exp(score))
