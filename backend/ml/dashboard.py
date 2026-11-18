"""Streamlit dashboard: lead list and a full model comparison.

Run from backend/:  uv run --extra ml streamlit run ml/dashboard.py
Data is synthetic (ml/synthetic.py), so the numbers validate the pipeline, not real conversion.
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # streamlit puts ml/ on the path, not backend/

from ml.compare_models import CATEGORICAL, NUMERIC, build_models, matrix  # noqa: E402
from ml.synthetic import generate  # noqa: E402

FEATURES = CATEGORICAL + NUMERIC
HE = {
    "logreg": "רגרסיה לוגיסטית",
    "random_forest": "יער אקראי",
    "hist_gb": "Gradient Boosting",
    "base_rate": "ללא מודל",
}
# Fixed categorical slots (validated light palette): the colour follows the model, never its rank.
COLOR = {
    "רגרסיה לוגיסטית": "#2a78d6",
    "יער אקראי": "#eb6834",
    "Gradient Boosting": "#1baf7a",
    "ללא מודל": "#8a8983",
}
DASH = {  # secondary encoding, so identity never rests on colour alone
    "רגרסיה לוגיסטית": [1, 0],
    "יער אקראי": [6, 3],
    "Gradient Boosting": [2, 2],
    "ללא מודל": [4, 4],
}
MODEL_SCALE = alt.Scale(domain=list(COLOR)[:3], range=list(COLOR.values())[:3])
STAGES = {"new": "חדש", "contacted": "נוצר קשר", "quoted": "נשלחה הצעה", "negotiating": "במשא ומתן"}
SOURCES = {
    "website_form": "טופס באתר",
    "ai_chat": "צ׳אט",
    "whatsapp": "וואטסאפ",
    "phone": "טלפון",
    "referral": "המלצה",
    "instagram": "אינסטגרם",
    "google": "גוגל",
}
FEATURE_HE = {
    "source": "מקור",
    "event_type": "סוג אירוע",
    "guests": "אורחים",
    "days_until_event": "ימים עד האירוע",
    "budget": "תקציב",
    "quote_amount": "סכום הצעה",
    "quote_budget_ratio": "יחס הצעה לתקציב",
    "repeat_customer": "לקוח חוזר",
    "has_email": "השאיר אימייל",
    "response_hours": "שעות לתגובה",
    "touches": "פניות",
    "viewed_menu": "צפה בתפריט",
    "weekend_event": "אירוע בסוף שבוע",
}

st.set_page_config(page_title="לידים ומודלים | yumm.ai", layout="wide")
st.markdown(
    """<style>
    .stApp, [data-testid="stSidebar"] { direction: rtl; text-align: right; }
    [data-testid="stMetricValue"], .stDataFrame, .vega-embed { direction: ltr; }
    </style>""",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="מאמן מודלים...")
def run(n: int, seed: int, test_size: float, threshold: float):
    rows = generate(n, seed)
    y = np.array([r["converted"] for r in rows])
    X = matrix(rows)
    idx = np.arange(n)
    tr, te = train_test_split(idx, test_size=test_size, stratify=y, random_state=0)
    base = float(y[tr].mean())
    out, curves, cal, gains, imp = {}, [], [], [], []
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    for key, model in build_models().items():
        name = HE[key]
        model.fit(X[tr], y[tr])
        p = model.predict_proba(X[te])[:, 1]
        yt = y[te]
        pred = (p >= threshold).astype(int)
        scores = cross_val_score(model, X[tr], y[tr], cv=cv, scoring="roc_auc")
        order = np.argsort(-p)
        k = max(1, len(yt) // 10)
        out[name] = {
            "ROC-AUC": roc_auc_score(yt, p),
            "PR-AUC": average_precision_score(yt, p),
            "Brier": brier_score_loss(yt, p),
            "Log-loss": log_loss(yt, p),
            "Accuracy": accuracy_score(yt, pred),
            "Precision": precision_score(yt, pred, zero_division=0),
            "Recall": recall_score(yt, pred),
            "F1": f1_score(yt, pred),
            "Lift@10%": yt[order[:k]].mean() / yt.mean(),
            "CV ROC-AUC (ממוצע)": scores.mean(),
            "CV ROC-AUC (סטיית תקן)": scores.std(),
            "_cm": [[int(((pred == a) & (yt == b)).sum()) for a in (0, 1)] for b in (0, 1)],
        }
        fpr, tpr, _ = roc_curve(yt, p)
        curves += [
            {"מודל": name, "עקומה": "ROC", "x": a, "y": b} for a, b in zip(fpr, tpr, strict=True)
        ]
        pr, rc, _ = precision_recall_curve(yt, p)
        curves += [
            {"מודל": name, "עקומה": "PR", "x": a, "y": b} for a, b in zip(rc, pr, strict=True)
        ]
        o, pp = calibration_curve(yt, p, n_bins=8, strategy="quantile")
        cal += [{"מודל": name, "חזוי": a, "בפועל": b} for a, b in zip(pp, o, strict=True)]
        cum = np.cumsum(yt[order]) / yt.sum()
        gains += [
            {"מודל": name, "אחוז לידים מהגבוה לנמוך": (i + 1) / len(yt), "אחוז סגירות שנתפסו": c}
            for i, c in enumerate(cum)
        ]
        r = permutation_importance(model, X[te], yt, scoring="roc_auc", n_repeats=5, random_state=0)
        imp += [
            {"מודל": name, "גורם": FEATURE_HE[f], "חשיבות": v}
            for f, v in zip(FEATURE_HE, r.importances_mean, strict=True)
        ]
    out[HE["base_rate"]] = {
        "ROC-AUC": 0.5,
        "PR-AUC": float(y[te].mean()),
        "Brier": brier_score_loss(y[te], np.full(len(te), base)),
        "Log-loss": log_loss(y[te], np.full(len(te), base)),
    }
    # Scored lead list from the best model (by held-out ROC-AUC), for the worklist tab.
    best_key = max(build_models(), key=lambda k: out[HE[k]]["ROC-AUC"])
    best = build_models()[best_key].fit(X[tr], y[tr])
    sample = [rows[i] for i in te[:80]]
    probs = best.predict_proba(matrix(sample))[:, 1]
    leads = pd.DataFrame(sample)
    leads["סיכוי"] = probs
    return (
        out,
        pd.DataFrame(curves),
        pd.DataFrame(cal),
        pd.DataFrame(gains),
        pd.DataFrame(imp),
        leads,
        HE[best_key],
        len(tr),
        len(te),
        float(y.mean()),
    )


def line(df, x, y, title, xt, yt, diagonal=False):
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:Q", scale=alt.Scale(domain=[0, 1]), title=xt),
        y=alt.Y(f"{y}:Q", scale=alt.Scale(domain=[0, 1]), title=yt),
        color=alt.Color(
            "מודל:N",
            scale=MODEL_SCALE,
            legend=alt.Legend(orient="bottom"),
        ),
        strokeDash=alt.StrokeDash(
            "מודל:N",
            scale=alt.Scale(domain=list(DASH)[:3], range=list(DASH.values())[:3]),
            legend=None,
        ),
        tooltip=["מודל", alt.Tooltip(f"{x}:Q", format=".2f"), alt.Tooltip(f"{y}:Q", format=".2f")],
    )
    layers = [
        base.mark_line(
            strokeWidth=2, interpolate="step-after" if title.startswith("PR") else "linear"
        )
    ]
    if diagonal:
        layers.append(
            alt.Chart(pd.DataFrame({"a": [0, 1], "b": [0, 1]}))
            .mark_line(color="#8a8983", strokeDash=[4, 4])
            .encode(x="a:Q", y="b:Q")
        )
    return alt.layer(*layers).properties(title=title, height=300)


st.title("לידים ומודלים: סיכוי להזמנה")
st.caption("נתונים סינתטיים. המדדים מוכיחים שהצנרת עובדת, לא כמה המודל מדויק על לקוחות אמיתיים.")

with st.sidebar:
    st.header("הגדרות")
    n = st.slider("מספר לידים בנתונים", 500, 10000, 3000, 500)
    seed = st.number_input("זרע (seed)", 0, 9999, 7)
    test_size = st.slider("חלק מערכת הבדיקה", 0.1, 0.5, 0.3, 0.05)
    threshold = st.slider("סף החלטה (לדיוק, Recall, F1 ומטריצת בלבול)", 0.1, 0.9, 0.5, 0.05)

(metrics, curves, cal, gains, imp, leads, best, n_tr, n_te, rate) = run(
    n, int(seed), test_size, threshold
)
st.write(
    f"אימון על **{n_tr}** לידים, בדיקה על **{n_te}**. שיעור הסגירה בנתונים: **{rate:.1%}**. "
    f"המודל הטוב ביותר לפי ROC-AUC: **{best}**."
)

tab_models, tab_curves, tab_factors, tab_leads = st.tabs(
    ["השוואת מדדים", "עקומות", "גורמים משפיעים", "רשימת לידים"]
)

with tab_models:
    df = pd.DataFrame(metrics).T.drop(columns="_cm", errors="ignore").astype(float)
    st.subheader("כל המדדים")
    st.dataframe(
        df.style.format("{:.3f}", na_rep="").highlight_max(
            axis=0,
            subset=[
                c for c in df.columns if c not in ("Brier", "Log-loss", "CV ROC-AUC (סטיית תקן)")
            ],
            color="#cde2fb",
        ),
        width="stretch",
    )
    st.caption(
        "מודגש: הטוב ביותר בכל עמודה (למעט Brier, Log-loss וסטיית תקן, שבהם נמוך יותר טוב). "
        "Accuracy, Precision, Recall ו-F1 תלויים בסף ההחלטה בסרגל הצד."
    )
    st.subheader("מטריצות בלבול (בסף שנבחר)")
    cols = st.columns(3)
    for col, key in zip(cols, ("logreg", "random_forest", "hist_gb"), strict=True):
        cm = metrics[HE[key]]["_cm"]
        col.markdown(f"**{HE[key]}**")
        col.dataframe(
            pd.DataFrame(
                cm, index=["לא נסגר בפועל", "נסגר בפועל"], columns=["חזוי: לא", "חזוי: כן"]
            )
        )

with tab_curves:
    a, b = st.columns(2)
    a.altair_chart(
        line(
            curves[curves["עקומה"] == "ROC"],
            "x",
            "y",
            "ROC",
            "שיעור חיובי שגוי",
            "שיעור חיובי אמיתי",
            diagonal=True,
        ),
        width="stretch",
    )
    b.altair_chart(
        line(
            curves[curves["עקומה"] == "PR"], "x", "y", "PR (דיוק מול Recall)", "Recall", "Precision"
        ),
        width="stretch",
    )
    c, d = st.columns(2)
    c.altair_chart(
        line(
            cal.rename(columns={"חזוי": "x", "בפועל": "y"}),
            "x",
            "y",
            "כיול: חזוי מול בפועל",
            "סיכוי חזוי",
            "שיעור סגירה בפועל",
            diagonal=True,
        ),
        width="stretch",
    )
    g = gains.rename(columns={"אחוז לידים מהגבוה לנמוך": "x", "אחוז סגירות שנתפסו": "y"})
    d.altair_chart(
        line(
            g,
            "x",
            "y",
            "Gains: סגירות שנתפסו לפי דירוג",
            "אחוז הלידים (מהגבוה לנמוך)",
            "אחוז הסגירות שנתפסו",
            diagonal=True,
        ),
        width="stretch",
    )
    st.caption(
        "הקו המקווקו האפור הוא ניחוש אקראי. לכיול טוב העקומה קרובה לאלכסון. "
        "בטבלת המדדים ובטבלאות הנתונים אפשר לקרוא את הערכים המדויקים."
    )
    with st.expander("טבלת נתוני הכיול"):
        st.dataframe(cal, width="stretch")

with tab_factors:
    st.subheader("חשיבות גורמים (Permutation importance, ירידה ב-ROC-AUC)")
    chart = (
        alt.Chart(imp)
        .mark_bar()
        .encode(
            y=alt.Y("גורם:N", sort="-x", title=None),
            x=alt.X("חשיבות:Q"),
            color=alt.Color("מודל:N", scale=MODEL_SCALE),
            yOffset="מודל:N",
            tooltip=["מודל", "גורם", alt.Tooltip("חשיבות:Q", format=".3f")],
        )
        .properties(height=420)
    )
    st.altair_chart(chart, width="stretch")
    st.caption("ככל שהערך גבוה יותר, ערבוב הגורם פוגע יותר ביכולת המודל להבדיל בין לידים.")

with tab_leads:
    st.subheader(f"לידים לדוגמה מדורגים לפי {best}")
    leads = leads.assign(סיכוי=leads["סיכוי"] * 100)
    show = leads.assign(
        מקור=leads["source"].map(SOURCES),
        אירוע=leads["event_type"],
        דירוג=pd.cut(leads["סיכוי"], [0, 30, 55, 100], labels=["נמוך", "בינוני", "גבוה"]),
    )
    band = st.multiselect("דירוג", ["גבוה", "בינוני", "נמוך"], default=["גבוה", "בינוני"])
    show = show[show["דירוג"].isin(band)].sort_values("סיכוי", ascending=False)
    st.dataframe(
        show[
            [
                "lead_id",
                "אירוע",
                "מקור",
                "guests",
                "budget",
                "quote_amount",
                "touches",
                "דירוג",
                "סיכוי",
            ]
        ].rename(
            columns={
                "lead_id": "ליד",
                "guests": "אורחים",
                "budget": "תקציב",
                "quote_amount": "הצעה",
                "touches": "פניות",
            }
        ),
        width="stretch",
        hide_index=True,
        column_config={
            "סיכוי": st.column_config.ProgressColumn(
                "סיכוי", min_value=0, max_value=100, format="%.0f%%"
            )
        },
    )
    st.caption("הדירוג הוא המלצה בלבד ואינו משנה הצעה, מחיר או הזמנה.")
