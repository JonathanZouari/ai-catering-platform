"""Purchase probability for a lead, from the trained logistic-regression numbers.

The model file holds plain numbers (scaling, coefficients, intercept), so scoring needs no
scikit-learn at runtime and never unpickles anything. Retrain with scripts/train_lead_model.py.
"""

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

MODEL_PATH = Path(__file__).resolve().parents[2] / "data" / "lead_model.json"


@lru_cache
def load_model(path: Path = MODEL_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def purchase_probability(lead: dict[str, Any], model: dict[str, Any] | None = None) -> float:
    """Probability (0 to 1) that this lead orders. Unknown categories add nothing."""
    m = model or load_model()
    z = m["intercept"]
    for name, p in m["numeric"].items():
        z += p["coef"] * (float(lead[name]) - p["mean"]) / p["scale"]
    for name, weights in m["categorical"].items():
        z += weights.get(str(lead[name]), 0.0)
    return 1 / (1 + math.exp(-z))


def is_hot(probability: float, model: dict[str, Any] | None = None) -> bool | None:
    """True above the chosen threshold. None while no threshold has been chosen."""
    threshold = (model or load_model()).get("threshold")
    return None if threshold is None else probability >= threshold
