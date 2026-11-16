"""Compare random vs time-based train/test splits for the lead purchase model.

Both methods train the same logistic regression. Each split gives an *estimate* of how the model
will score on future leads. Because the data is synthetic, we can also generate a truly unseen
future period and measure the *actual* score, then see which estimate was closer.

Usage (from backend/):  uv run --group ml python -m ml.compare_splits
"""

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.generate_leads import generate

HERE = Path(__file__).parent
TARGET = "purchased"
# Identity, raw dates and age_group (fairness) are deliberately not features.
CATEGORICAL = [
    "event_type",
    "fulfillment",
    "city",
    "customer_type",
    "preferred_contact",
    "kashrut",
    "venue_type",
    "device",
    "browser",
    "os",
    "browser_language",
    "traffic_source",
    "days_bucket",
]
NUMERIC = [
    "log_guests",
    "vegetarian_share",
    "restricted_share",
    "has_notes",
    "has_phone",
    "has_email",
    "is_past_customer",
    "log_past_spend",
    "marketing_consent",
    "requested_callback",
    "budget_given",
    "budget_low",
    "hour_sin",
    "hour_cos",
    "night_visit",
    "log_time_on_site",
    "pages_viewed",
    "viewed_menu",
    "bot_like_form",
    "returning_visitor",
    "used_ai_chat",
    "has_draft",
    "log_draft_total",
]
METRICS = {
    "roc_auc": "ROC-AUC",
    "average_precision": "PR-AUC",
    "brier": "Brier",
    "log_loss": "LogLoss",
}


def features(df: pd.DataFrame) -> pd.DataFrame:
    """Turn raw lead columns into model inputs. Uses only what is known at submission time."""
    guests = df["adults"] + df["children"]
    budget = pd.to_numeric(df["budget_per_guest_ils"], errors="coerce")
    days = df["days_until_event"]
    out = pd.DataFrame(
        {
            "log_guests": np.log1p(guests),
            "vegetarian_share": df["vegetarian"] / guests,
            "restricted_share": df["restricted"] / guests,
            "has_notes": (df["notes_length"] > 0).astype(int),
            "log_past_spend": np.log1p(df["past_spend_ils"]),
            "budget_given": budget.notna().astype(int),
            "budget_low": (budget < 70).astype(int),
            "hour_sin": np.sin(2 * np.pi * df["visit_hour"] / 24),
            "hour_cos": np.cos(2 * np.pi * df["visit_hour"] / 24),
            "night_visit": (df["visit_hour"] < 6).astype(int),
            "log_time_on_site": np.log(df["time_on_site_sec"]),
            "bot_like_form": (df["form_fill_sec"] < 15).astype(int),
            "has_draft": (df["dishes_in_draft"] > 0).astype(int),
            "log_draft_total": np.log1p(df["draft_total_ils"]),
            "days_bucket": pd.cut(days, [0, 3, 90, 10_000], labels=["short", "normal", "far"]),
        }
    )
    passthrough = [c for c in NUMERIC + CATEGORICAL if c in df.columns]
    out[passthrough] = df[passthrough]
    out[CATEGORICAL] = out[CATEGORICAL].astype(str).replace({"": "missing", "nan": "missing"})
    return out[NUMERIC + CATEGORICAL]


def make_model() -> Pipeline:
    prep = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CATEGORICAL),
        ]
    )
    return Pipeline([("prep", prep), ("clf", LogisticRegression(max_iter=2000))])


def score(model: Pipeline, x: pd.DataFrame, y: pd.Series) -> dict:
    p = model.predict_proba(x)[:, 1]
    return {
        "roc_auc": roc_auc_score(y, p),
        "average_precision": average_precision_score(y, p),
        "brier": brier_score_loss(y, p),
        "log_loss": log_loss(y, p),
    }


