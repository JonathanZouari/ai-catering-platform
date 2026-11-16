"""Fills a throwaway database with synthetic leads, for trying out the lead model.

    uv run python -m scripts.synthetic_leads            # 1000 leads, seed 7
    uv run python -m scripts.synthetic_leads --count 500 --seed 1

It never touches a real caterer: it builds a separate database (default
`ai_catering_synth_test`, on the same server as TEST_DATABASE_URL), wipes it, applies the
migrations, creates one demo caterer, and inserts the leads with their real outcomes.

The outcome is drawn from a hidden formula that is different from the rules in
services/lead_scoring.py plus random noise, so the data is realistic but not circular.
Everything here is invented. Nothing is a real customer.
"""

import argparse
import hashlib
import json
import math
import os
import random
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.schemas.caterers import CatererCreate
from app.services import lead_scoring
from app.services.caterers import create_caterer
from app.services.lead_scoring import Features
from scripts import test_database

LOCAL_ENV = Path(__file__).resolve().parents[2] / ".env.test"
DEFAULT_DATABASE = "ai_catering_synth_test"
TODAY = date(2026, 11, 16)


def base_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url and LOCAL_ENV.exists():
        for line in LOCAL_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("TEST_DATABASE_URL="):
                url = line.split("=", 1)[1]
    if not url:
        raise SystemExit("Set TEST_DATABASE_URL (or pass --database-url).")
    return url


def ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.scalar(
            text("select 1 from pg_database where datname = :n"), {"n": target.database}
        )
        if not exists:
            connection.exec_driver_sql(f'create database "{target.database}"')
    admin.dispose()


def draw_features(rng: random.Random) -> Features:
    low, high = rng.choices([(0, 6), (7, 60), (61, 180), (181, 400)], [10, 45, 30, 15])[0]
    days = rng.randint(low, high)
    guests = max(2, int(rng.lognormvariate(3.2, 0.7)))
    categories = rng.choices([1, 2, 3, 4, 5], [10, 25, 30, 25, 10])[0]
    chat = rng.choice([0, 0, rng.randint(1, 20), rng.randint(1, 20), rng.randint(21, 40)])
    accepted = rng.choices([0, 1, 2], [60, 30, 10])[0] if chat else 0
    rejected = rng.choices([0, 1, 2], [70, 22, 8])[0] if chat else 0
    total = round(guests * rng.uniform(35, 90) + rng.uniform(0, 300), 2)
    return Features(
        days_to_event=days,
        guests=guests,
        total=total,
        categories=categories,
        chat_messages=chat,
        proposals_accepted=accepted,
        proposals_rejected=rejected,
        has_email=True if rng.random() < 0.55 else None,
        delivery_resolved=True if rng.random() < 0.4 else None,
        kashrut_acknowledged=rng.random() < 0.08,
    )


