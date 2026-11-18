"""Synthetic lead generator.

The label is drawn from a known logistic function of the features, so a good model can recover
the signal. This validates the pipeline only. It says nothing about real conversion rates.
All people are fake: names are placeholders, phones are not generated.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

EVENT_TYPES = [
    "יום הולדת",
    "אירוע משפחתי",
    "בר או בת מצווה",
    "ארוחת שבת",
    "יום נישואין",
    "חגיגה פרטית",
    "אחר",
]
SOURCES = ["website_form", "ai_chat", "whatsapp", "phone", "referral", "instagram", "google"]

# Effect of each category on the log-odds of converting. Invented for the simulation.
SOURCE_EFFECT = {
    "referral": 1.0,
    "phone": 0.6,
    "whatsapp": 0.3,
    "website_form": 0.0,
    "ai_chat": 0.1,
    "instagram": -0.5,
    "google": -0.4,
}
TYPE_EFFECT = {
    "בר או בת מצווה": 0.5,
    "אירוע משפחתי": 0.3,
    "יום הולדת": 0.0,
    "ארוחת שבת": 0.2,
    "יום נישואין": 0.1,
    "חגיגה פרטית": 0.0,
    "אחר": -0.4,
}
INTERCEPT = -0.9

FIELDS = [
    "lead_id",
    "source",
    "event_type",
    "guests",
    "days_until_event",
    "budget",
    "quote_amount",
    "quote_budget_ratio",
    "repeat_customer",
    "has_email",
    "response_hours",
    "touches",
    "viewed_menu",
    "weekend_event",
    "converted",
]


def generate(n: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        source = rng.choice(SOURCES, p=[0.25, 0.15, 0.2, 0.1, 0.12, 0.1, 0.08])
        event_type = rng.choice(EVENT_TYPES, p=[0.18, 0.2, 0.17, 0.12, 0.08, 0.15, 0.1])
        guests = int(np.clip(rng.lognormal(3.3, 0.6), 4, 300))
        days_until = int(np.clip(rng.gamma(2.0, 18.0), 1, 240))
        repeat = bool(rng.random() < 0.18)
        has_email = bool(rng.random() < 0.7)
        viewed_menu = bool(rng.random() < (0.55 if source in ("website_form", "ai_chat") else 0.3))
        weekend = bool(rng.random() < 0.4)
        # Price per guest around 140 NIS; budget is what the customer says they can spend.
        quote = round(guests * rng.normal(140, 25), -1)
        budget = round(quote * rng.lognormal(0.0, 0.3), -1)
        ratio = quote / budget if budget else 1.0
        response_hours = float(np.clip(rng.exponential(6.0), 0.1, 96))
        touches = int(np.clip(rng.poisson(2.5 + (1.0 if repeat else 0)), 0, 12))

        z = (
            INTERCEPT
            + SOURCE_EFFECT[source]
            + TYPE_EFFECT[event_type]
            + 0.9 * repeat
            + 0.3 * has_email
            + 0.4 * viewed_menu
            - 0.9 * np.log1p(response_hours) / np.log(10)  # slow reply hurts
            - 2.2 * max(ratio - 1.0, 0.0)  # quote above budget hurts
            + 0.25 * min(touches, 6)
            - 0.012 * abs(days_until - 30)  # too soon or too far hurts
            + 0.15 * np.log(guests / 40)
            + 0.2 * weekend
            + rng.normal(0, 0.6)  # unexplained noise
        )
        converted = bool(rng.random() < 1 / (1 + np.exp(-z)))
        rows.append(
            {
                "lead_id": f"L{i:05d}",
                "source": source,
                "event_type": event_type,
                "guests": guests,
                "days_until_event": days_until,
                "budget": int(budget),
                "quote_amount": int(quote),
                "quote_budget_ratio": round(ratio, 3),
                "repeat_customer": int(repeat),
                "has_email": int(has_email),
                "response_hours": round(response_hours, 2),
                "touches": touches,
                "viewed_menu": int(viewed_menu),
                "weekend_event": int(weekend),
                "converted": int(converted),
            }
        )
    return rows


def write_csv(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=3000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", type=Path, default=Path("ml/out/leads.csv"))
    a = p.parse_args()
    rows = generate(a.n, a.seed)
    write_csv(rows, a.out)
    rate = sum(r["converted"] for r in rows) / len(rows)
    print(f"wrote {len(rows)} leads to {a.out} (conversion rate {rate:.1%})")


if __name__ == "__main__":
    main()
