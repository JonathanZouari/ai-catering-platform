"""Trains the logistic-regression model that predicts whether a lead will order.

Order of work matters: the data is split into train and test FIRST. Scaling means, standard
deviations and the category list are learned from the training rows only, inside one Pipeline,
so nothing about the test rows leaks into the model. No class balancing: the displayed
percentage must stay a real probability. The class imbalance is handled by the threshold.

Run from backend/:  uv run python scripts/train_lead_model.py [--threshold 0.3]
Writes data/lead_model.json (plain numbers, loaded by app/services/lead_scoring.py without
scikit-learn or pickle) and data/lead_model_report.json (test-set metrics).
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
NUMERIC = [
    "guests",
    "days_until_event",
    "budget_per_guest",
    "dishes_viewed",
    "minutes_on_site",
    "visits",
    "used_chat",
]
CATEGORICAL = ["event_type", "source"]
THRESHOLDS = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
SEED = 42


def load_history() -> tuple[list[dict], np.ndarray]:
    with (DATA_DIR / "leads_history.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    y = np.array([int(r["ordered"]) for r in rows])
    return rows, y


def to_matrix(rows: list[dict]) -> np.ndarray:
    """Numeric columns as floats, categorical as strings, in one object array."""
    return np.array(
        [[float(r[c]) for c in NUMERIC] + [r[c] for c in CATEGORICAL] for r in rows],
        dtype=object,
    )


def build_pipeline() -> Pipeline:
    n = len(NUMERIC)
    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), list(range(n))),
            ("cat", OneHotEncoder(handle_unknown="ignore"), list(range(n, n + len(CATEGORICAL)))),
        ]
    )
    return Pipeline([("pre", pre), ("model", LogisticRegression(max_iter=1000))])


def threshold_table(y_true: np.ndarray, proba: np.ndarray) -> list[dict]:
    table = []
    for t in THRESHOLDS:
        pred = (proba >= t).astype(int)
        table.append(
            {
                "threshold": t,
                "flagged": int(pred.sum()),
                "true_positives": int(((pred == 1) & (y_true == 1)).sum()),
                "precision": round(float(precision_score(y_true, pred, zero_division=0)), 3),
                "recall": round(float(recall_score(y_true, pred)), 3),
            }
        )
    return table


def export_model(pipe: Pipeline, threshold: float | None) -> dict:
    pre = pipe.named_steps["pre"]
    scaler: StandardScaler = pre.named_transformers_["num"]
    encoder: OneHotEncoder = pre.named_transformers_["cat"]
    coef = pipe.named_steps["model"].coef_[0]
    n = len(NUMERIC)
    numeric = {
        name: {"mean": float(m), "scale": float(s), "coef": float(c)}
        for name, m, s, c in zip(NUMERIC, scaler.mean_, scaler.scale_, coef[:n], strict=True)
    }
    categorical, i = {}, n
    for name, cats in zip(CATEGORICAL, encoder.categories_, strict=True):
        categorical[name] = {str(cat): float(coef[i + j]) for j, cat in enumerate(cats)}
        i += len(cats)
    return {
        "version": 1,
        "intercept": float(pipe.named_steps["model"].intercept_[0]),
        "numeric": numeric,
        "categorical": categorical,
        "threshold": threshold,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=None, help="cut-off for a hot lead")
    args = parser.parse_args()

    rows, y = load_history()
    # 1. Split before any processing. Stratify keeps the same order rate in both parts.
    train_rows, test_rows, y_train, y_test = train_test_split(
        rows, y, test_size=0.2, stratify=y, random_state=SEED
    )
    # 2. Fit scaling, encoding and the model on the training rows only.
    pipe = build_pipeline().fit(to_matrix(train_rows), y_train)
    # 3. Evaluate once on the untouched test rows.
    proba = pipe.predict_proba(to_matrix(test_rows))[:, 1]

    report = {
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "train_order_rate": round(float(y_train.mean()), 3),
        "test_order_rate": round(float(y_test.mean()), 3),
        "test_auc": round(float(roc_auc_score(y_test, proba)), 3),
        "thresholds": threshold_table(y_test, proba),
    }
    model = export_model(pipe, args.threshold)
    (DATA_DIR / "lead_model.json").write_text(
        json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DATA_DIR / "lead_model_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
