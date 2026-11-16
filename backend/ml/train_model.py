"""Train the final lead purchase model with a time-based protocol.

1. Sort leads by time. The first 80% is for development, the last 20% is the test period.
2. Tune regularization (C) with TimeSeriesSplit on the development part only.
3. Score the tuned model once on the test period: this is the number to report.
4. Refit on all leads and save the model.

Usage (from backend/):  uv run --group ml python -m ml.train_model
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

from ml.compare_splits import TARGET, features, make_model, score

HERE = Path(__file__).parent
C_GRID = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)
    return df.sort_values("created_at", kind="stable").reset_index(drop=True)


def calibration_table(y: pd.Series, p: np.ndarray, bins: int = 5) -> list[dict]:
    """Leads grouped by predicted probability (quantiles): predicted vs actual purchase rate."""
    groups = pd.qcut(p, bins, labels=False, duplicates="drop")
    frame = pd.DataFrame({"p": p, "y": y.to_numpy(), "g": groups})
    return [
        {"group": int(g) + 1, "leads": len(d), "predicted": d["p"].mean(), "actual": d["y"].mean()}
        for g, d in frame.groupby("g")
    ]


def coefficients(model) -> pd.Series:
    names = model.named_steps["prep"].get_feature_names_out()
    coefs = pd.Series(model.named_steps["clf"].coef_[0], index=names)
    return coefs.reindex(coefs.abs().sort_values(ascending=False).index)


def train(df: pd.DataFrame) -> dict:
    x, y = features(df), df[TARGET]
    cut = int(len(df) * 0.8)
    x_dev, y_dev, x_test, y_test = x.iloc[:cut], y.iloc[:cut], x.iloc[cut:], y.iloc[cut:]

    search = GridSearchCV(
        make_model(),
        {"clf__C": C_GRID},
        cv=TimeSeriesSplit(5),
        scoring="average_precision",
    ).fit(x_dev, y_dev)
    best_c = search.best_params_["clf__C"]

    p_test = search.best_estimator_.predict_proba(x_test)[:, 1]
    test_scores = score(search.best_estimator_, x_test, y_test)
    top = p_test >= np.quantile(p_test, 0.8)

    final = make_model().set_params(clf__C=best_c).fit(x, y)
    return {
        "model": final,
        "best_c": best_c,
        "cv_score": search.best_score_,
        "test": test_scores,
        "base_rate_test": y_test.mean(),
        "top20_rate": y_test[top].mean(),
        "top20_share_of_buyers": y_test[top].sum() / y_test.sum(),
        "calibration": calibration_table(y_test, p_test),
        "coefficients": coefficients(final),
        "period": (df["created_at"].iloc[0], df["created_at"].iloc[cut], df["created_at"].iloc[-1]),
        "n": (cut, len(df) - cut),
    }


def report(r: dict) -> str:
    start, test_start, end = r["period"]
    t = r["test"]
    lines = [
        "# Lead purchase model: final training report",
        "",
        f"Trained {datetime.now():%Y-%m-%d} on synthetic data. Logistic regression, time-based.",
        "",
        "## Protocol",
        "",
        f"- Development: {r['n'][0]} leads, {start} to {test_start}. "
        f"Tuned C over {C_GRID} with TimeSeriesSplit(5), scored by PR-AUC.",
        f"- Test period: {r['n'][1]} leads, {test_start} to {end}. Scored once.",
        f"- Chosen C = {r['best_c']} (CV PR-AUC {r['cv_score']:.3f}).",
        "- Final model refit on all leads with that C: `models/lead_model.joblib`.",
        "",
        "## Test-period scores (the numbers to report)",
        "",
        "| Metric | Model | Baseline (always predict the base rate) |",
        "|---|---|---|",
        f"| ROC-AUC | {t['roc_auc']:.3f} | 0.500 |",
        f"| PR-AUC | {t['average_precision']:.3f} | {r['base_rate_test']:.3f} |",
        f"| Brier | {t['brier']:.3f} | {r['base_rate_test'] * (1 - r['base_rate_test']):.3f} |",
        f"| LogLoss | {t['log_loss']:.3f} | - |",
        "",
        f"Top 20% of leads by score buy at {r['top20_rate']:.1%} "
        f"(vs {r['base_rate_test']:.1%} overall) and hold "
        f"{r['top20_share_of_buyers']:.0%} of all buyers.",
        "",
        "## Calibration on the test period",
        "",
        "| Score group (low to high) | Leads | Predicted rate | Actual rate |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {c['group']} | {c['leads']} | {c['predicted']:.1%} | {c['actual']:.1%} |"
        for c in r["calibration"]
    ]
    lines += [
        "",
        "## Strongest features (final model)",
        "",
        "Coefficients are log-odds per one standard deviation (numeric) or vs. the other",
        "categories (one-hot). Positive raises the purchase probability.",
        "",
        "| Feature | Coefficient |",
        "|---|---|",
    ]
    lines += [f"| `{name}` | {value:+.3f} |" for name, value in r["coefficients"].head(20).items()]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", type=Path, default=HERE / "data" / "leads_synthetic.csv")
    p.add_argument("--model-out", type=Path, default=HERE / "models" / "lead_model.joblib")
    p.add_argument("--report-out", type=Path, default=HERE / "reports" / "final_model.md")
    args = p.parse_args()

    r = train(load(args.data))
    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    # joblib uses pickle: only ever load a model file this project produced itself.
    joblib.dump(r["model"], args.model_out)
    meta = {"C": r["best_c"], "test": r["test"], "trained_on": str(args.data.name)}
    args.model_out.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    text = report(r)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
