"""Lead conversion score: logistic regression over facts known when the lead arrives.

Standard library only. Features never look at status, notes or anything that happens after the
lead is created, so training on closed leads does not leak the outcome.
A score is a prioritisation hint for the owner, not a prediction to show customers.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

MODEL_PATH = Path(__file__).with_name("lead_model.json")
MAX_GUESTS = 5000
LARGE_EVENT_GUESTS = 150
SHORT_NOTICE_DAYS = 7

# Owner-facing "why" labels: (when the lead has it, when it does not).
FEATURE_LABELS: dict[str, tuple[str, str]] = {
    "src_ai_chat": ("הגיע דרך העוזר החכם", "לא הגיע דרך העוזר החכם"),
    "src_manual": ("הוזן ידנית על ידי העסק", "לא הוזן ידנית"),
    "has_email": ("השאיר כתובת מייל", "לא השאיר מייל"),
    "returning_customer": ("לקוח קיים", "לקוח חדש"),
    "repeat_contact": ("פנה יותר מפעם אחת", "פנייה ראשונה"),
    "date_known": ("ציין תאריך אירוע", "לא ציין תאריך אירוע"),
    "short_notice": ("האירוע בעוד פחות משבוע", "יש מספיק זמן עד האירוע"),
    "date_passed": ("תאריך האירוע כבר עבר", "תאריך האירוע עוד לפניו"),
    "guests_known": ("ציין מספר אורחים", "לא ציין מספר אורחים"),
    "large_event": (f"מעל {LARGE_EVENT_GUESTS} אורחים", f"עד {LARGE_EVENT_GUESTS} אורחים"),
    "guests_log": ("מספר האורחים", "מספר האורחים"),
    "has_message": ("כתב הודעה", "לא כתב הודעה"),
}
FEATURES: tuple[str, ...] = tuple(FEATURE_LABELS)
# Meaningless when the parent fact is missing (e.g. "up to 150 guests" when no count was given).
REQUIRES: dict[str, str] = {
    "short_notice": "date_known",
    "date_passed": "date_known",
    "large_event": "guests_known",
    "guests_log": "guests_known",
}


def _to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def lead_features(lead: Mapping[str, Any], prior_same_phone: int = 0) -> dict[str, float]:
    """Features for one lead row (as stored in `leads`). Missing optional fields are fine."""
    created = _to_date(lead.get("created_at"))
    if created is None:
        raise ValueError("lead needs created_at")
    event = _to_date(lead.get("event_date"))
    days = (event - created).days if event else None

    guests = lead.get("guest_count")
    guests = int(guests) if isinstance(guests, int | float) and guests >= 1 else None
    if guests is not None:
        guests = min(guests, MAX_GUESTS)

    source = lead.get("source")
    return {
        "src_ai_chat": float(source == "ai_chat"),
        "src_manual": float(source == "manual"),
        "has_email": float(bool((lead.get("email") or "").strip())),
        "returning_customer": float(lead.get("customer_id") is not None),
        "repeat_contact": float(prior_same_phone > 0),
        "date_known": float(days is not None),
        "short_notice": float(days is not None and 0 <= days < SHORT_NOTICE_DAYS),
        "date_passed": float(days is not None and days < 0),
        "guests_known": float(guests is not None),
        "large_event": float(guests is not None and guests > LARGE_EVENT_GUESTS),
        "guests_log": math.log1p(guests) if guests is not None else 0.0,
        "has_message": float(bool((lead.get("message") or "").strip())),
    }


def prior_contacts(leads: Sequence[Mapping[str, Any]]) -> dict[Any, int]:
    """For each lead id, how many earlier leads share its phone."""
    seen: dict[str, int] = {}
    result: dict[Any, int] = {}
    for lead in sorted(leads, key=lambda r: str(r["created_at"])):
        phone = lead["phone"]
        result[lead["id"]] = seen.get(phone, 0)
        seen[phone] = seen.get(phone, 0) + 1
    return result


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


@dataclass(frozen=True)
class LeadModel:
    version: str
    intercept: float
    coefficients: dict[str, float]
    means: dict[str, float]
    trained_on_synthetic: bool
    metrics: dict[str, float]

    def probability(self, feats: Mapping[str, float]) -> float:
        z = self.intercept + sum(self.coefficients[f] * feats[f] for f in FEATURES)
        return _sigmoid(z)

    def reasons(self, feats: Mapping[str, float], top: int = 3) -> list[dict[str, Any]]:
        """Largest pushes away from an average lead, in owner-facing Hebrew."""
        impacts = [
            (f, self.coefficients[f] * (feats[f] - self.means[f]))
            for f in FEATURES
            if f not in REQUIRES or feats[REQUIRES[f]]
        ]
        impacts = [(f, v) for f, v in impacts if abs(v) >= 0.05]
        impacts.sort(key=lambda item: abs(item[1]), reverse=True)
        return [
            {
                "feature": f,
                "label": FEATURE_LABELS[f][0 if feats[f] > 0 else 1],
                "direction": "up" if v > 0 else "down",
                "impact": round(v, 3),
            }
            for f, v in impacts[:top]
        ]

    def save(self, path: Path = MODEL_PATH) -> None:
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n", "utf-8")

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> LeadModel:
        data = json.loads(path.read_text("utf-8"))
        if set(data["coefficients"]) != set(FEATURES):
            raise ValueError("model features do not match the code; retrain the model")
        return cls(**data)


# ---- Training (Newton / IRLS with L2, no third-party libraries)


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve a·x = b by Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            raise ValueError("singular matrix; add more varied training data")
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            factor = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def fit_logistic(
    rows: Sequence[Mapping[str, float]], labels: Sequence[int], l2: float = 1.0, max_iter: int = 50
) -> tuple[float, dict[str, float]]:
    """Return (intercept, coefficients). The intercept is not penalised."""
    if len(rows) != len(labels) or not rows:
        raise ValueError("need the same, non-zero number of rows and labels")
    if len(set(labels)) < 2:
        raise ValueError("need both converted and lost leads to train")
    x = [[1.0] + [row[f] for f in FEATURES] for row in rows]
    k = len(FEATURES) + 1
    beta = [0.0] * k
    for _ in range(max_iter):
        grad = [-l2 * beta[j] if j else 0.0 for j in range(k)]
        hess = [[(l2 if i == j and i else 0.0) for j in range(k)] for i in range(k)]
        for xi, yi in zip(x, labels, strict=True):
            p = _sigmoid(sum(b * v for b, v in zip(beta, xi, strict=True)))
            w = p * (1 - p)
            for i in range(k):
                grad[i] += (yi - p) * xi[i]
                for j in range(i, k):
                    hess[i][j] += w * xi[i] * xi[j]
        for i in range(k):
            for j in range(i):
                hess[i][j] = hess[j][i]
        step = _solve(hess, grad)
        beta = [b + s for b, s in zip(beta, step, strict=True)]
        if max(abs(s) for s in step) < 1e-8:
            break
    return beta[0], dict(zip(FEATURES, beta[1:], strict=True))


def auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Area under the ROC curve (Mann-Whitney, ties count half)."""
    pos = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    neg = [s for s, y in zip(scores, labels, strict=True) if y == 0]
    if not pos or not neg:
        raise ValueError("AUC needs both classes")
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def brier(probs: Sequence[float], labels: Sequence[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, labels, strict=True)) / len(labels)
