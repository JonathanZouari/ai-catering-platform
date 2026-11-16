"""Train the lead closing-probability model.

    uv run python -m app.ml.train --data data/leads.csv --out models --data-source real
    uv run python -m app.ml.train --data data/leads_synthetic.csv --data-source synthetic

Input: a CSV export of the `lead_training_data` view (closed leads, one row each).
Output, in --out:
    lead-model-<version>.joblib   artifact {model, features, threshold, version, metrics, ...};
                                  load it with app.ml.scoring
    metrics-<version>.json        the same metrics, readable

Method: older leads train, the newest quarter tests (time split, no peeking at the future).
A baseline that always predicts the training win rate, a logistic regression and a
gradient-boosted tree are compared by time-series cross-validation on the training part.
The winner is scored once on the test part, then refit on all data for the saved artifact.
A model trained on synthetic data is named `synthetic-...` so it cannot be mistaken for a real one.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.features import (
    BOOLEAN,
    CATEGORICAL,
    FEATURES,
    LABEL,
    NUMERIC,
    TIME_COLUMN,
    build_features,
    load_training_frame,
)

MIN_ROWS = 100
MIN_PER_CLASS = 20
# The tree must beat the simpler logistic model by this much cross-validated AUC to be chosen.
TREE_MARGIN = 0.01


class NotEnoughDataError(ValueError):
    pass


def _preprocess(scale: bool) -> ColumnTransformer:
    numeric = [("impute", SimpleImputer(strategy="median"))]
    if scale:
        numeric.append(("scale", StandardScaler()))
    return ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", Pipeline(numeric), NUMERIC),
            ("bool", "passthrough", BOOLEAN),
        ]
    )


def make_model(kind: str, seed: int) -> Pipeline:
    if kind == "baseline":
        return Pipeline([("prep", _preprocess(False)), ("clf", DummyClassifier(strategy="prior"))])
    if kind == "logistic":
        clf = LogisticRegression(max_iter=1000, C=1.0)
        return Pipeline([("prep", _preprocess(True)), ("clf", clf)])
    if kind == "tree":
        clf = HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=150, random_state=seed
        )
        return Pipeline([("prep", _preprocess(False)), ("clf", clf)])
    raise ValueError(kind)


def check_enough_data(df: pd.DataFrame, min_rows: int, min_per_class: int) -> None:
    counts = df[LABEL].value_counts()
    won, lost = int(counts.get(True, 0)), int(counts.get(False, 0))
    if len(df) < min_rows or min(won, lost) < min_per_class:
        raise NotEnoughDataError(
            f"need at least {min_rows} closed leads and {min_per_class} of each class; "
            f"got {len(df)} (won {won}, lost {lost}). Use --min-rows/--min-per-class to override."
        )


def time_split(df: pd.DataFrame, test_fraction: float = 0.25) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Oldest leads train, newest test. Rows are sorted by created_at; the split is by position."""
    ordered = df.sort_values(TIME_COLUMN, kind="stable").reset_index(drop=True)
    cut = round(len(ordered) * (1 - test_fraction))
    return ordered.iloc[:cut], ordered.iloc[cut:]


def evaluate(y: np.ndarray, p: np.ndarray, threshold: float, train_rate: float) -> dict:
    pred = p >= threshold
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[False, True]).ravel()
    single_class = len(set(y.tolist())) < 2
    bins = pd.qcut(pd.Series(p).rank(method="first"), q=min(5, len(p)), labels=False).to_numpy()
    calibration = [
        {
            "n": int((bins == b).sum()),
            "mean_predicted": round(float(p[bins == b].mean()), 3),
            "observed_rate": round(float(y[bins == b].mean()), 3),
        }
        for b in sorted(set(bins.tolist()))
    ]
    constant = np.full(len(y), train_rate)
    return {
        "n": len(y),
        "base_rate": round(float(y.mean()), 3),
        "roc_auc": None if single_class else round(float(roc_auc_score(y, p)), 4),
        "pr_auc": None if single_class else round(float(average_precision_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "brier_constant_baseline": round(float(brier_score_loss(y, constant)), 4),
        "log_loss": round(float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[False, True])), 4),
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "calibration": calibration,
    }


def cross_validated_auc(kind: str, x: pd.DataFrame, y: np.ndarray, seed: int) -> float:
    scores = cross_val_score(
        make_model(kind, seed),
        x,
        y,
        cv=TimeSeriesSplit(n_splits=4),
        scoring="roc_auc",
        error_score=np.nan,
    )
    return float(np.nanmean(scores))


