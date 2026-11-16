"""Train a logistic-regression purchase predictor: 80% train / 20% held-out test."""

import json

import joblib
import numpy as np
from common import CATEGORICAL, DATA_DIR, MODEL_PATH, NUMERIC, connect
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 42


def load() -> tuple[np.ndarray, np.ndarray]:
    cols = NUMERIC + CATEGORICAL
    with connect() as conn:
        rows = conn.execute(
            f"select {', '.join(cols)}, is_buyer from leads where is_buyer is not null"  # noqa: S608
        ).fetchall()
    X = np.array([r[:-1] for r in rows], dtype=object)
    y = np.array([r[-1] for r in rows])
    return X, y


def main() -> None:
    X, y = load()
    idx_num = list(range(len(NUMERIC)))
    idx_cat = list(range(len(NUMERIC), len(NUMERIC) + len(CATEGORICAL)))

    # Random 80/20 split; stratify keeps the buyer ratio equal in both sets.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y
    )

    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), idx_num),
            ("cat", OneHotEncoder(handle_unknown="ignore"), idx_cat),
        ]
    )
    model = Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=1000))])

    # Validation on the training portion only (5-fold CV): the test set stays untouched.
    cv_auc = cross_val_score(model, X_train, y_train, cv=5, scoring="roc_auc")

    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, pred).ravel()

    cat_names = model.named_steps["pre"].named_transformers_["cat"].get_feature_names_out(
        CATEGORICAL
    )
    names = NUMERIC + list(cat_names)
    coefs = sorted(
        zip(names, model.named_steps["clf"].coef_[0], strict=True), key=lambda t: -abs(t[1])
    )

    report = {
        "n_train": len(y_train),
        "n_test": len(y_test),
        "buyer_rate_train": round(float(y_train.mean()), 3),
        "buyer_rate_test": round(float(y_test.mean()), 3),
        "cv_auc_train_mean": round(float(cv_auc.mean()), 3),
        "cv_auc_train_std": round(float(cv_auc.std()), 3),
        "test": {
            "accuracy": round(accuracy_score(y_test, pred), 3),
            "precision": round(precision_score(y_test, pred), 3),
            "recall": round(recall_score(y_test, pred), 3),
            "f1": round(f1_score(y_test, pred), 3),
            "roc_auc": round(roc_auc_score(y_test, proba), 3),
            "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        },
        "coefficients_standardised": {k: round(float(v), 3) for k, v in coefs},
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    (DATA_DIR / "lead_model_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
