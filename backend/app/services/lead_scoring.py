"""Lead score: the estimated chance that a submitted request becomes a sale.

A transparent rule-based model: each signal adds log-odds to a base, and the sum goes through
a sigmoid. A missing input adds nothing and is reported as unknown, never as a bad sign.
Pure functions only, no database. The weights are starting values (OPEN_DECISIONS) and
the score is advisory: it never approves or rejects an order.
"""

import math
from dataclasses import dataclass, field

SCORE_VERSION = "rules-1"
BASE = -0.5  # log-odds of a lead with no signals at all
MAX_REASONS = 5


@dataclass(frozen=True)
class Features:
    """Numbers and flags only. No name, phone, email or address."""

    days_to_event: int | None = None
    guests: int | None = None
    total: float | None = None
    categories: int | None = None
    chat_messages: int | None = None
    proposals_accepted: int | None = None
    proposals_rejected: int | None = None
    has_email: bool | None = None
    delivery_resolved: bool | None = None
    kashrut_acknowledged: bool | None = None

    def as_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class Score:
    probability: float
    reasons: list[dict] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)


# (feature, Hebrew label used for "unknown")
LABELS = {
    "days_to_event": "זמן עד האירוע",
    "guests": "מספר סועדים",
    "categories": "מגוון המנות",
    "chat_messages": "שיחה עם העוזר",
    "has_email": "כתובת אימייל",
}


def _lead_time(days: int) -> tuple[str, float]:
    if days < 3:
        return "האירוע בעוד פחות מ-3 ימים", -0.8
    if 7 <= days <= 60:
        return "האירוע בטווח של שבוע עד חודשיים", 0.5
    if days > 180:
        return "האירוע רחוק, יותר מחצי שנה", -0.3
    return "", 0.0


def band(probability: float) -> str:
    if probability < 0.4:
        return "low"
    if probability < 0.65:
        return "medium"
    return "high"


def score(features: Features) -> Score:
    parts: list[tuple[str, float]] = []

    def add(label: str, points: float) -> None:
        if label and points:
            parts.append((label, points))

    if features.days_to_event is not None:
        add(*_lead_time(features.days_to_event))
    if features.guests is not None and features.guests >= 30:
        add("אירוע גדול, 30 סועדים ומעלה", 0.3)
    if features.categories is not None and features.categories >= 3:
        add("הזמנה מגוונת, 3 קטגוריות ומעלה", 0.4)
    if features.chat_messages is not None and 1 <= features.chat_messages <= 20:
        add("שוחח עם העוזר", 0.2)
    if (features.proposals_accepted or 0) > 0:
        add("אישר הצעות של העוזר", 0.3)
    elif (features.proposals_rejected or 0) > 0:
        add("דחה הצעות של העוזר", -0.2)
    if features.has_email:
        add("השאיר כתובת אימייל", 0.2)
    if features.delivery_resolved:
        add("כתובת המשלוח בתחום השירות", 0.1)
    if features.kashrut_acknowledged:
        add("אישר אזהרת כשרות", -0.1)

    total = BASE + sum(points for _, points in parts)
    probability = 1 / (1 + math.exp(-total))
    parts.sort(key=lambda part: abs(part[1]), reverse=True)
    unknown = [label for name, label in LABELS.items() if getattr(features, name) is None]
    return Score(
        probability=round(probability, 3),
        reasons=[{"label": label, "points": points} for label, points in parts[:MAX_REASONS]],
        unknown=unknown,
    )
