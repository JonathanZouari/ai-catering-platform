"""Add SYNTHETIC lead-behaviour columns to the customers export.

!! These values are invented. They are generated so that they correlate with has_ordered, the
!! way real lead data usually does, in order to demonstrate how richer features improve the model.
!! Any improvement measured on them is true by construction and says nothing about real customers.
!! Replace them with real data (lead source, response time, ...) as soon as it is collected.

The original file is never modified; the output is data/combined_clients_orders_enriched.csv.
Each customer gets one set of values (repeated on all of their rows). 20% of customers draw
their values from the *other* class's distribution, so the classes overlap like real data.

Usage (from backend/):  python scripts/enrich_synthetic_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "combined_clients_orders.csv"
OUT = ROOT / "data" / "combined_clients_orders_enriched.csv"
SEED = 7
CROSSOVER = 0.20  # share of customers whose behaviour looks like the other class
MISSING_BUDGET = 0.08  # budget is often not stated, so the imputer has something to do

SOURCES = ["referral", "google", "instagram", "facebook", "whatsapp_direct", "paid_ad"]
SOURCE_PROBS = {
    True: [0.30, 0.25, 0.15, 0.10, 0.12, 0.08],
    False: [0.05, 0.20, 0.20, 0.20, 0.05, 0.30],
}


def draw(rng: np.random.Generator, ordered: bool) -> dict:
    return {
        "lead_source": rng.choice(SOURCES, p=SOURCE_PROBS[ordered]),
        # hours until the business first replied: fast replies convert better
        "response_time_hours": float(
            np.clip(rng.lognormal(np.log(3 if ordered else 12), 0.7), 0.1, 96)
        ),
        # days between the inquiry and the event
        "lead_time_days": float(rng.gamma(4, 12 if ordered else 6)),
        "interactions_count": int(rng.poisson(5 if ordered else 2)),
        "site_visits": int(rng.poisson(6 if ordered else 3)),
        "requested_quote": "yes" if rng.random() < (0.9 if ordered else 0.35) else "no",
        "stated_budget": float(rng.lognormal(np.log(6000 if ordered else 3500), 0.4)),
    }


def main() -> None:
    rng = np.random.default_rng(SEED)
    rows = pd.read_csv(SOURCE, encoding="utf-8-sig")
    customers = rows.drop_duplicates("customer_id")[["customer_id", "has_ordered"]]
    extra = []
    for customer_id, has_ordered in customers.itertuples(index=False):
        behaves_like_orderer = (has_ordered == "yes") != (rng.random() < CROSSOVER)
        values = draw(rng, behaves_like_orderer)
        if rng.random() < MISSING_BUDGET:
            values["stated_budget"] = np.nan
        extra.append({"customer_id": customer_id, **values})
    enriched = rows.merge(pd.DataFrame(extra), on="customer_id", how="left")
    enriched.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"saved {len(enriched)} rows, {len(extra)} customers -> {OUT}")


if __name__ == "__main__":
    main()
