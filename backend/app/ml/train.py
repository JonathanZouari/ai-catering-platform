"""Train the lead-scoring model: linear and logistic regression side by side.

    uv run python -m app.ml.train --source synthetic   # made-up data (app/ml/synthetic.py)
    uv run python -m app.ml.train --source db          # real orders from DATABASE_URL

Writes app/ml/lead_model.json, which the server scores with (app/services/leads.py).
Needs scikit-learn (dev dependency group); the server does not.
"""

import argparse
import json
from datetime import UTC, date, datetime, timedelta

import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import synthetic
from app.models.orders import Order
from app.services.leads import FEATURES, MODEL_PATH, features

LEAD_CLOSED_DAYS = 14  # a draft this old without a submission counts as "did not purchase"
MIN_DB_ROWS = 200  # below this the coefficients are noise
TEST_SHARE = 0.2
SEED = 7


def label(order: Order, today: date) -> int | None:
    """1 purchased, 0 did not, None still open (left out of training)."""
    if order.submitted_at is not None:
        return 1
    closed = order.created_at.date() <= today - timedelta(days=LEAD_CLOSED_DAYS)
    return 0 if closed or order.event.event_date < today else None


def db_rows(db: Session, today: date) -> tuple[list[list[float]], list[int]]:
    data, labels = [], []
    for order in db.scalars(select(Order)).unique():
        if (outcome := label(order, today)) is not None:
            row = features(order)
            data.append([row[name] for name in FEATURES])
            labels.append(outcome)
    return data, labels


def train(data: list[list[float]], labels: list[int], source: str) -> dict:
    """Fit both models on one split and return the model file contents."""
    x_train, x_test, y_train, y_test = train_test_split(
        np.array(data), np.array(labels), test_size=TEST_SHARE, random_state=SEED, stratify=labels
    )
    scaler = StandardScaler().fit(x_train)
    x_train, x_test = scaler.transform(x_train), scaler.transform(x_test)

    linear = LinearRegression().fit(x_train, y_train)
    logistic = LogisticRegression(max_iter=1000).fit(x_train, y_train)
    raw = linear.predict(x_test)
    predictions = {"linear": np.clip(raw, 0, 1), "logistic": logistic.predict_proba(x_test)[:, 1]}

    metrics = {
        kind: {
            "auc": round(float(roc_auc_score(y_test, p)), 4),
            "brier": round(float(brier_score_loss(y_test, p)), 4),
        }
        for kind, p in predictions.items()
    }
    # Share of raw linear predictions that are not valid probabilities.
    metrics["linear"]["out_of_range"] = round(float(np.mean((raw < 0) | (raw > 1))), 4)
    return {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source,
        "rows": len(labels),
        "chosen": min(metrics, key=lambda kind: metrics[kind]["brier"]),
        "features": list(FEATURES),
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "models": {
            "linear": {"coef": linear.coef_.tolist(), "intercept": float(linear.intercept_)},
            "logistic": {
                "coef": logistic.coef_[0].tolist(),
                "intercept": float(logistic.intercept_[0]),
            },
        },
        "metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=("synthetic", "db"), required=True)
    source = parser.parse_args().source

    if source == "synthetic":
        data, labels = synthetic.rows()
    else:
        from app.core.db import get_engine  # needs DATABASE_URL; not for synthetic runs

        if (engine := get_engine()) is None:
            raise SystemExit("DATABASE_URL is not configured")
        with Session(engine) as db:
            data, labels = db_rows(db, datetime.now(UTC).date())
        if len(labels) < MIN_DB_ROWS or len(set(labels)) < 2:
            raise SystemExit(
                f"Not enough closed leads to train: {len(labels)} rows, "
                f"{sum(labels)} purchased (need {MIN_DB_ROWS} rows and both outcomes)"
            )

    model = train(data, labels, source)
    MODEL_PATH.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")

    print(f"rows: {model['rows']}  purchased: {sum(labels) / len(labels):.1%}  source: {source}")
    print(f"{'model':<10}{'AUC':>8}{'Brier':>8}{'out of 0..1':>14}")
    for kind, m in model["metrics"].items():
        outside = f"{m['out_of_range']:.1%}" if "out_of_range" in m else "-"
        print(f"{kind:<10}{m['auc']:>8.3f}{m['brier']:>8.3f}{outside:>14}")
    print(f"chosen: {model['chosen']} (lower Brier)  ->  {MODEL_PATH}")


if __name__ == "__main__":
    main()
