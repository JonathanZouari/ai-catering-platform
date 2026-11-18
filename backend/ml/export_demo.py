"""Export scored synthetic leads as JSON for the admin demo screen.

Trains the logistic regression on synthetic data, scores a sample and adds the top factors
behind each score. Demo data only: names are placeholders, nothing is real.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ml.compare_models import CATEGORICAL, NUMERIC, build_models, evaluate, matrix
from ml.synthetic import generate

OPEN_STAGES = ["new", "contacted", "quoted", "negotiating"]
FACTOR_LABELS = {
    "source": "מקור",
    "event_type": "סוג אירוע",
    "guests": "מספר אורחים",
    "days_until_event": "זמן עד האירוע",
    "budget": "תקציב",
    "quote_amount": "סכום ההצעה",
    "quote_budget_ratio": "יחס הצעה לתקציב",
    "repeat_customer": "לקוח חוזר",
    "has_email": "השאיר אימייל",
    "response_hours": "זמן תגובה",
    "touches": "מספר פניות",
    "viewed_menu": "צפה בתפריט",
    "weekend_event": "אירוע בסוף שבוע",
}


def band(p: float) -> str:
    return "high" if p >= 0.55 else "medium" if p >= 0.3 else "low"


def export(n_train: int, n_show: int, seed: int) -> list[dict]:
    rows = generate(n_train + n_show, seed)
    train, show = rows[:n_train], rows[n_train:]
    X_tr = matrix(train)
    y_tr = np.array([r["converted"] for r in train])
    model = build_models()["logreg"]
    model.fit(X_tr, y_tr)
    pre, clf = model[0], model[-1]
    names = pre.get_feature_names_out()
    Xs = pre.transform(matrix(show))
    contrib = Xs * clf.coef_[0]
    proba = model.predict_proba(matrix(show))[:, 1]

    rng = np.random.default_rng(seed)
    out = []
    for i, r in enumerate(show):
        is_open = i < n_show * 0.4
        if is_open:
            t = r["touches"]
            stage = OPEN_STAGES[0 if t <= 1 else 1 if t <= 3 else 2 + int(rng.random() < 0.35)]
        else:
            stage = "won" if r["converted"] else "lost"
        order = np.argsort(-np.abs(contrib[i]))
        factors, seen = [], set()
        for j in order:
            idx = int(str(names[j]).split("__x", 1)[1].split("_")[0])
            key = (CATEGORICAL + NUMERIC)[idx]
            if key in seen:
                continue
            seen.add(key)
            factors.append(
                {
                    "label": FACTOR_LABELS.get(key, key),
                    "effect": "up" if contrib[i, j] > 0 else "down",
                }
            )
            if len(factors) == 3:
                break
        out.append(
            {
                "id": r["lead_id"],
                "name": f"ליד לדוגמה {i + 1:02d}",
                "source": r["source"],
                "event_type": r["event_type"],
                "guests": r["guests"],
                "days_until_event": r["days_until_event"],
                "budget": r["budget"],
                "quote_amount": r["quote_amount"],
                "touches": r["touches"],
                "response_hours": r["response_hours"],
                "stage": stage,
                "score": round(float(proba[i]), 3),
                "band": band(float(proba[i])),
                "factors": factors,
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("../frontend/admin/leads/demo-leads.json"))
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    leads = export(3000, 60, a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(leads, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = generate(3000, 7)
    y = np.array([r["converted"] for r in rows])
    models_out = a.out.with_name("demo-models.json")
    models_out.write_text(
        json.dumps(evaluate(rows, y, 0), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"wrote {len(leads)} leads to {a.out} and model metrics to {models_out}")


if __name__ == "__main__":
    main()
