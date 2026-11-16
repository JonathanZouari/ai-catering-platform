"""Train the lead purchase model and write app/services/lead_model.json.

Run from backend/:
    uv run python -m scripts.train_lead_model

Shortcut: this trains on the synthetic leads from scripts/sample_leads.py, the same rows as
the database seed. Once real leads have outcomes, read the closed leads (won / lost) from
the database here instead; nothing else needs to change.
"""

import json

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from app.services.lead_scoring import MODEL_FILE, features
from scripts.sample_leads import generate

CLOSED_STATUSES = ("won", "lost")


def train(leads: list[dict]) -> dict:
    """Fit a logistic regression on the closed leads.

    Returns the model in the shape lead_scoring reads: an intercept and one coefficient per
    feature, both on the raw feature scale, plus metrics from a 25% holdout.
    """
    closed = [lead for lead in leads if lead["status"] in CLOSED_STATUSES]
    rows = [features(lead) for lead in closed]
    names = sorted({name for row in rows for name in row})
    x = [[row.get(name, 0.0) for name in names] for row in rows]
    y = [1 if lead["status"] == "won" else 0 for lead in closed]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, random_state=0, stratify=y
    )
    holdout = _fit(x_train, y_train)
    predicted = holdout["model"].predict_proba(holdout["scaler"].transform(x_test))[:, 1]

    # The shipped coefficients use every closed lead; the holdout fit is only for the metrics.
    final = _fit(x, y)
    # Folding the scaler into the coefficients lets the server score raw values.
    scaled = final["model"].coef_[0] / final["scaler"].scale_
    intercept = final["model"].intercept_[0] - float(scaled @ final["scaler"].mean_)
    return {
        "trained_on": "synthetic leads (scripts/sample_leads.py)",
        "training_rows": len(closed),
        "holdout_rows": len(y_test),
        "holdout_auc": round(float(roc_auc_score(y_test, predicted)), 3),
        "holdout_brier": round(float(brier_score_loss(y_test, predicted)), 3),
        "intercept": round(float(intercept), 6),
        "coefficients": {
            name: round(float(value), 6) for name, value in zip(names, scaled, strict=True)
        },
    }


def _fit(x: list[list[float]], y: list[int]) -> dict:
    scaler = StandardScaler().fit(x)
    model = LogisticRegression().fit(scaler.transform(x), y)
    return {"scaler": scaler, "model": model}


if __name__ == "__main__":
    model = train(generate())
    MODEL_FILE.write_text(
        json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        f"Wrote {MODEL_FILE.name}: {model['training_rows']} rows, "
        f"holdout AUC {model['holdout_auc']}, Brier {model['holdout_brier']}"
    )