def top_coefficients(model: Pipeline, k: int = 10) -> list[dict]:
    names = model.named_steps["prep"].get_feature_names_out()
    coefs = model.named_steps["clf"].coef_[0]
    order = np.argsort(-np.abs(coefs))[:k]
    return [{"feature": str(names[i]), "coef": round(float(coefs[i]), 3)} for i in order]


def data_fingerprint(df: pd.DataFrame) -> str:
    cols = sorted(df.columns)
    hashed = pd.util.hash_pandas_object(df[cols].astype(str), index=False).to_numpy()
    return hashlib.sha256(hashed.tobytes()).hexdigest()[:8]


def train(
    df: pd.DataFrame,
    *,
    data_source: str,
    threshold: float = 0.5,
    min_rows: int = MIN_ROWS,
    min_per_class: int = MIN_PER_CLASS,
    seed: int = 42,
) -> dict:
    """Run the whole pipeline and return the artifact (not yet saved)."""
    check_enough_data(df, min_rows, min_per_class)
    train_df, test_df = time_split(df)
    x_train, y_train = build_features(train_df), train_df[LABEL].to_numpy(dtype=bool)
    x_test, y_test = build_features(test_df), test_df[LABEL].to_numpy(dtype=bool)
    train_rate = float(y_train.mean())

    cv = {k: cross_validated_auc(k, x_train, y_train, seed) for k in ("logistic", "tree")}
    chosen = "tree" if cv["tree"] > cv["logistic"] + TREE_MARGIN else "logistic"

    test_metrics = {}
    for kind in ("baseline", chosen):
        fitted = make_model(kind, seed).fit(x_train, y_train)
        proba = fitted.predict_proba(x_test)[:, 1]
        test_metrics[kind] = evaluate(y_test, proba, threshold, train_rate)

    final = make_model(chosen, seed).fit(build_features(df), df[LABEL].to_numpy(dtype=bool))
    version = f"{data_source}-{chosen}-{datetime.now(UTC):%Y%m%d}-{data_fingerprint(df)}"
    metrics = {
        "version": version,
        "data_source": data_source,
        "chosen_model": chosen,
        "threshold": threshold,
        "rows": {"total": len(df), "train": len(train_df), "test": len(test_df)},
        "train_period": [str(train_df[TIME_COLUMN].min()), str(train_df[TIME_COLUMN].max())],
        "test_period": [str(test_df[TIME_COLUMN].min()), str(test_df[TIME_COLUMN].max())],
        "cv_roc_auc_on_train": {k: round(v, 4) for k, v in cv.items()},
        "test": test_metrics,
        "top_coefficients": top_coefficients(final) if chosen == "logistic" else None,
        "warning": (
            "Trained on SYNTHETIC data: it learned the generator's formula, not real customers."
            if data_source == "synthetic"
            else None
        ),
    }
    return {
        "model": final,
        "features": FEATURES,
        "threshold": threshold,
        "version": version,
        "trained_at": datetime.now(UTC).isoformat(),
        "metrics": metrics,
    }


def save(artifact: dict, out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    version = artifact["version"]
    model_path = out / f"lead-model-{version}.joblib"
    metrics_path = out / f"metrics-{version}.json"
    joblib.dump(artifact, model_path)
    metrics_path.write_text(
        json.dumps(artifact["metrics"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return model_path, metrics_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--data", required=True, help="CSV export of lead_training_data")
    ap.add_argument("--out", default="models")
    ap.add_argument("--data-source", choices=["real", "synthetic"], required=True)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--min-rows", type=int, default=MIN_ROWS)
    ap.add_argument("--min-per-class", type=int, default=MIN_PER_CLASS)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    artifact = train(
        load_training_frame(args.data),
        data_source=args.data_source,
        threshold=args.threshold,
        min_rows=args.min_rows,
        min_per_class=args.min_per_class,
        seed=args.seed,
    )
    model_path, metrics_path = save(artifact, args.out)
    m = artifact["metrics"]
    t, b = m["test"][m["chosen_model"]], m["test"]["baseline"]
    print(
        f"version: {m['version']}  (chosen: {m['chosen_model']}, cv auc {m['cv_roc_auc_on_train']})"
    )
    print(
        f"test n={t['n']}  roc_auc={t['roc_auc']}  pr_auc={t['pr_auc']}  brier={t['brier']} "
        f"(constant baseline {b['brier']})  accuracy={t['accuracy']}"
    )
    if m["warning"]:
        print(f"WARNING: {m['warning']}")
    print(f"saved: {model_path}\n       {metrics_path}")


if __name__ == "__main__":
    main()
