# /// script
# requires-python = ">=3.12"
# dependencies = ["scikit-learn>=1.6,<2"]
# ///
"""Reproducible synthetic experiment, NOT a business conversion forecast.

Run: uv run --script tools/train_lead_demo.py
Only information available when a website inquiry is submitted is used.
"""

import json
import math
import random
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
FEATURES = [
    "guest_count",
    "days_until_event",
    "budget_per_guest",
    "date_provided",
    "budget_provided",
]
rng = random.Random(20261116)


def synthetic(index):
    guests = rng.randint(10, 250)
    days = rng.randint(2, 180) if rng.random() > 0.15 else None
    budget = rng.randint(40, 280) if rng.random() > 0.25 else None
    # Deliberately artificial generating assumptions, with random outcomes.
    # These coefficients are NOT the trained coefficients or real customer behavior.
    latent = -1.9 + 0.004 * guests + 0.013 * ((budget or 100) - 100)
    latent += 0.8 * (days is not None) - 0.009 * (days or 60)
    latent += 0.5 * (budget is not None)
    converted = int(rng.random() < 1 / (1 + math.exp(-latent)))
    return {
        "id": f"synthetic-{index:04d}",
        "is_synthetic": True,
        "name": f"פונה לדוגמה {index}",
        "email": f"lead-{index}@example.invalid",
        "guest_count": guests,
        "days_until_event": days,
        "budget_per_guest": budget,
        "converted_within_30_days": converted,
    }


def vector(row):
    return [
        row["guest_count"],
        row["days_until_event"] or 0,
        row["budget_per_guest"] or 0,
        int(row["days_until_event"] is not None),
        int(row["budget_per_guest"] is not None),
    ]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    rows = [synthetic(i) for i in range(1, 1201)]
    train, test = train_test_split(
        rows,
        test_size=0.25,
        random_state=42,
        stratify=[r["converted_within_30_days"] for r in rows],
    )
    model = make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=1000, random_state=42)
    )
    model.fit(
        [vector(r) for r in train], [r["converted_within_30_days"] for r in train]
    )
    y = [r["converted_within_30_days"] for r in test]
    p = model.predict_proba([vector(r) for r in test])[:, 1]
    predicted = (p >= 0.5).astype(int)
    prevalence = sum(r["converted_within_30_days"] for r in train) / len(train)
    metrics = {
        "evaluation": "SYNTHETIC ONLY — not evidence of real conversion performance",
        "train_rows": len(train),
        "test_rows": len(test),
        "threshold": 0.5,
        "roc_auc": float(roc_auc_score(y, p)),
        "brier_score": float(brier_score_loss(y, p)),
        "baseline_brier_score": float(brier_score_loss(y, [prevalence] * len(test))),
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "confusion_matrix_actual_rows_predicted_columns": confusion_matrix(
            y, predicted
        ).tolist(),
    }
    scaler, classifier = model.steps[0][1], model.steps[1][1]
    artifact = {
        "version": "synthetic-logistic-v1",
        "synthetic_only": True,
        "target": "approved_order_within_30_days_of_website_inquiry",
        "prediction_time": "initial_website_form_submission",
        "features": FEATURES,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coefficients": classifier.coef_[0].tolist(),
        "intercept": float(classifier.intercept_[0]),
        "threshold": 0.5,
        "metrics": metrics,
    }
    for row in rows:
        row["split"] = "train" if row in train else "test"
    write(ROOT / "docs/demo/leads-training-synthetic.json", rows)
    write(ROOT / "backend/app/models/lead_demo_logistic.json", artifact)
    # New unlabelled leads, not training/test records. Outcomes must not appear in the live demo.
    demo = []
    for i in range(1201, 1225):
        row = synthetic(i)
        del row["converted_within_30_days"]
        probability = float(model.predict_proba([vector(row)])[0, 1])
        row.update(
            demo_probability=probability,
            demo_class="higher" if probability >= 0.5 else "lower",
            stage="new",
        )
        demo.append(row)
    write(
        ROOT / "frontend/demo/leads.json",
        {"synthetic_only": True, "model": artifact, "leads": demo},
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
