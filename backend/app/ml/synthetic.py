"""Made-up leads for building and testing the training pipeline before real data exists.

shortcut: the outcome follows a rule invented here, so scores trained on it say nothing about
real customers; retrain with `--source db` once there are enough real orders.
"""

import numpy as np

from app.services.leads import EVENT_TYPE_FEATURES, FEATURES

# Invented effect of each input on the log-odds of submitting the order.
EFFECTS = {
    "has_phone": 1.1,
    "is_delivery": 0.3,
    "has_children": 0.2,
    "dietary_share": -0.6,
    "type_wedding": -0.8,
    "type_company": 0.6,
    "type_shabbat": 0.5,
}
BASE_LOG_ODDS = 0.4
GUESTS_EFFECT = -0.004  # per guest: big events shop around more
DAYS_EFFECT = -0.012  # per day until the event: far-off events are less urgent


# Measured over 3 seeds: at 2,000 rows test AUC swings 0.69-0.75 and the chosen model flips;
# at 50,000 it holds at 0.73-0.74 (the rule's own ceiling is 0.73) and the choice is stable.
DEFAULT_ROWS = 50_000


def rows(count: int = DEFAULT_ROWS, seed: int = 7) -> tuple[list[list[float]], list[int]]:
    """Feature rows in FEATURES order, and whether each lead purchased."""
    rng = np.random.default_rng(seed)
    types = [None, *EVENT_TYPE_FEATURES.values()]  # None is "other"
    data, labels = [], []
    for _ in range(count):
        row = dict.fromkeys(FEATURES, 0.0)
        row["guests"] = float(rng.integers(10, 300))
        row["has_children"] = float(rng.random() < 0.5)
        row["days_to_event"] = float(rng.integers(3, 180))
        row["is_delivery"] = float(rng.random() < 0.6)
        row["has_phone"] = float(rng.random() < 0.7)
        row["dietary_share"] = float(rng.beta(1, 6))
        if kind := types[rng.integers(len(types))]:
            row[kind] = 1.0
        log_odds = (
            BASE_LOG_ODDS
            + GUESTS_EFFECT * row["guests"]
            + DAYS_EFFECT * row["days_to_event"]
            + sum(effect * row[name] for name, effect in EFFECTS.items())
        )
        data.append([row[name] for name in FEATURES])
        labels.append(int(rng.random() < 1 / (1 + np.exp(-log_odds))))
    return data, labels
