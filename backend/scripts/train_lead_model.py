"""Trains a logistic regression that predicts whether a lead ends as won (a purchase).

    uv run --with scikit-learn python -m scripts.train_lead_model

Reads the real outcomes in `lead_outcomes` (features captured when the score was made),
splits them at random into training and test sets, and compares the model with the
rule-based score `rules-1` on the same test rows. Nothing is written back and the app does
not use the result yet: moving from rules to a model needs real data and your approval
(docs/OPEN_DECISIONS.md).
"""

import argparse
import os
from pathlib import Path

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.services.lead_scoring import Features
from scripts import test_database
from scripts.synthetic_leads import DEFAULT_DATABASE, LOCAL_ENV

NAMES = list(Features().as_dict())


def default_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url and Path(LOCAL_ENV).exists():
        for line in Path(LOCAL_ENV).read_text(encoding="utf-8").splitlines():
            if line.startswith("TEST_DATABASE_URL="):
                url = line.split("=", 1)[1]
    if not url:
        raise SystemExit("Set TEST_DATABASE_URL (or pass --database-url).")
    return make_url(url).set(database=DEFAULT_DATABASE).render_as_string(hide_password=False)


def load(url: str):
    engine = create_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(
            text("select outcome, score_at_decision, features from lead_outcomes order by lead_id")
        ).all()
    # Unknown stays unknown: a missing value stays NaN here, then gets an indicator column.
    matrix = np.array(
        [
            [np.nan if row.features[name] is None else float(row.features[name]) for name in NAMES]
            for row in rows
        ]
    )
    labels = np.array([1 if row.outcome == "won" else 0 for row in rows])
    rules = np.array([float(row.score_at_decision) for row in rows])
    return matrix, labels, rules


def report(name: str, truth, probability) -> None:
    predicted = (probability >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(truth, predicted).ravel()
    print(f"\n{name}")
    print(f"  ROC AUC   {roc_auc_score(truth, probability):.3f}")
    print(f"  Accuracy  {accuracy_score(truth, predicted):.3f}")
    print(f"  Precision {precision_score(truth, predicted, zero_division=0):.3f}")
    print(f"  Recall    {recall_score(truth, predicted, zero_division=0):.3f}")
    print(f"  Brier     {brier_score_loss(truth, probability):.3f}  (lower is better)")
    print(f"  Confusion tn={tn} fp={fp} fn={fn} tp={tp}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and test the lead purchase model.")
    parser.add_argument("--database-url")
    parser.add_argument("--train-share", type=float, default=0.88)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    url = args.database_url or default_url()
    test_database.require_test_database(url)
    matrix, labels, rules = load(url)
    print(f"{len(labels)} leads, {labels.mean():.1%} won")

    # A random split, stratified so both sets keep the same share of purchases.
    train_x, test_x, train_y, test_y, _, test_rules = train_test_split(
        matrix, labels, rules, train_size=args.train_share, random_state=args.seed, stratify=labels
    )
    print(f"train {len(train_y)} ({len(train_y) / len(labels):.0%}), test {len(test_y)}")

    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(max_iter=1000),
    )
    folds = cross_val_score(model, train_x, train_y, cv=5, scoring="roc_auc")
    print(
        f"\n5-fold cross-validation on the training set, ROC AUC: "
        f"{folds.mean():.3f} +/- {folds.std():.3f}"
    )

    model.fit(train_x, train_y)
    report("Logistic regression on the test set", test_y, model.predict_proba(test_x)[:, 1])
    report("Rule-based score rules-1 on the same test set", test_y, test_rules)

    names = NAMES + [f"{NAMES[i]} (missing)" for i in model[0].indicator_.features_]
    coefficients = model[-1].coef_[0]
    print("\nStrongest effects (standardized coefficients):")
    for index in np.argsort(-np.abs(coefficients))[:8]:
        print(f"  {names[index]:<38} {coefficients[index]:+.2f}")


if __name__ == "__main__":
    main()
