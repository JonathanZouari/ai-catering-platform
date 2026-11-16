"""Streamlit dashboard: lead scoring, data preprocessing, linear and logistic models.

Run from the repo root:  streamlit run dashboard/app.py
"""

import sys
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    accuracy_score,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend" / "scripts")]

import train_linear_model as linear  # noqa: E402
import train_logistic_models as logistic  # noqa: E402
from app.services.lead_scoring import LeadService  # noqa: E402

DATA = ROOT / "data" / "combined_clients_orders.csv"
TIERS = {"hot": "חם", "warm": "בינוני", "cold": "קר"}

st.set_page_config(page_title="יאמי: לידים וחיזוי", page_icon="🍽️", layout="wide")
st.markdown(
    "<style>.stApp, .stMarkdown, .stDataFrame {direction: rtl; text-align: right;}</style>",
    unsafe_allow_html=True,
)
st.title("🍽️ לידים וחיזוי לקוחות")

if not DATA.exists():
    st.error(f"קובץ הנתונים לא נמצא: {DATA}")
    st.stop()

with st.sidebar:
    st.header("הגדרות")
    test_size = st.slider("חלק ה-Test", 0.1, 0.4, 0.2, 0.05)
    seed = st.number_input("Random seed", 0, 9999, 42)
    has_synthetic = logistic.ENRICHED_SOURCE.exists()
    use_synthetic = st.toggle(
        "משתני ליד פקטיביים (מקור, זמן תגובה, תקציב...)",
        value=has_synthetic,
        disabled=not has_synthetic,
        help="נתונים שהומצאו להדגמה. השיפור שהם מראים נכון מראש ואינו מעיד על לקוחות אמיתיים.",
    )


@st.cache_data
def lead_table(as_of: date) -> tuple[pd.DataFrame, dict]:
    service = LeadService.from_csv(DATA)
    leads = pd.DataFrame([vars(lead) for lead in service.leads(as_of)])
    return leads, service.forecast(as_of)


@st.cache_data
def logistic_results(test_size: float, seed: int, enriched: bool = False):
    data = logistic.preprocess(logistic.load(enriched), enriched)
    X, y = data.drop(columns=logistic.TARGET), data[logistic.TARGET]
    # stratify=y keeps the same ordered / not-ordered ratio in train and test
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y
    )
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    table, curves = [], []
    for name, model in logistic.MODELS.items():
        cv_auc = cross_val_score(model, X_tr, y_tr, cv=cv, scoring="roc_auc").mean()
        model.fit(X_tr, y_tr)
        scores = model.predict_proba(X_te)[:, 1]
        auc = roc_auc_score(y_te, scores)
        table.append(
            {
                "מודל": name,
                "CV AUC": round(cv_auc, 3),
                "Test AUC": round(auc, 3),
                "Accuracy": round(accuracy_score(y_te, model.predict(X_te)), 3),
            }
        )
        fpr, tpr, _ = roc_curve(y_te, scores)
        curves.append(pd.DataFrame({"FPR": fpr, "TPR": tpr, "מודל": f"{name} ({auc:.3f})"}))
    split = pd.DataFrame(
        {
            "קבוצה": ["Train", "Test"],
            "לקוחות": [len(y_tr), len(y_te)],
            "הזמינו": [int(y_tr.sum()), int(y_te.sum())],
            "לא הזמינו": [int((y_tr == 0).sum()), int((y_te == 0).sum())],
        }
    )
    split["% הזמינו"] = (split["הזמינו"] / split["לקוחות"] * 100).round(1)
    default = logistic.MODELS["2. L2, C=1 (default)"]
    coefs = (
        pd.Series(default.coef_[0], index=X.columns, name="מקדם")
        .sort_values(key=abs, ascending=False)
        .head(12)
        .rename_axis("משתנה")
        .reset_index()
    )
    return pd.DataFrame(table), pd.concat(curves), split, len(data), coefs


