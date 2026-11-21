"""Generates made-up leads for the purchase-prediction model. The app has no real leads yet.

Each lead gets four form fields and five on-site behaviour signals. Whether a historical lead
ordered comes from a hidden rule plus random chance, so no model can be perfect on this data.

Run from backend/:  uv run python scripts/generate_leads.py
Writes data/leads_history.csv (with the outcome, for training) and data/leads_open.csv
(no outcome yet, scored and shown in the owner dashboard). The seed makes runs repeatable.
"""

import csv
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SEED = 19
N_HISTORY = 1000
N_OPEN = 40

# Same occasion list as the customer flow (frontend/js/customer/mock-backend.js).
EVENT_TYPES = [
    "יום הולדת",
    "אירוע משפחתי",
    "בר או בת מצווה",
    "ארוחת שבת",
    "יום נישואין",
    "חגיגה פרטית",
    "אחר",
]
SOURCES = ["google", "instagram", "facebook", "referral", "direct"]

# The hidden rule. The model never sees these numbers; it has to learn them back from the data.
EVENT_EFFECT = {
    "יום הולדת": 0.0,
    "אירוע משפחתי": 0.2,
    "בר או בת מצווה": 0.5,
    "ארוחת שבת": -0.2,
    "יום נישואין": 0.1,
    "חגיגה פרטית": 0.0,
    "אחר": -0.4,
}
SOURCE_EFFECT = {"google": 0.0, "instagram": -0.4, "facebook": -0.2, "referral": 0.9, "direct": 0.3}

FIRST_NAMES = [
    "נועה",
    "יוסי",
    "מיכל",
    "דני",
    "שירה",
    "אבי",
    "רותם",
    "עומר",
    "תמר",
    "איתי",
    "הילה",
    "גיל",
    "ליאת",
    "רון",
    "מאיה",
    "אסף",
    "יעל",
    "עידו",
    "קרן",
    "אלון",
]
LAST_NAMES = ["כהן", "לוי", "מזרחי", "פרץ", "ביטון", "אברהם", "פרידמן", "דהן", "אזולאי", "שפירא"]

FIELDS = [
    "lead_id",
    "full_name",
    "phone",
    "event_type",
    "guests",
    "days_until_event",
    "budget_per_guest",
    "dishes_viewed",
    "minutes_on_site",
    "visits",
    "source",
    "used_chat",
]


def make_leads(rng: np.random.Generator, n: int, id_prefix: str) -> list[dict]:
    leads = []
    for i in range(n):
        leads.append(
            {
                "lead_id": f"{id_prefix}-{i + 1:04d}",
                "full_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                # 050-000xxxx is not a real allocated range: obviously fake numbers.
                "phone": f"050-000{rng.integers(0, 10_000):04d}",
                "event_type": str(rng.choice(EVENT_TYPES)),
                "guests": int(np.clip(rng.lognormal(3.6, 0.6), 8, 400)),
                "days_until_event": int(rng.integers(1, 181)),
                "budget_per_guest": int(np.clip(rng.normal(130, 40), 50, 320)),
                "dishes_viewed": int(rng.poisson(rng.choice([2, 7, 15]))),
                "minutes_on_site": round(float(rng.exponential(6)) + 0.5, 1),
                "visits": int(1 + rng.poisson(0.8)),
                "source": str(rng.choice(SOURCES, p=[0.35, 0.25, 0.15, 0.1, 0.15])),
                "used_chat": int(rng.random() < 0.3),
            }
        )
    return leads


def hidden_logit(lead: dict) -> float:
    return (
        -3.3
        + 0.09 * lead["dishes_viewed"]
        + 0.45 * (lead["visits"] - 1)
        + 0.04 * lead["minutes_on_site"]
        + 0.8 * lead["used_chat"]
        - 0.007 * lead["days_until_event"]
        + 0.006 * (lead["budget_per_guest"] - 130)
        + 0.002 * lead["guests"]
        + EVENT_EFFECT[lead["event_type"]]
        + SOURCE_EFFECT[lead["source"]]
    )


def write(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rng = np.random.default_rng(SEED)
    history = make_leads(rng, N_HISTORY, "H")
    for lead in history:
        p = 1 / (1 + np.exp(-hidden_logit(lead)))
        lead["ordered"] = int(rng.random() < p)
    open_leads = make_leads(rng, N_OPEN, "L")

    DATA_DIR.mkdir(exist_ok=True)
    write(DATA_DIR / "leads_history.csv", history, [*FIELDS, "ordered"])
    write(DATA_DIR / "leads_open.csv", open_leads, FIELDS)
    rate = sum(lead["ordered"] for lead in history) / N_HISTORY
    print(f"history: {N_HISTORY} leads, {rate:.1%} ordered; open: {N_OPEN} leads")


if __name__ == "__main__":
    main()
