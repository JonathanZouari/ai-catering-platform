"""Synthetic closed-lead history for building and testing the lead score. NOT real data.

The outcome is drawn from TRUE_EFFECTS below, so a correct pipeline must recover them.
These effects are invented for testing; they say nothing about real customers.
No names, phones or emails are generated: only the fields the model uses.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta

from app.services.lead_scoring import FEATURES, lead_features

TRUE_INTERCEPT = -1.2
TRUE_EFFECTS: dict[str, float] = {
    "src_ai_chat": 0.5,
    "src_manual": 0.3,
    "has_email": 0.4,
    "returning_customer": 1.2,
    "repeat_contact": 0.6,
    "date_known": 0.8,
    "short_notice": -0.9,
    "date_passed": -2.0,
    "guests_known": 0.3,
    "large_event": -1.6,
    "guests_log": 0.0,  # deliberately no effect: the model should find ~0
    "has_message": 0.3,
}
assert set(TRUE_EFFECTS) == set(FEATURES)  # noqa: S101 - fail fast if the feature list changes


def generate(n: int = 600, seed: int = 7) -> tuple[list[dict], list[int], list[int]]:
    """Return (lead rows, prior-same-phone counts, converted labels). Deterministic per seed."""
    rng = random.Random(seed)  # noqa: S311 - synthetic data, not security
    start = date(2025, 1, 1)
    rows, priors, labels = [], [], []
    for i in range(n):
        created = start + timedelta(days=rng.randrange(0, 600))
        days_ahead = rng.choice([None, None] + [rng.randint(-5, 120) for _ in range(6)])
        guests = rng.choice([None, rng.randint(8, 60), rng.randint(20, 120), rng.randint(100, 400)])
        row = {
            "id": i,
            "created_at": created.isoformat(),
            "source": rng.choices(["landing_form", "ai_chat", "manual"], [0.6, 0.25, 0.15])[0],
            "email": "x@example.com" if rng.random() < 0.6 else None,
            "customer_id": "c" if rng.random() < 0.15 else None,
            "event_date": (created + timedelta(days=days_ahead)).isoformat()
            if days_ahead is not None
            else None,
            "guest_count": guests,
            "message": "x" if rng.random() < 0.5 else None,
        }
        prior = 1 if rng.random() < 0.1 else 0
        feats = lead_features(row, prior)
        z = TRUE_INTERCEPT + sum(TRUE_EFFECTS[f] * feats[f] for f in FEATURES)
        labels.append(int(rng.random() < 1 / (1 + math.exp(-z))))
        rows.append(row)
        priors.append(prior)
    return rows, priors, labels
