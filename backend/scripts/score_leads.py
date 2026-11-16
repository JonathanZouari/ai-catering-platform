"""Score every open lead (new / contacted) and upsert into lead_scores.

Run from backend/ with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY set:
    python -m scripts.score_leads             # write scores
    python -m scripts.score_leads --dry-run   # print only
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from app.services.lead_scoring import LeadModel, lead_features, prior_contacts

OPEN_STATUSES = ("new", "contacted")


def score_rows(leads: list[dict], model: LeadModel) -> list[dict]:
    priors = prior_contacts(leads)
    now = datetime.now(UTC).isoformat()
    rows = []
    for lead in leads:
        if lead["status"] not in OPEN_STATUSES:
            continue
        feats = lead_features(lead, priors[lead["id"]])
        rows.append(
            {
                "lead_id": lead["id"],
                "probability": round(model.probability(feats), 3),
                "model_version": model.version,
                "trained_on_synthetic": model.trained_on_synthetic,
                "reasons": model.reasons(feats),
                "scored_at": now,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> None:
    from scripts.supabase_rest import SupabaseRest

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    db = SupabaseRest()
    leads = db.select(
        "leads",
        "id,full_name,phone,source,email,customer_id,event_date,created_at,guest_count,message,status",
    )
    rows = score_rows(leads, LeadModel.load())
    names = {lead["id"]: lead["full_name"] for lead in leads}
    for row in sorted(rows, key=lambda r: r["probability"], reverse=True):
        why = "; ".join(
            ("+" if r["direction"] == "up" else "-") + r["label"] for r in row["reasons"]
        )
        print(f"{row['probability']:>6.1%}  {names[row['lead_id']]}  ({why})")
    if not args.dry_run:
        db.upsert("lead_scores", rows, on_conflict="lead_id")
        print(f"upserted {len(rows)} scores with model {rows[0]['model_version'] if rows else '-'}")


if __name__ == "__main__":
    main()
