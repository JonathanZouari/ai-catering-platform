"""Lead scoring and revenue forecast.

A *lead* is a customer with no approved order yet: a prospect who never inquired, or a customer
whose orders are still draft / pending approval / rejected.

The model is a Laplace-smoothed Naive Bayes trained on every customer's first order
(label: approved vs. not approved). It is deliberately simple and explainable: each feature
contributes a log-odds term that we turn into a short Hebrew reason. The business rules around
it (recency, event date passed, order status) are explicit constants below, not learned.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

OPEN_STATUSES = ("draft", "pending_approval", "rejected")

# Multipliers applied on top of the model probability.
STATUS_FACTOR = {"pending_approval": 1.0, "draft": 1.0, "rejected": 0.25}
EVENT_PASSED_FACTOR = 0.05
PROSPECT_FACTOR = 0.5  # never inquired: weaker signal than someone who built an order
PROSPECT_HALF_LIFE_DAYS = 120  # interest in a bare sign-up fades quickly
PROSPECT_FLOOR = 0.02  # keeps old sign-ups rankable instead of collapsing to zero
SMOOTHING = 2.0

HOT_THRESHOLD = 0.6
WARM_THRESHOLD = 0.35

FEATURE_LABELS = {
    "city": "עיר",
    "has_email": "אימייל",
    "event_type": "סוג אירוע",
    "guests": "גודל האירוע",
    "fulfillment": "אספקה",
    "kashrut": "כשרות",
    "value": "גובה ההצעה",
}


def _guest_bucket(guests: int) -> str:
    if guests <= 20:
        return "עד 20"
    if guests <= 50:
        return "21-50"
    if guests <= 100:
        return "51-100"
    return "מעל 100"


def _value_bucket(total: float) -> str:
    if total < 3000:
        return "עד 3,000"
    if total < 6000:
        return "3,000-6,000"
    if total < 10000:
        return "6,000-10,000"
    return "מעל 10,000"


def _num(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _features(row: dict[str, str], *, with_order: bool) -> dict[str, str]:
    features = {
        "city": row["customer_city"] or "לא ידוע",
        "has_email": "יש" if row["email"] else "אין",
    }
    if with_order:
        features |= {
            "event_type": row["event_type"] or "אחר",
            "guests": _guest_bucket(int(_num(row["total_guests"]))),
            "fulfillment": "משלוח" if row["fulfillment_type"] == "delivery" else "איסוף",
            "kashrut": row["menu_kashrut"] or "לא ידוע",
            "value": _value_bucket(_num(row["total"])),
        }
    return features


class NaiveBayes:
    """Binary Naive Bayes over categorical features, with additive smoothing."""

    def __init__(self) -> None:
        self.positives = 0
        self.total = 0
        self._counts: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(lambda: [0, 0])
        )
        self._cardinality: dict[str, set[str]] = defaultdict(set)

    def fit(self, samples: list[tuple[dict[str, str], bool]]) -> NaiveBayes:
        for features, label in samples:
            self.total += 1
            self.positives += label
            for name, value in features.items():
                self._counts[name][value][int(label)] += 1
                self._cardinality[name].add(value)
        return self

    @property
    def base_rate(self) -> float:
        return self.positives / self.total if self.total else 0.5

    def _rate(self, name: str, value: str, label: bool) -> float:
        counts = self._counts[name][value]
        class_total = self.positives if label else self.total - self.positives
        k = len(self._cardinality[name]) + 1
        return (counts[int(label)] + SMOOTHING) / (class_total + SMOOTHING * k)

    def predict(self, features: dict[str, str]) -> tuple[float, dict[str, float]]:
        """Return P(approved) and the log-odds contribution of each feature."""
        prior = math.log(self.base_rate / (1 - self.base_rate))
        contributions = {
            name: math.log(self._rate(name, value, True) / self._rate(name, value, False))
            for name, value in features.items()
        }
        logit = prior + sum(contributions.values())
        return 1 / (1 + math.exp(-logit)), contributions


@dataclass
class Lead:
    customer_id: str
    full_name: str
    phone: str
    email: str
    city: str
    kind: str  # "prospect" | "open_order"
    order_status: str | None
    created_at: datetime
    event_type: str | None
    event_date: date | None
    guests: int | None
    quote_total: float | None
    probability: float
    tier: str
    expected_revenue: float
    days_to_event: int | None
    action: str
    reasons: list[str] = field(default_factory=list)


def _tier(probability: float) -> str:
    if probability >= HOT_THRESHOLD:
        return "hot"
    if probability >= WARM_THRESHOLD:
        return "warm"
    return "cold"


class LeadService:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._rows = rows
        by_customer: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            by_customer[row["customer_id"]].append(row)
        self._by_customer = by_customer

        first_orders = []
        approved_totals: list[float] = []
        for orders in by_customer.values():
            placed = sorted(
                (o for o in orders if o["order_id"]), key=lambda o: o["order_created_at"]
            )
            if placed:
                first_orders.append(placed[0])
            approved_totals += [_num(o["total"]) for o in placed if o["status"] == "approved"]
        self.model = NaiveBayes().fit(
            [(_features(o, with_order=True), o["status"] == "approved") for o in first_orders]
        )
        # Only the shared features (city, email) apply to prospects, so they get their own model.
        self.prospect_model = NaiveBayes().fit(
            [(_features(o, with_order=False), o["status"] == "approved") for o in first_orders]
        )
        self.avg_order_value = sum(approved_totals) / len(approved_totals) if approved_totals else 0

    @classmethod
    def from_csv(cls, path: str | Path) -> LeadService:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            return cls(list(csv.DictReader(handle)))

    # -- scoring -----------------------------------------------------------------------------

    def _reasons(self, contributions: dict[str, float], features: dict[str, str]) -> list[str]:
        ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        reasons = []
        for name, weight in ranked:
            if abs(weight) < 0.1:
                continue
            direction = "מעלה" if weight > 0 else "מורידה"
            reasons.append(f"{FEATURE_LABELS[name]}: {features[name]} ({direction} את הסיכוי)")
        return reasons

    def _score_customer(self, orders: list[dict[str, str]], as_of: date) -> Lead | None:
        head = orders[0]
        if any(o["status"] == "approved" for o in orders):
            return None
        created = datetime.fromisoformat(head["customer_created_at"])
        placed = sorted((o for o in orders if o["order_id"]), key=lambda o: o["order_created_at"])
        base = {
            "customer_id": head["customer_id"],
            "full_name": head["full_name"],
            "phone": head["phone"],
            "email": head["email"],
            "city": head["customer_city"],
            "created_at": created,
        }

        if not placed:
            features = _features(head, with_order=False)
            probability, contributions = self.prospect_model.predict(features)
            age_days = max((as_of - created.date()).days, 0)
            probability *= PROSPECT_FACTOR * 0.5 ** (age_days / PROSPECT_HALF_LIFE_DAYS)
            probability = max(probability, PROSPECT_FLOOR)
            return Lead(
                **base,
                kind="prospect",
                order_status=None,
                event_type=None,
                event_date=None,
                guests=None,
                quote_total=None,
                probability=probability,
                tier=_tier(probability),
                expected_revenue=probability * self.avg_order_value,
                days_to_event=None,
                action="ליד ללא פנייה: לשלוח הודעת היכרות והצעה לאירוע הקרוב",
                reasons=[*self._reasons(contributions, features), f"נרשם לפני {age_days} ימים"],
            )

        order = placed[-1]  # latest order is the one still open
        features = _features(order, with_order=True)
        probability, contributions = self.model.predict(features)
        probability *= STATUS_FACTOR[order["status"]]
        event_date = date.fromisoformat(order["event_date"])
        days_to_event = (event_date - as_of).days
        passed = days_to_event < 0
        if passed:
            probability *= EVENT_PASSED_FACTOR
        total = _num(order["total"])
        action = {
            "pending_approval": "ההצעה ממתינה לאישור העסק: לאשר או לדחות",
            "draft": "הלקוח לא סיים את ההזמנה: ליצור קשר ולעזור להשלים",
            "rejected": "ההצעה נדחתה: לבדוק אם אפשר להציע חלופה",
        }[order["status"]]
        if passed:
            action = "האירוע כבר עבר: לא נדרשת פעולה מיידית"
        return Lead(
            **base,
            kind="open_order",
            order_status=order["status"],
            event_type=order["event_type"],
            event_date=event_date,
            guests=int(_num(order["total_guests"])),
            quote_total=total,
            probability=probability,
            tier=_tier(probability),
            expected_revenue=probability * total,
            days_to_event=days_to_event,
            action=action,
            reasons=self._reasons(contributions, features),
        )

    def leads(self, as_of: date | None = None) -> list[Lead]:
        as_of = as_of or date.today()
        scored = (self._score_customer(orders, as_of) for orders in self._by_customer.values())
        found = [lead for lead in scored if lead is not None]
        return sorted(found, key=lambda lead: lead.probability, reverse=True)

    def get(self, customer_id: str, as_of: date | None = None) -> Lead | None:
        orders = self._by_customer.get(customer_id)
        return self._score_customer(orders, as_of or date.today()) if orders else None

    # -- forecast ----------------------------------------------------------------------------

    def forecast(self, as_of: date | None = None) -> dict:
        leads = self.leads(as_of)
        tiers = {t: {"count": 0, "expected_revenue": 0.0} for t in ("hot", "warm", "cold")}
        by_month: dict[str, dict[str, float]] = defaultdict(
            lambda: {"count": 0, "expected_revenue": 0.0}
        )
        for lead in leads:
            tiers[lead.tier]["count"] += 1
            tiers[lead.tier]["expected_revenue"] += lead.expected_revenue
            if lead.event_date and (lead.days_to_event or 0) >= 0:
                month = by_month[lead.event_date.strftime("%Y-%m")]
                month["count"] += 1
                month["expected_revenue"] += lead.expected_revenue
        return {
            "total_leads": len(leads),
            "expected_conversions": round(sum(lead.probability for lead in leads), 1),
            "expected_revenue": round(sum(lead.expected_revenue for lead in leads), 2),
            "base_conversion_rate": round(self.model.base_rate, 3),
            "average_order_value": round(self.avg_order_value, 2),
            "tiers": {
                t: {"count": v["count"], "expected_revenue": round(v["expected_revenue"], 2)}
                for t, v in tiers.items()
            },
            "by_event_month": [
                {
                    "month": m,
                    "count": int(v["count"]),
                    "expected_revenue": round(v["expected_revenue"], 2),
                }
                for m, v in sorted(by_month.items())
            ],
        }
