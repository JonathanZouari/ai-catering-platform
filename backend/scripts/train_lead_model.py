"""Train the lead conversion model and write app/services/lead_model.json.

Run from backend/:
    python -m scripts.train_lead_model                 # synthetic history (default, development)
    python -m scripts.train_lead_model --source db     # real closed leads; refuses if too few

A model trained on synthetic data is marked trained_on_synthetic=true, and every score it writes
carries that flag, so the admin can label it as a demo.
"""

from __future__ import annotations

import argparse
import random
import sys

from app.services.lead_scoring import (
    FEATURES,
    MODEL_PATH,
    LeadModel,
    auc,
    brier,
    fit_logistic,
    lead_features,
    prior_contacts,
)

MIN_CLOSED_LEADS = 100
MIN_PER_CLASS = 20
MODEL_VERSION = "v1"


def load_real() -> tuple[list[dict], list[int]]:
    from scripts.supabase_rest import SupabaseRest

    leads = SupabaseRest().select(
        "leads",
        "id,phone,source,email,customer_id,event_date,created_at,guest_count,message,status",
    )
    priors = prior_contacts(leads)
    closed = [lead for lead in leads if lead["status"] in ("converted", "lost")]
    labels = [int(lead["status"] == "converted") for lead in closed]
    if (
        len(closed) < MIN_CLOSED_LEADS
        or min(sum(labels), len(labels) - sum(labels)) < MIN_PER_CLASS
    ):
        raise SystemExit(
            f"Not enough real outcomes yet: {len(closed)} closed leads, {sum(labels)} converted. "
            f"Need {MIN_CLOSED_LEADS}+ closed and {MIN_PER_CLASS}+ of each outcome."
        )
    return [lead_features(lead, priors[lead["id"]]) for lead in closed], labels


def load_synthetic(n: int, seed: int) -> tuple[list[dict], list[int]]:
    from scripts.synthetic_leads import generate

    rows, priors, labels = generate(n, seed)
    return [lead_features(r, p) for r, p in zip(rows, priors, strict=True)], labels


def train(features: list[dict], labels: list[int], synthetic: bool, seed: int = 7) -> LeadModel:
    """Hold out 25% (stratified) to measure, then refit on everything for the saved model."""
    rng = random.Random(seed)  # noqa: S311 - data split, not security
    test_idx: set[int] = set()
    for cls in (0, 1):
        idx = [i for i, y in enumerate(labels) if y == cls]
        rng.shuffle(idx)
        test_idx.update(idx[: max(1, len(idx) // 4)])
    train_x = [f for i, f in enumerate(features) if i not in test_idx]
    train_y = [y for i, y in enumerate(labels) if i not in test_idx]
    test_x = [f for i, f in enumerate(features) if i in test_idx]
    test_y = [y for i, y in enumerate(labels) if i in test_idx]

    b0, coefs = fit_logistic(train_x, train_y)
    held_out = LeadModel("eval", b0, coefs, {f: 0.0 for f in FEATURES}, synthetic, {})
    probs = [held_out.probability(x) for x in test_x]

    b0, coefs = fit_logistic(features, labels)
    means = {f: sum(row[f] for row in features) / len(features) for f in FEATURES}
    return LeadModel(
        version=f"{MODEL_VERSION}-{'synthetic' if synthetic else 'real'}",
        intercept=round(b0, 6),
        coefficients={f: round(c, 6) for f, c in coefs.items()},
        means={f: round(m, 6) for f, m in means.items()},
        trained_on_synthetic=synthetic,
        metrics={
            "n_train": len(features),
            "base_rate": round(sum(labels) / len(labels), 4),
            "holdout_auc": round(auc(probs, test_y), 4),
            "holdout_brier": round(brier(probs, test_y), 4),
            "holdout_n": len(test_y),
        },
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=["synthetic", "db"], default="synthetic")
    parser.add_argument("--n", type=int, default=600, help="synthetic rows")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    if args.source == "db":
        features, labels = load_real()
    else:
        features, labels = load_synthetic(args.n, args.seed)
    model = train(features, labels, synthetic=args.source == "synthetic", seed=args.seed)
    model.save(MODEL_PATH)
    print(f"saved {MODEL_PATH.name}: {model.version}", model.metrics, file=sys.stderr)
    for f in FEATURES:
        print(f"  {f:<20} {model.coefficients[f]:+.3f}", file=sys.stderr)


if __name__ == "__main__":
    main()