@st.cache_data
def linear_results(test_size: float, seed: int):
    raw = linear.load(DATA)
    data = linear.preprocess(raw.copy())
    X, y = data.drop(columns=linear.TARGET), data[linear.TARGET]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=test_size, random_state=seed)
    model = LinearRegression().fit(X_tr, y_tr)
    pred = model.predict(X_te)
    coefs = pd.Series(model.coef_, index=X.columns).sort_values(key=abs, ascending=False)
    return {
        "rows_before": len(raw),
        "rows_after": len(data),
        "r2_train": r2_score(y_tr, model.predict(X_tr)),
        "r2_test": r2_score(y_te, pred),
        "mae_test": mean_absolute_error(y_te, pred),
        "coefs": coefs.head(10).rename_axis("משתנה").reset_index(name="מקדם"),
        "scatter": pd.DataFrame({"בפועל": y_te.values, "חיזוי": pred}),
        "preview": data.head(10),
    }


tab_leads, tab_prep, tab_linear, tab_logistic = st.tabs(
    ["לידים וחיזוי הכנסות", "עיבוד נתונים", "רגרסיה לינארית", "רגרסיה לוגיסטית ו-ROC"]
)

with tab_leads:
    leads, forecast = lead_table(date.today())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("לידים פתוחים", forecast["total_leads"])
    c2.metric("לידים חמים", forecast["tiers"]["hot"]["count"])
    c3.metric("הזמנות צפויות", forecast["expected_conversions"])
    c4.metric("הכנסה צפויה", f"₪{forecast['expected_revenue']:,.0f}")
    st.subheader("הכנסה צפויה לפי חודש האירוע")
    st.bar_chart(pd.DataFrame(forecast["by_event_month"]), x="month", y="expected_revenue")
    st.subheader("רשימת לידים")
    chosen = st.multiselect("דרגה", list(TIERS), default=["hot", "warm"], format_func=TIERS.get)
    view = leads[leads["tier"].isin(chosen)].copy()
    view["סיכוי"] = (view["probability"] * 100).round(0).astype(int)
    view["דרגה"] = view["tier"].map(TIERS)
    view["סיבות"] = view["reasons"].map(" | ".join)
    st.dataframe(
        view[
            ["full_name", "city", "דרגה", "סיכוי", "order_status", "event_date",
             "quote_total", "expected_revenue", "action", "סיבות"]
        ].rename(
            columns={
                "full_name": "לקוח",
                "city": "עיר",
                "order_status": "סטטוס",
                "event_date": "תאריך אירוע",
                "quote_total": "הצעה",
                "expected_revenue": "הכנסה צפויה",
                "action": "פעולה מומלצת",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

with tab_prep:
    lin = linear_results(test_size, seed)
    st.subheader("סדר העיבוד")
    st.markdown(
        "1. **ערכים חסרים**: `SimpleImputer(mean)` על עמודות מספריות.\n"
        "2. **נרמול**: `MinMaxScaler`, כל הערכים בין 0 ל-1.\n"
        "3. **קידוד קטגוריות**: `OneHotEncoder`.\n"
        "4. **ערכים חריגים**: כלל ה-IQR (1.5 × IQR).\n"
        "5. **פיצול**: Train / Test.\n"
        "6. **אימון**: `LinearRegression`."
    )
    a, b = st.columns(2)
    a.metric("שורות לפני הסרת חריגים", lin["rows_before"])
    b.metric("שורות אחרי הסרת חריגים", lin["rows_after"])
    st.caption("דוגמה מהנתונים לאחר העיבוד")
    st.dataframe(lin["preview"], use_container_width=True)

with tab_linear:
    lin = linear_results(test_size, seed)
    st.subheader("חיזוי סכום ההזמנה (total)")
    a, b, c = st.columns(3)
    a.metric("R² אימון", f"{lin['r2_train']:.3f}")
    b.metric("R² בדיקה", f"{lin['r2_test']:.3f}")
    c.metric("MAE בדיקה (סקאלה 0-1)", f"{lin['mae_test']:.4f}")
    perfect = pd.DataFrame({"x": [0, 1], "y": [0, 1]})
    st.altair_chart(
        alt.Chart(lin["scatter"]).mark_circle(opacity=0.5).encode(x="בפועל", y="חיזוי")
        + alt.Chart(perfect).mark_line(color="red").encode(x="x", y="y"),
        use_container_width=True,
    )
    st.caption("הקו האדום הוא חיזוי מושלם. המשתנה החזק ביותר הוא מספר המבוגרים באירוע.")
    st.dataframe(lin["coefs"], hide_index=True)

with tab_logistic:
    st.subheader("חיזוי האם לקוח הזמין (has_ordered)")
    table, curves, split, n, coefs = logistic_results(test_size, seed, use_synthetic)
    if use_synthetic:
        base_table = logistic_results(test_size, seed, False)[0]
        st.warning(
            "הנתונים בלשונית זו כוללים עמודות **פקטיביות** (מקור הליד, זמן תגובה, תקציב, "
            "אינטראקציות ועוד) שנוצרו כדי להדגים איך מידע עשיר משפר את המודל. השיפור נכון "
            "מראש ואינו מעיד על ביצועים על לקוחות אמיתיים."
        )
        a, b, c = st.columns(3)
        a.metric("AUC לפני (משתנים מקוריים)", f"{base_table['Test AUC'].max():.3f}")
        b.metric(
            "AUC אחרי (עם משתנים פקטיביים)",
            f"{table['Test AUC'].max():.3f}",
            delta=f"{table['Test AUC'].max() - base_table['Test AUC'].max():+.3f}",
        )
        c.metric("לקוחות לאחר הסרת חריגים", n)
    st.markdown(
        f"הנתונים כוללים **{n} לקוחות**, גם כאלה שהזמינו וגם כאלה שלא. הפיצול מתבצע עם "
        "`stratify`, כך ששתי הקבוצות שומרות על אותו יחס בין מי שהזמין למי שלא."
    )
    st.dataframe(split, hide_index=True)
    st.subheader("השוואת מודלים")
    st.dataframe(table, hide_index=True, use_container_width=True)
    roc = alt.Chart(curves).mark_line().encode(x="FPR", y="TPR", color="מודל")
    diagonal = (
        alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]}))
        .mark_line(color="gray", strokeDash=[5, 5])
        .encode(x="x", y="y")
    )
    st.altair_chart((roc + diagonal).properties(height=420), use_container_width=True)
    st.subheader("על מה הניבוי מתבסס (מקדמי מודל 2)")
    st.caption("מקדם חיובי מעלה את הסיכוי להזמין, שלילי מוריד. המשתנים המספריים מנורמלים 0-1.")
    st.altair_chart(
        alt.Chart(coefs)
        .mark_bar()
        .encode(
            x="מקדם",
            y=alt.Y("משתנה", sort="-x"),
            color=alt.condition(alt.datum["מקדם"] > 0, alt.value("#2f6b1f"), alt.value("#b3402a")),
        ),
        use_container_width=True,
    )
    best = table["Test AUC"].max()
    if best < 0.6:
        st.warning(
            f"AUC הטוב ביותר הוא {best:.3f}, קרוב ל-0.5 (ניחוש אקראי). המשתנים שידועים לפני "
            "הזמנה (עיר, קיום אימייל, תאריך הרשמה) לא מנבאים אם הלקוח יזמין. הדיוק הגבוה "
            "(כ-87%) מגיע רק מכך שרוב הלקוחות הזמינו, ולא מיכולת הניבוי של המודל."
        )
    st.markdown(
        """
**איך לקרוא את התוצאות**
- **ROC**: לכל סף החלטה, כמה מהמזמינים זוהו (TPR) לעומת כמה מהלא-מזמינים סווגו בטעות (FPR). עקומה הרחוקה מהאלכסון היא מודל טוב.
- **AUC**: השטח מתחת לעקומה. 0.5 הוא ניחוש אקראי, 1.0 הוא מושלם.
- **CV AUC**: ממוצע על 5 חלוקות של ה-Train. הוא בודק שהתוצאה יציבה ולא תלויה בפיצול אחד.
- **Accuracy**: אחוז הניבויים הנכונים. כאן הוא מטעה בגלל חוסר איזון (87% הזמינו).
- **מודלים**: ללא רגולריזציה; L2 רגיל; L2 חזק (C קטן, מקדמים קטנים יותר); L1 (מאפס משתנים לא חשובים); L2 עם `class_weight=balanced` (נותן משקל גבוה יותר למי שלא הזמין, ולכן הדיוק יורד).
"""
    )
