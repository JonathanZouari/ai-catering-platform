"""Predict whether a customer ordered (has_ordered) and compare several logistic regressions.

Dataset: one row per customer (1,437), including the customers who never ordered.
Only signals known before an order exist are used (city, email present, sign-up date), so the
model is usable on a brand-new lead. Segment, order counts and lifetime value are excluded: they
are derived from has_ordered itself (leakage).

Pipeline order follows the course spec: impute -> scale -> one-hot -> IQR outliers -> split.
The 80/20 split is stratified on has_ordered, so both sets keep the same share of customers who
ordered and who did not.

With --enriched the SYNTHETIC lead-behaviour columns from enrich_synthetic_data.py are added
(lead source, response time, budget, ...). They are invented, so the improvement they show is
true by construction.

Usage (from backend/):  python scripts/train_logistic_models.py [--enriched]
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "combined_clients_orders.csv"
ENRICHED_SOURCE = ROOT / "data" / "combined_clients_orders_enriched.csv"
OUT_CSV = ROOT / "data" / "customers_preprocessed.csv"
OUT_PNG = ROOT / "docs" / "roc_logistic_models.png"
OUT_PNG_ENRICHED = ROOT / "docs" / "roc_logistic_models_enriched.png"
TARGET = "has_ordered"
NUMERIC = ["tenure_days", "signup_month"]
CATEGORICAL = ["customer_city", "has_email"]
EXTRA_NUMERIC = [
    "response_time_hours",
    "lead_time_days",
    "interactions_count",
    "site_visits",
    "stated_budget",
]
EXTRA_CATEGORICAL = ["lead_source", "requested_quote"]
RANDOM_STATE = 42


def columns(enriched: bool) -> tuple[list[str], list[str]]:
    if enriched:
        return NUMERIC + EXTRA_NUMERIC, CATEGORICAL + EXTRA_CATEGORICAL
    return NUMERIC, CATEGORICAL


def load(enriched: bool = False) -> pd.DataFrame:
    rows = pd.read_csv(ENRICHED_SOURCE if enriched else SOURCE, encoding="utf-8-sig")
    customers = rows.drop_duplicates("customer_id").copy()
    created = pd.to_datetime(customers["customer_created_at"])
    customers["tenure_days"] = (created.max() - created).dt.days
    customers["signup_month"] = created.dt.month
    customers["has_email"] = customers["email"].notna().map({True: "yes", False: "no"})
    customers["customer_city"] = customers["customer_city"].fillna("unknown")
    customers[TARGET] = (customers["has_ordered"] == "yes").astype(int)
    numeric, categorical = columns(enriched)
    return customers[[*numeric, *categorical, TARGET]]


def preprocess(df: pd.DataFrame, enriched: bool = False) -> pd.DataFrame:
    numeric, categorical = columns(enriched)
    df = df.copy()
    df[numeric] = SimpleImputer(strategy="mean").fit_transform(df[numeric])  # 1. missing
    df[numeric] = MinMaxScaler().fit_transform(df[numeric])  # 2. scale 0-1
    encoder = OneHotEncoder(sparse_output=False)  # 3. one-hot
    encoded = pd.DataFrame(
        encoder.fit_transform(df[categorical]),
        columns=encoder.get_feature_names_out(categorical),
        index=df.index,
    )
    df = pd.concat([encoded, df[numeric], df[TARGET]], axis=1)
    q1, q3 = df[numeric].quantile(0.25), df[numeric].quantile(0.75)  # 4. IQR outliers
    iqr = q3 - q1
    inside = ((df[numeric] >= q1 - 1.5 * iqr) & (df[numeric] <= q3 + 1.5 * iqr)).all(axis=1)
    removed = df[~inside][TARGET]
    print(
        f"outliers removed: {len(removed)} of {len(df)} "
        f"(ordered {int(removed.sum())}, not ordered {int((removed == 0).sum())})"
    )
    return df[inside]


MODELS = {
    "1. Plain (no regularization)": LogisticRegression(C=np.inf, max_iter=2000),
    "2. L2, C=1 (default)": LogisticRegression(C=1.0, max_iter=2000),
    "3. L2 strong, C=0.05": LogisticRegression(C=0.05, max_iter=2000),
    "4. L1 (Lasso), C=0.5": LogisticRegression(C=0.5, solver="liblinear", l1_ratio=1),
    "5. L2 balanced classes": LogisticRegression(class_weight="balanced", max_iter=2000),
}


def main(enriched: bool = False) -> None:
    processed = preprocess(load(enriched), enriched)
    processed.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    X, y = processed.drop(columns=TARGET), processed[TARGET]
    print(
        f"customers: {len(y)}  ordered: {y.sum()} ({y.mean():.1%})  not ordered: {(y == 0).sum()}"
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    for name, part in (("train", y_train), ("test", y_test)):
        print(
            f"{name}: {len(part)} rows, ordered {part.sum()} ({part.mean():.1%}), "
            f"not ordered {(part == 0).sum()}"
        )

    cv = StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE)
    plt.figure(figsize=(7, 6))
    print(f"\n{'model':32} {'CV AUC':>8} {'test AUC':>9} {'accuracy':>9}")
    for name, model in MODELS.items():
        cv_auc = cross_val_score(model, X_train, y_train, cv=cv, scoring="roc_auc").mean()
        model.fit(X_train, y_train)
        scores = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, scores)
        acc = accuracy_score(y_test, model.predict(X_test))
        print(f"{name:32} {cv_auc:8.3f} {auc:9.3f} {acc:9.3f}")
        fpr, tpr, _ = roc_curve(y_test, scores)
        plt.plot(fpr, tpr, label=f"{name} (AUC={auc:.3f})")
    plt.plot([0, 1], [0, 1], "k--", label="Random guess (AUC=0.500)")
    plt.xlabel("False positive rate")
    plt.ylabel("True positive rate")
    suffix = " - SYNTHETIC features" if enriched else ""
    plt.title(f"ROC: predicting has_ordered{suffix} (test set)")
    plt.legend(loc="lower right", fontsize=8)
    plt.grid(alpha=0.3)
    out_png = OUT_PNG_ENRICHED if enriched else OUT_PNG
    out_png.parent.mkdir(exist_ok=True)
    plt.savefig(out_png, dpi=130, bbox_inches="tight")
    print(f"\nROC saved -> {out_png}")

    best = MODELS["2. L2, C=1 (default)"]
    top = pd.Series(best.coef_[0], index=X.columns).sort_values(key=abs, ascending=False).head(12)
    print("\nstrongest coefficients (model 2):\n", top.round(2).to_string())


if __name__ == "__main__":
    main("--enriched" in sys.argv)
