"""Generate synthetic CRM leads and insert them into the leads table.

The buyer label is drawn from a hidden logistic "true" process, so a fitted model
has real structure to recover (but also noise, so it is not perfect).
"""

import argparse

import numpy as np
from common import SCHEMA, connect

SOURCES = ["web", "referral", "phone", "ad"]
EVENT_TYPES = ["wedding", "birthday", "corporate", "bar_mitzvah", "other"]
SOURCE_EFFECT = {"web": 0.0, "referral": 0.9, "phone": 0.6, "ad": -0.5}
EVENT_EFFECT = {
    "wedding": 0.5,
    "birthday": -0.1,
    "corporate": 0.4,
    "bar_mitzvah": 0.3,
    "other": -0.4,
}


def generate(n: int, seed: int) -> list[tuple]:
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        source = str(rng.choice(SOURCES, p=[0.45, 0.2, 0.15, 0.2]))
        event_type = str(rng.choice(EVENT_TYPES, p=[0.2, 0.3, 0.2, 0.15, 0.15]))
        days_until_event = int(np.clip(rng.gamma(2.2, 20), 2, 240))
        guest_count = int(np.clip(rng.lognormal(3.9, 0.6), 8, 400))
        dishes = int(np.clip(rng.poisson(3.5), 0, 20))
        quote = bool(rng.random() < min(0.15 + 0.07 * dishes, 0.9))
        chat = int(rng.poisson(2 + 3 * quote))
        visits = int(rng.poisson(1.5 + 0.3 * dishes))
        inactive = int(np.clip(rng.exponential(8) - 0.6 * visits, 0, 60))
        has_email = bool(rng.random() < 0.85)
        has_phone = bool(rng.random() < 0.55)

        # Hidden ground truth: urgency sweet spot (2-6 weeks), size, intent, engagement.
        z = (
            -2.6
            + 0.9 * (14 <= days_until_event <= 45)
            - 0.012 * max(days_until_event - 60, 0)
            + 0.008 * guest_count
            + 0.15 * dishes
            + 1.6 * quote
            + 0.10 * chat
            + 0.12 * visits
            - 0.08 * inactive
            + 0.5 * has_phone
            + 0.3 * has_email
            + SOURCE_EFFECT[source]
            + EVENT_EFFECT[event_type]
            + rng.normal(0, 0.8)
        )
        is_buyer = bool(rng.random() < 1 / (1 + np.exp(-z)))
        rows.append(
            (
                source,
                event_type,
                days_until_event,
                guest_count,
                dishes,
                int(quote),
                chat,
                visits,
                inactive,
                int(has_phone),
                int(has_email),
                "won" if is_buyer else "lost",
                int(is_buyer),
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = generate(args.n, args.seed)
    with connect() as conn:
        conn.execute(SCHEMA)
        conn.execute("delete from leads")  # re-runnable: replace, don't append
        conn.executemany(
            "insert into leads (source, event_type, days_until_event, guest_count, "
            "dishes_selected, quote_submitted, ai_chat_messages, visits_last_7d, "
            "days_since_last_activity, has_phone, has_email, stage, is_buyer) "
            "values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        total, buyers = conn.execute("select count(*), sum(is_buyer) from leads").fetchone()
    print(f"Inserted {total} leads; buyers: {buyers} ({buyers / total:.1%})")


if __name__ == "__main__":
    main()