def evaluate(df: pd.DataFrame, future: pd.DataFrame, seed: int = 0) -> dict:
    x, y = features(df), df[TARGET]
    xf, yf = features(future), future[TARGET]
    cut = int(len(df) * 0.8)
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(len(df))
    splits = {
        "random": (shuffled[:cut], shuffled[cut:]),
        "time": (np.arange(cut), np.arange(cut, len(df))),
    }
    cvs = {
        "random": StratifiedKFold(5, shuffle=True, random_state=seed),
        "time": TimeSeriesSplit(5),
    }
    scoring = {"roc_auc": "roc_auc", "average_precision": "average_precision",
               "brier": "neg_brier_score", "log_loss": "neg_log_loss"}  # fmt: skip

    results = {}
    for name, (train, test) in splits.items():
        model = make_model().fit(x.iloc[train], y.iloc[train])
        cv = cross_validate(make_model(), x, y, cv=cvs[name], scoring=scoring)
        results[name] = {
            "holdout": score(model, x.iloc[test], y.iloc[test]),
            "cv_mean": {k: abs(cv[f"test_{k}"].mean()) for k in scoring},
            "cv_std": {k: cv[f"test_{k}"].std() for k in scoring},
            "future": score(model, xf, yf),
        }
    return results


def run_scenario(drift: float, repeats: int, rows: int) -> list[dict]:
    """Train on a fresh 2025 sample and score on a fresh 2026 sample, `repeats` times."""
    runs = []
    for k in range(repeats):
        past = pd.DataFrame(generate(rows, seed=1000 + k, drift=drift))
        future = pd.DataFrame(generate(rows, seed=2000 + k, start=date(2026, 1, 1), drift=drift))
        runs.append(evaluate(past, future, seed=k))
    return runs


def report_table(runs: list[dict]) -> list[str]:
    lines = [
        "| Metric | Method | Holdout estimate | CV estimate | Actual on future "
        "| Mean holdout error | Mean CV error | CV closer in |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for key, label in METRICS.items():
        errs = {
            m: np.array([abs(r[m]["cv_mean"][key] - r[m]["future"][key]) for r in runs])
            for m in ("random", "time")
        }
        for method, other in (("random", "time"), ("time", "random")):
            mean = {
                part: np.mean([r[method][part][key] for r in runs])
                for part in ("holdout", "cv_mean", "future")
            }
            hold_err = np.mean(
                [abs(r[method]["holdout"][key] - r[method]["future"][key]) for r in runs]
            )
            wins = int((errs[method] < errs[other]).sum())
            lines.append(
                f"| {label} | {method} | {mean['holdout']:.3f} | {mean['cv_mean']:.3f} "
                f"| {mean['future']:.3f} | {hold_err:.3f} | {errs[method].mean():.3f} "
                f"| {wins}/{len(runs)} |"
            )
    return lines


def report(scenarios: dict, repeats: int, rows: int) -> str:
    lines = [
        "# Random vs time-based split: comparison",
        "",
        f"Each scenario is repeated {repeats} times. Each one trains on {rows} fresh 2025 leads",
        f"and scores on {rows} fresh 2026 leads that no split has seen. Values are means over",
        "repeats. **Error** = |estimate - actual future score|: smaller means the method predicts",
        "real-world performance more honestly. *CV closer in* counts the repeats where this",
        "method's CV estimate beat the other method's. Higher is better for ROC-AUC and PR-AUC,",
        "lower is better for Brier and LogLoss.",
    ]
    for title, runs in scenarios.items():
        lines += ["", f"## {title}", ""] + report_table(runs)
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repeats", type=int, default=10)
    p.add_argument("--rows", type=int, default=5000)
    p.add_argument("--out", type=Path, default=HERE / "reports" / "split_comparison.md")
    args = p.parse_args()

    scenarios = {
        "Scenario 1: stable market (no drift)": run_scenario(0.0, args.repeats, args.rows),
        "Scenario 2: market changes over time (drift)": run_scenario(1.0, args.repeats, args.rows),
    }
    text = report(scenarios, args.repeats, args.rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
