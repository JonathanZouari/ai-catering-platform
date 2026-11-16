"""Writes one self-contained HTML report on the lead score and the purchase model.

    uv run --with plotly --with scikit-learn python -m scripts.lead_report [--out report.html]

Reads `lead_outcomes` from the throwaway synthetic database (name must contain "test"),
trains the logistic regression on a random split, and compares it with the rule-based score
`rules-1`. The file works offline: the charts and their script are inside it. It only reads.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from sklearn.calibration import calibration_curve
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from scripts import test_database
from scripts.train_lead_model import NAMES, default_url, load

STYLE = """
body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#f6f7f9;color:#1c2330}
main{max-width:1180px;margin:0 auto;padding:24px 20px 48px}
h1{margin:0 0 4px}h2{margin:32px 0 10px;font-size:1.15rem}
.note{background:#fff8e1;border:1px solid #f0d98a;padding:10px 14px;border-radius:8px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}
.kpi{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px #0001}
.kpi b{display:block;font-size:1.6rem}.kpi span{color:#596273;font-size:.85rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:14px}
.card{background:#fff;border-radius:10px;padding:8px;box-shadow:0 1px 3px #0001}
table{border-collapse:collapse;width:100%;background:#fff;border-radius:10px}
th,td{padding:8px 12px;text-align:right;border-bottom:1px solid #e6e9ef}
th:first-child,td:first-child{text-align:left}
.win{font-weight:700;color:#12713a}
@media(max-width:560px){.grid{grid-template-columns:1fr}}
"""


def metrics(truth, probability, threshold=0.5) -> dict:
    predicted = (probability >= threshold).astype(int)
    return {
        "ROC AUC": roc_auc_score(truth, probability),
        "Accuracy": accuracy_score(truth, predicted),
        "Precision": precision_score(truth, predicted, zero_division=0),
        "Recall": recall_score(truth, predicted, zero_division=0),
        "Brier (lower is better)": brier_score_loss(truth, probability),
    }


def chart(figure) -> str:
    figure.update_layout(margin={"l": 50, "r": 20, "t": 50, "b": 45}, height=380)
    return f'<div class="card">{figure.to_html(full_html=False, include_plotlyjs=False)}</div>'


def build(url: str, train_share: float, seed: int) -> str:
    test_database.require_test_database(url)
    matrix, labels, rules = load(url)
    train_x, test_x, train_y, test_y, _, test_rules = train_test_split(
        matrix, labels, rules, train_size=train_share, random_state=seed, stratify=labels
    )
    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(max_iter=1000),
    )
    folds = cross_val_score(model, train_x, train_y, cv=5, scoring="roc_auc")
    model.fit(train_x, train_y)
    prob = model.predict_proba(test_x)[:, 1]

    scores = {"Logistic regression": metrics(test_y, prob), "rules-1": metrics(test_y, test_rules)}
    best = {
        key: max(scores, key=lambda n: scores[n][key] * (-1 if "Brier" in key else 1))
        for key in scores["rules-1"]
    }
    rows = "".join(
        f"<tr><td>{key}</td>"
        + "".join(
            f'<td class="{"win" if best[key] == name else ""}">{scores[name][key]:.3f}</td>'
            for name in scores
        )
        + "</tr>"
        for key in best
    )
    head = "<tr><th>Test set</th><th>Logistic regression</th><th>rules-1</th></tr>"
    table = f"<table>{head}{rows}</table>"

    roc = go.Figure()
    for name, p in (("Logistic regression", prob), ("rules-1", test_rules)):
        fpr, tpr, _ = roc_curve(test_y, p)
        roc.add_scatter(x=fpr, y=tpr, name=f"{name} (AUC {roc_auc_score(test_y, p):.2f})")
    roc.add_scatter(x=[0, 1], y=[0, 1], name="Chance", line={"dash": "dot", "color": "gray"})
    roc.update_layout(
        title="ROC curve", xaxis_title="False positive rate", yaxis_title="True positive rate"
    )

    cal = go.Figure()
    for name, p in (("Logistic regression", prob), ("rules-1", test_rules)):
        actual, predicted = calibration_curve(test_y, p, n_bins=6, strategy="quantile")
        cal.add_scatter(x=predicted, y=actual, mode="lines+markers", name=name)
    cal.add_scatter(x=[0, 1], y=[0, 1], name="Perfect", line={"dash": "dot", "color": "gray"})
    cal.update_layout(
        title="Calibration: does a 60% score win ~60% of the time?",
        xaxis_title="Predicted probability",
        yaxis_title="Share that actually won",
    )

    frame = pd.DataFrame({"rules-1 score": rules, "Outcome": np.where(labels == 1, "won", "lost")})
    dist = px.histogram(
        frame,
        x="rules-1 score",
        color="Outcome",
        nbins=25,
        barmode="overlay",
        opacity=0.65,
        title="rules-1 score by outcome (all decided leads)",
    )

    bands = pd.cut(
        rules, [0, 0.4, 0.65, 1.0], labels=["low", "medium", "high"], include_lowest=True
    )
    rates = pd.DataFrame({"band": bands, "won": labels}).groupby("band", observed=True)["won"]
    rates = rates.agg(["mean", "count"]).reset_index()
    band = px.bar(
        rates,
        x="band",
        y="mean",
        text=rates["count"].map(lambda n: f"{n} leads"),
        title="Win rate per rules-1 band (what the caterer sees)",
    )
    band.update_yaxes(range=[0, 1], tickformat=".0%", title="Win rate")

    names = NAMES + [f"{NAMES[i]} (missing)" for i in model[0].indicator_.features_]
    effects = pd.DataFrame({"feature": names, "coefficient": model[-1].coef_[0]})
    effects = effects.reindex(effects["coefficient"].abs().sort_values().index)
    coef = px.bar(
        effects,
        x="coefficient",
        y="feature",
        orientation="h",
        title="Logistic regression effects (standardized)",
    )

    tn, fp, fn, tp = confusion_matrix(test_y, (prob >= 0.5).astype(int)).ravel()
    conf = px.imshow(
        [[tn, fp], [fn, tp]],
        text_auto=True,
        x=["Predicted lost", "Predicted won"],
        y=["Actually lost", "Actually won"],
        color_continuous_scale="Blues",
        title="Confusion matrix, test set (threshold 0.50)",
    )

    kpis = [
        (f"{len(labels)}", "decided leads"),
        (f"{labels.mean():.1%}", "won"),
        (
            f"{len(train_y)} / {len(test_y)}",
            f"train / test ({train_share:.0%} / {1 - train_share:.0%})",
        ),
        (f"{folds.mean():.3f}", f"5-fold CV AUC on train (± {folds.std():.3f})"),
    ]
    kpi_html = "".join(f'<div class="kpi"><b>{v}</b><span>{k}</span></div>' for v, k in kpis)
    charts = "".join(chart(f) for f in (roc, cal, dist, band, coef, conf))
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lead purchase model</title>
<style>{STYLE}</style><script>{get_plotlyjs()}</script>
<main><h1>Lead purchase model</h1>
<p class="note">The outcomes are synthetic, generated by a hidden formula plus noise, so this shows
the pipeline works, not how real customers behave. The model is not used by the app yet.</p>
<div class="kpis">{kpi_html}</div>
<h2>Model vs. rule-based score (test set, best value in green)</h2>{table}
<h2>Charts</h2><div class="grid">{charts}</div></main></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the lead model report as HTML.")
    parser.add_argument("--out", default="lead_report.html")
    parser.add_argument("--database-url")
    parser.add_argument("--train-share", type=float, default=0.88)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    html = build(args.database_url or default_url(), args.train_share, args.seed)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"Wrote {Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
