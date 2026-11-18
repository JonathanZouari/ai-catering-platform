"""Compare conversion models on a lead CSV (see ml/synthetic.py).

Metrics are computed on a held-out split. On synthetic data they validate the pipeline only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CATEGORICAL = ["source", "event_type"]
NUMERIC = [
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
]
TARGET = "converted"


def load(path: Path) -> tuple[list[dict], np.ndarray]:
    import csv

    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    y = np.array([int(r[TARGET]) for r in rows])
    return rows, y


def matrix(rows: list[dict]):
    cat = np.array([[r[c] for c in CATEGORICAL] for r in rows], dtype=object)
    num = np.array([[float(r[c]) for c in NUMERIC] for r in rows])
    return np.hstack([cat, num.astype(object)])


def build_models():
    n_cat = len(CATEGORICAL)
    cat_idx = list(range(n_cat))
    num_idx = list(range(n_cat, n_cat + len(NUMERIC)))
    onehot = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    linear_pre = ColumnTransformer([("c", onehot, cat_idx), ("n", StandardScaler(), num_idx)])
    tree_pre = ColumnTransformer([("c", onehot, cat_idx)], remainder="passthrough")
    return {
        "logreg": make_pipeline(linear_pre, LogisticRegression(max_iter=1000)),
        "random_forest": make_pipeline(
            tree_pre, RandomForestClassifier(n_estimators=300, min_samples_leaf=5, random_state=0)
        ),
        "hist_gb": make_pipeline(
            tree_pre,
            HistGradientBoostingClassifier(
                max_depth=3, learning_rate=0.05, max_iter=200, random_state=0
            ),
        ),
    }


def top_decile_lift(y: np.ndarray, p: np.ndarray) -> float:
    k = max(1, len(y) // 10)
    top = np.argsort(-p)[:k]
    return float(y[top].mean() / y.mean())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=Path("ml/out/leads.csv"))
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    rows, y = load(a.data)
    X = matrix(rows)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, stratify=y, random_state=a.seed)

    base = np.full(len(y_te), y_tr.mean())
    results = {"base_rate": base}
    for name, model in build_models().items():
        model.fit(X_tr, y_tr)
        results[name] = model.predict_proba(X_te)[:, 1]

    print(f"train={len(y_tr)} test={len(y_te)} positive rate={y.mean():.1%}\n")
    print(f"{'model':<14}{'ROC-AUC':>9}{'PR-AUC':>9}{'Brier':>8}{'Lift@10%':>10}")
    for name, p in results.items():
        auc = roc_auc_score(y_te, p) if name != "base_rate" else 0.5
        print(
            f"{name:<14}{auc:>9.3f}{average_precision_score(y_te, p):>9.3f}"
            f"{brier_score_loss(y_te, p):>8.3f}{top_decile_lift(y_te, p):>10.2f}"
        )

    best = max(
        (n for n in results if n != "base_rate"), key=lambda n: roc_auc_score(y_te, results[n])
    )
    print(f"\nCalibration of {best} (predicted vs observed, 5 bins):")
    obs, pred = calibration_curve(y_te, results[best], n_bins=5, strategy="quantile")
    for o, p_ in zip(obs, pred, strict=True):
        print(f"  predicted {p_:.2f}  observed {o:.2f}")


if __name__ == "__main__":
    main()
