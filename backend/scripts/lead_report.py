"""Writes one self-contained HTML report on the lead purchase model.

    uv run --with plotly --with scikit-learn python -m scripts.lead_report [--out report.html]

Reads `lead_outcomes` from the throwaway synthetic database (name must contain "test"),
trains the logistic regression on a random split, and reports how well it predicts. It also
lists every lead with the model's chance to buy next to what really happened. The file works
offline: the charts and their script are inside it. It only reads.
"""

import argparse
import html
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs, get_plotlyjs_version
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
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_predict,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine, text

from scripts import test_database
from scripts.train_lead_model import NAMES, default_url

STYLE = """
body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#f6f7f9;color:#1c2330}
main{max-width:1180px;margin:0 auto;padding:24px 20px 48px}
h1{margin:0 0 4px}h2{margin:32px 0 10px;font-size:1.15rem}
.note{background:#fff8e1;border:1px solid #f0d98a;padding:10px 14px;border-radius:8px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}
.kpi{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px #0001}
.kpi b{display:block;font-size:1.6rem}.kpi span{color:#596273;font-size:.85rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(480px,1fr));gap:14px}
.card{background:#fff;border-radius:10px;padding:8px;box-shadow:0 1px 3px #0001;min-width:0}
table{border-collapse:collapse;width:100%;background:#fff;border-radius:10px}
th,td{padding:8px 12px;text-align:right;border-bottom:1px solid #e6e9ef}
th:first-child,td:first-child{text-align:left}
.tools{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:10px 0}
.tools select,.tools input{padding:7px 10px;border:1px solid #cfd5df;border-radius:8px;font:inherit}
#leads th{cursor:pointer;position:sticky;top:0;background:#eef1f6;white-space:nowrap}
#leads td.l,#leads th.l{text-align:left}
.ok{color:#12713a}.bad{color:#a02323}
.scroll{max-height:640px;overflow:auto;border-radius:10px;box-shadow:0 1px 3px #0001}
@media(max-width:560px){.grid{grid-template-columns:1fr}}
"""

# Filters and click-to-sort for the lead table. Plain JS, nothing loaded from outside.
TABLE_SCRIPT = """
const body=document.querySelector('#leads tbody'),rows=[...body.rows];
const q=document.getElementById('q'),fo=document.getElementById('fo');
const fr=document.getElementById('fr'),fs=document.getElementById('fs');
function apply(){let n=0;rows.forEach(r=>{
const ok=(!q.value||r.cells[0].textContent.includes(q.value))
&&(!fo.value||r.dataset.outcome===fo.value)
&&(!fr.value||r.dataset.right===fr.value)&&(!fs.value||r.dataset.split===fs.value);
r.hidden=!ok;if(ok)n++});
document.getElementById('count').textContent=n+' of '+rows.length+' leads'}
[q,fo,fr,fs].forEach(e=>e.addEventListener('input',apply));apply();
let dir=-1;
function value(r,c){const t=r.cells[c];if(t.dataset.v)return +t.dataset.v;
const n=+t.textContent.replace(/,/g,'');return isNaN(n)?t.textContent:n}
document.querySelectorAll('#leads th').forEach(th=>th.addEventListener('click',()=>{
const c=+th.dataset.col;dir=-dir;
rows.sort((a,b)=>{const x=value(a,c),y=value(b,c);return (x>y?1:x<y?-1:0)*dir});
rows.forEach(r=>body.append(r))}));
"""

COLUMNS = [
    ("Lead", "l"),
    ("Event date", "l"),
    ("Guests", ""),
    ("Total (ILS)", ""),
    ("Model chance to buy", ""),
    ("Actual outcome", ""),
    ("Model at 50%", ""),
    ("Set", ""),
]


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
    body = figure.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True})
    return f'<div class="card">{body}</div>'


def load_leads(url: str) -> list[dict]:
    """One row per decided lead, in a fixed order so a seed gives the same split every run."""
    engine = create_engine(url)
    query = text(
        "select lo.lead_id, lo.outcome, lo.score_at_decision, lo.features, c.full_name, "
        "e.event_date, o.total from lead_outcomes lo "
        "join leads l on l.id = lo.lead_id and l.caterer_id = lo.caterer_id "
        "join orders o on o.id = l.order_id and o.caterer_id = l.caterer_id "
        "join events e on e.id = o.event_id and e.caterer_id = o.caterer_id "
        "join customers c on c.id = o.customer_id and c.caterer_id = o.caterer_id "
        "order by lo.lead_id"
    )
    with engine.connect() as connection:
        return [dict(row._mapping) for row in connection.execute(query)]


def lead_row(row, actual, chance, in_test) -> str:
    right = int(chance >= 0.5) == actual
    return (
        f"<tr data-outcome='{'won' if actual else 'lost'}' "
        f"data-right='{'right' if right else 'wrong'}' "
        f"data-split='{'test' if in_test else 'train'}'>"
        f"<td class='l'>{html.escape(row['full_name'])}</td>"
        f"<td class='l'>{row['event_date']}</td>"
        f"<td>{row['features']['guests']}</td>"
        f"<td>{float(row['total']):,.0f}</td>"
        f"<td data-v='{chance:.4f}'><b>{chance:.0%}</b></td>"
        f"<td>{'won' if actual else 'lost'}</td>"
        f"<td class='{'ok' if right else 'bad'}'>{'correct' if right else 'wrong'}</td>"
        f"<td>{'test' if in_test else 'train'}</td></tr>"
    )


