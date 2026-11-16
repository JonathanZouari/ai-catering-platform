"""Build a self-contained HTML dashboard (lead distribution + model evaluation).

Run after seed_leads.py and train_lead_model.py. Output: backend/data/crm_dashboard.html
"""

import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from common import CATEGORICAL, DATA_DIR, MODEL_PATH, connect
from sklearn.metrics import roc_curve
from sklearn.model_selection import train_test_split
from train_lead_model import SEED, load

TEMPLATE = Path(__file__).with_name("dashboard_template.html")
OUT = DATA_DIR / "crm_dashboard.html"


def bin_counts(values, y, edges, labels):
    """Count buyers / non-buyers per half-open bin [edge_i, edge_i+1)."""
    idx = np.digitize(values, edges[1:-1])
    out = []
    for i, label in enumerate(labels):
        mask = idx == i
        out.append({"label": label, "buyers": int(y[mask].sum()), "non": int((1 - y[mask]).sum())})
    return out


def categorical(col_values, y):
    counts = Counter()
    buyers = Counter()
    for v, b in zip(col_values, y, strict=True):
        counts[v] += 1
        buyers[v] += int(b)
    keys = sorted(counts, key=lambda k: -counts[k])
    return [{"label": k, "buyers": buyers[k], "non": counts[k] - buyers[k]} for k in keys]


def main() -> None:
    X, y = load()
    y = y.astype(int)
    cols_num = X[:, :9].astype(float)
    days, guests, dishes, quote = cols_num[:, 0], cols_num[:, 1], cols_num[:, 2], cols_num[:, 3]
    source, event_type = X[:, 9], X[:, 10]

    distribution = {
        "source": categorical(source, y),
        "event_type": categorical(event_type, y),
        "days_until_event": bin_counts(
            days,
            y,
            [0, 15, 31, 46, 61, 91, 121, 1e9],
            ["0-14", "15-30", "31-45", "46-60", "61-90", "91-120", "121+"],
        ),
        "guest_count": bin_counts(
            guests,
            y,
            [0, 25, 50, 100, 150, 250, 1e9],
            ["<25", "25-49", "50-99", "100-149", "150-249", "250+"],
        ),
        "dishes_selected": bin_counts(
            dishes, y, [0, 1, 3, 5, 8, 1e9], ["0", "1-2", "3-4", "5-7", "8+"]
        ),
        "quote_submitted": categorical(["yes" if q else "no" for q in quote], y),
    }

    # Recreate the exact 80/20 split used for training (same seed + stratify).
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
    # Safe: MODEL_PATH is the file our own train_lead_model.py wrote (gitignored, never downloaded).
    model = joblib.load(MODEL_PATH)
    proba = model.predict_proba(X_test)[:, 1]
    report = json.loads((DATA_DIR / "lead_model_report.json").read_text())

    fpr, tpr, _ = roc_curve(y_test, proba)
    keep = np.unique(np.linspace(0, len(fpr) - 1, 60).astype(int))
    roc = [[round(float(fpr[i]), 4), round(float(tpr[i]), 4)] for i in keep]

    edges = np.linspace(0, 1, 11)
    # Short labels (bin start) so the 10 columns don't collide on the axis.
    score_hist = bin_counts(proba, y_test, edges, [f"{a:.1f}" for a in edges[:-1]])

    order = np.argsort(proba)
    bands = []
    for i, chunk in enumerate(np.array_split(order, 5)):
        bands.append(
            {
                "label": f"Band {i + 1}"
                + (" (lowest)" if i == 0 else " (highest)" if i == 4 else ""),
                "avg_score": round(float(proba[chunk].mean()), 3),
                "actual_rate": round(float(y_test[chunk].mean()), 3),
                "n": int(len(chunk)),
            }
        )

    data = {
        "total": int(len(y)),
        "buyers": int(y.sum()),
        "distribution": distribution,
        "report": report,
        "roc": roc,
        "score_hist": score_hist,
        "bands": bands,
        "categorical_features": CATEGORICAL,
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/null", json.dumps(data))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    # Fail early if the data / model are missing.
    with connect() as conn:
        conn.execute("select 1 from leads limit 1")
    main()