def purchase_probability(f: Features, rng: random.Random) -> float:
    """The hidden truth. Not the scoring rules: other weights, a size effect, and noise."""
    days, guests = f.days_to_event, f.guests
    logit = -2.1
    logit += 1.0 if 7 <= days <= 60 else 0.0
    logit -= 1.2 if days < 3 else 0.0
    logit -= 0.6 if days > 180 else 0.0
    logit += 0.012 * (guests - 25)
    logit += 0.0006 * (f.total - 1500) / 1.0
    logit += 0.45 if f.categories >= 3 else 0.0
    logit += 0.04 * min(f.chat_messages, 15)
    logit += 0.7 if f.proposals_accepted else (-0.5 if f.proposals_rejected else 0.0)
    logit += 0.8 if f.has_email else 0.0
    logit += 0.2 if f.delivery_resolved else 0.0
    logit -= 0.2 if f.kashrut_acknowledged else 0.0
    logit += rng.gauss(0, 0.6)
    return 1 / (1 + math.exp(-logit))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Insert synthetic leads into a throwaway database."
    )
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--database-url", help="a database whose name contains 'test'")
    args = parser.parse_args()

    url = args.database_url or make_url(base_url()).set(database=DEFAULT_DATABASE).render_as_string(
        hide_password=False
    )
    test_database.require_test_database(url)
    ensure_database(url)
    engine = create_engine(url)
    test_database.reset(engine)

    rng = random.Random(args.seed)  # noqa: S311  (reproducible synthetic data, not security)
    with Session(engine, expire_on_commit=False) as session:
        user_id = uuid4()
        test_database.add_auth_user(session, user_id)
        caterer = create_caterer(
            session, CatererCreate(slug="synthetic", name="קייטרינג דמו", auth_user_id=user_id)
        )
        slot = session.scalar(
            text(
                "insert into time_slots (caterer_id, fulfillment_type, weekday, start_time, "
                "end_time) values (:c, 'pickup', 2, '09:00', '12:00') returning id"
            ),
            {"c": caterer.id},
        )

        rows = {"customers": [], "events": [], "orders": [], "leads": [], "lead_outcomes": []}
        won = 0
        for number in range(args.count):
            features = draw_features(rng)
            result = lead_scoring.score(features)
            bought = rng.random() < purchase_probability(features, rng)
            won += bought
            customer_id, event_id, order_id, lead_id = (uuid4() for _ in range(4))
            event_date = TODAY + timedelta(days=features.days_to_event)
            submitted = datetime.combine(TODAY - timedelta(days=rng.randint(0, 120)), time(12), UTC)
            guests = features.guests
            rows["customers"].append(
                {
                    "id": customer_id,
                    "c": caterer.id,
                    "n": f"לקוח דמו {number + 1}",
                    "p": "050-0000000",
                }
            )
            rows["events"].append(
                {
                    "id": event_id,
                    "c": caterer.id,
                    "cu": customer_id,
                    "d": event_date,
                    "a": guests,
                    "ch": 0,
                }
            )
            rows["orders"].append(
                {
                    "id": order_id,
                    "c": caterer.id,
                    "h": hashlib.sha256(order_id.bytes).hexdigest(),
                    "cu": customer_id,
                    "e": event_id,
                    "r": datetime.combine(event_date, time(9), UTC),
                    "s": slot,
                    "t": features.total,
                    "sub": submitted,
                }
            )
            outcome = "won" if bought else "lost"
            payload = {
                "id": lead_id,
                "c": caterer.id,
                "o": order_id,
                "st": outcome,
                "sc": result.probability,
                "v": lead_scoring.SCORE_VERSION,
                "rs": json.dumps(result.reasons),
                "f": json.dumps(features.as_dict()),
            }
            rows["leads"].append(payload)
            rows["lead_outcomes"].append(payload)

        session.execute(
            text(
                "insert into customers (id, caterer_id, full_name, phone) values (:id, :c, :n, :p)"
            ),
            rows["customers"],
        )
        session.execute(
            text(
                "insert into events (id, caterer_id, customer_id, event_type, event_date, "
                "adults, children) values (:id, :c, :cu, 'אירוע דמו', :d, :a, :ch)"
            ),
            rows["events"],
        )
        session.execute(
            text(
                "insert into orders (id, caterer_id, access_token_hash, customer_id, event_id, "
                "status, fulfillment_type, requested_at, time_slot_id, total, submitted_at) "
                "values (:id, :c, :h, :cu, :e, 'pending_approval', 'pickup', :r, :s, :t, :sub)"
            ),
            rows["orders"],
        )
        session.execute(
            text(
                "insert into leads (id, caterer_id, order_id, stage, score, score_version, "
                "reasons, features) values (:id, :c, :o, cast(:st as lead_stage), :sc, :v, "
                "cast(:rs as jsonb), cast(:f as jsonb))"
            ),
            rows["leads"],
        )
        session.execute(
            text(
                "insert into lead_outcomes (caterer_id, lead_id, outcome, score_at_decision, "
                "score_version, features) values (:c, :id, cast(:st as lead_stage), :sc, :v, "
                "cast(:f as jsonb))"
            ),
            rows["lead_outcomes"],
        )
        session.commit()

    print(f"Inserted {args.count} synthetic leads into {make_url(url).database}")
    print(f"won: {won} ({won / args.count:.0%}), lost: {args.count - won}")
    print(f"database url: {url.replace(make_url(url).password or '', '***')}")


if __name__ == "__main__":
    main()