def leads_table(rows, labels, chance, test_mask) -> str:
    order = np.argsort(-chance)
    body = "".join(lead_row(rows[i], labels[i], chance[i], test_mask[i]) for i in order)
    head = "".join(
        f"<th class='{css}' data-col='{i}'>{title}</th>" for i, (title, css) in enumerate(COLUMNS)
    )
    return (
        '<div class="tools"><input id="q" placeholder="Search lead name…">'
        '<select id="fo"><option value="">All outcomes</option><option>won</option>'
        "<option>lost</option></select>"
        '<select id="fr"><option value="">Right and wrong</option>'
        '<option value="right">Model right</option><option value="wrong">Model wrong</option>'
        "</select>"
        '<select id="fs"><option value="">Train and test</option><option>test</option>'
        "<option>train</option></select>"
        '<span id="count" class="note"></span></div>'
        f'<div class="scroll"><table id="leads"><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div><script>{TABLE_SCRIPT}</script>"
    )


def build(url: str, train_share: float, seed: int, cdn: bool = False) -> str:
    test_database.require_test_database(url)
    rows = load_leads(url)
    matrix = np.array(
        [
            [np.nan if r["features"][n] is None else float(r["features"][n]) for n in NAMES]
            for r in rows
        ]
    )
    labels = np.array([1 if r["outcome"] == "won" else 0 for r in rows])

    train_idx, test_idx = train_test_split(
        np.arange(len(rows)), train_size=train_share, random_state=seed, stratify=labels
    )
    train_x, test_x = matrix[train_idx], matrix[test_idx]
    train_y, test_y = labels[train_idx], labels[test_idx]

    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(max_iter=1000),
    )
    folds = cross_val_score(model, train_x, train_y, cv=5, scoring="roc_auc")
    model.fit(train_x, train_y)
    prob = model.predict_proba(test_x)[:, 1]

    # Every lead gets a chance from a model that never saw it: 5-fold out-of-fold predictions.
    chance = cross_val_predict(
        model,
        matrix,
        labels,
        cv=StratifiedKFold(5, shuffle=True, random_state=seed),
        method="predict_proba",
    )[:, 1]
    test_mask = np.isin(np.arange(len(rows)), test_idx)

    results = metrics(test_y, prob)
    metric_rows = "".join(f"<tr><td>{k}</td><td>{v:.3f}</td></tr>" for k, v in results.items())
    table = f"<table><tr><th>Test set</th><th>Logistic regression</th></tr>{metric_rows}</table>"

    roc = go.Figure()
    fpr, tpr, _ = roc_curve(test_y, prob)
    roc.add_scatter(x=fpr, y=tpr, name=f"Logistic regression (AUC {results['ROC AUC']:.2f})")
    roc.add_scatter(x=[0, 1], y=[0, 1], name="Chance", line={"dash": "dot", "color": "gray"})
    roc.update_layout(
        title="ROC curve", xaxis_title="False positive rate", yaxis_title="True positive rate"
    )

    cal = go.Figure()
    actual, predicted = calibration_curve(test_y, prob, n_bins=6, strategy="quantile")
    cal.add_scatter(x=predicted, y=actual, mode="lines+markers", name="Logistic regression")
    cal.add_scatter(x=[0, 1], y=[0, 1], name="Perfect", line={"dash": "dot", "color": "gray"})
    cal.update_layout(
        title="Calibration: does a 60% score win ~60% of the time?",
        xaxis_title="Predicted probability",
        yaxis_title="Share that actually won",
    )

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
    charts = "".join(chart(f) for f in (roc, cal, coef, conf))
    leads_html = leads_table(rows, labels, chance, test_mask)
    plotly_tag = (
        f'<script src="https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"></script>'
        if cdn
        else f"<script>{get_plotlyjs()}</script>"
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lead purchase model</title>
<style>{STYLE}</style>{plotly_tag}
<main><h1>Lead purchase model</h1>
<p class="note">The outcomes are synthetic, generated by a hidden formula plus noise, so this shows
the pipeline works, not how real customers behave. The model is not used by the app yet.</p>
<div class="kpis">{kpi_html}</div>
<h2>Model results (test set)</h2>{table}
<h2>Charts</h2><div class="grid">{charts}</div>
<h2>Every lead: chance to buy vs. what happened</h2>
<p class="note">"Model chance to buy" is out-of-fold: each lead is scored by a model trained on
the other four folds, so the model never saw that lead. "Set" marks the {1 - train_share:.0%}
hold-out used for the metrics above. Click a column to sort. "Model at 50%" says whether the
model's call at a 50% threshold matched the real outcome.</p>{leads_html}</main></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the lead model report as HTML.")
    parser.add_argument("--out", default="lead_report.html")
    parser.add_argument("--database-url")
    parser.add_argument("--train-share", type=float, default=0.88)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--cdn",
        action="store_true",
        help="load plotly.js from its CDN: a small file, needs internet",
    )
    args = parser.parse_args()
    html_text = build(args.database_url or default_url(), args.train_share, args.seed, args.cdn)
    Path(args.out).write_text(html_text, encoding="utf-8")
    print(f"Wrote {Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
