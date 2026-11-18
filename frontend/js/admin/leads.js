// Owner lead list. Scores are advisory: they sort the worklist and never change an order.
// ?demo loads synthetic leads from demo-leads.json so the screen works without Supabase.
import { announce } from "../lib/announce.js";
import { fill, h } from "../lib/dom.js";
import { fmtMoney } from "../lib/format.js";

const root = document.getElementById("leads");
const demo = new URLSearchParams(location.search).has("demo");

const STAGES = {
  new: "חדש",
  contacted: "נוצר קשר",
  quoted: "נשלחה הצעה",
  negotiating: "במשא ומתן",
  won: "נסגר",
  lost: "אבד",
};
const OPEN = new Set(["new", "contacted", "quoted", "negotiating"]);
const BANDS = { high: "גבוה", medium: "בינוני", low: "נמוך" };
const BAND_ORDER = { high: 0, medium: 1, low: 2 };
const SOURCES = {
  website_form: "טופס באתר", ai_chat: "צ׳אט", whatsapp: "וואטסאפ", phone: "טלפון",
  referral: "המלצה", instagram: "אינסטגרם", google: "גוגל",
};

const bandOf = (p) => (p >= 0.55 ? "high" : p >= 0.3 ? "medium" : "low");

async function loadDemo() {
  const res = await fetch("/admin/leads/demo-leads.json");
  if (!res.ok) throw new Error("demo data missing");
  return res.json();
}

// Supabase is imported only here: its module needs /api/public-config, which demo mode must not require.
async function loadLive() {
  const { requireSession, isAdmin, sb } = await import("../lib/supabase.js");
  const session = await requireSession();
  if (!isAdmin(session)) return null;
  const { data, error } = await sb.from("leads")
    .select("id,full_name,source,stage,event_type,event_date,guests,budget,created_at,lead_scores(probability,scored_at)")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data.map((l) => {
    const latest = [...(l.lead_scores ?? [])].sort((a, b) => b.scored_at.localeCompare(a.scored_at))[0];
    const score = latest ? Number(latest.probability) : null;
    return {
      id: l.id, name: l.full_name, source: l.source, stage: l.stage, event_type: l.event_type ?? "",
      guests: l.guests, budget: l.budget, score, band: score == null ? null : bandOf(score), factors: [],
      days_until_event: l.event_date ? Math.round((new Date(l.event_date) - Date.now()) / 864e5) : null,
    };
  });
}

const MODEL_NAMES = {
  base_rate: "ללא מודל (שיעור הסגירה הכללי)",
  logreg: "רגרסיה לוגיסטית",
  random_forest: "יער אקראי",
  hist_gb: "Gradient Boosting",
};
const METRICS = [
  ["roc_auc", "ROC-AUC", "עד כמה המודל מבדיל בין ליד שיסגור לליד שלא (0.5 = ניחוש, 1 = מושלם)", 3],
  ["pr_auc", "PR-AUC", "דיוק בזיהוי הלידים שייסגרו, גבוה יותר טוב", 3],
  ["brier", "Brier", "שגיאת ההסתברות, נמוך יותר טוב", 3],
  ["lift_top10", "Lift ב-10% העליונים", "פי כמה סגירות יש ב-10% הלידים עם הציון הגבוה ביותר, לעומת הממוצע", 2],
];

async function loadModels() {
  if (!demo) return null;
  const res = await fetch("/admin/leads/demo-models.json");
  return res.ok ? res.json() : null;
}

function modelsSection(m) {
  if (!m) {
    return h("section", { class: "stack", "aria-labelledby": "models-title" },
      h("h2", { id: "models-title", text: "מדדי המודלים" }),
      h("p", { class: "muted", text: "מדדים יוצגו אחרי שיאומנו מודלים על לידים אמיתיים שנסגרו או אבדו." }));
  }
  const pct = (x) => `${Math.round(x * 100)}%`;
  const head = h("tr", {}, h("th", { scope: "col", text: "מודל" }),
    METRICS.map(([, label, hint]) => h("th", { scope: "col", title: hint, text: label })));
  const body = m.models.map((row) => h("tr", {},
    h("th", { scope: "row" }, MODEL_NAMES[row.name] ?? row.name,
      row.name === m.best ? h("span", { class: "badge badge-green", text: "הטוב ביותר" }) : null),
    METRICS.map(([key, , , digits]) => h("td", { class: "num", text: row[key].toFixed(digits) }))));
  return h("section", { class: "stack", "aria-labelledby": "models-title" },
    h("h2", { id: "models-title", text: "מדדי המודלים" }),
    h("p", { class: "muted small", text: `נבדק על ${m.n_test} לידים שהמודלים לא ראו באימון (אומנו על ${m.n_train}). שיעור הסגירה בנתונים: ${pct(m.positive_rate)}.` }),
    h("p", { class: "leads-demo", text: "המדדים מחושבים על נתונים סינתטיים שנוצרו מנוסחה לוגיסטית, ולכן הרגרסיה הלוגיסטית מנצחת מראש. הם מוכיחים שהצנרת עובדת ולא כמה המודל מדויק על לקוחות אמיתיים." }),
    h("table", { class: "leads-table" }, h("caption", { class: "muted small", text: "השוואת מודלים. מעבירים עכבר על כותרת מדד להסבר." }),
      h("thead", {}, head), h("tbody", {}, body)),
    h("h3", { text: `כיול המודל הטוב ביותר (${MODEL_NAMES[m.best]})` }),
    h("p", { class: "muted small", text: "אם המודל מכויל, מתוך הלידים שקיבלו סיכוי של 40% בערך 40% באמת נסגרו." }),
    h("table", { class: "leads-table" }, h("caption", { class: "visually-hidden", text: "טבלת כיול" }),
      h("thead", {}, h("tr", {}, h("th", { scope: "col", text: "סיכוי שחזה המודל" }), h("th", { scope: "col", text: "שיעור סגירה בפועל" }))),
      h("tbody", {}, m.calibration.map((c) => h("tr", {}, h("td", { class: "num", text: pct(c.predicted) }), h("td", { class: "num", text: pct(c.observed) }))))));
}

const dayLabel = (d) => (d == null ? "" : d <= 0 ? "היום או עבר" : `בעוד ${d} ימים`);

async function main() {
  const head = h("header", { class: "admin-head" },
    h("h1", { class: "auth-title", text: "לידים" }),
    h("a", { class: "btn btn-ghost", href: "/admin/" }, "חזרה לממשק העסק"));

  let leads;
  let models = null;
  try {
    leads = demo ? await loadDemo() : await loadLive();
    models = await loadModels().catch(() => null);
  } catch {
    return fill(root, head, h("p", { role: "alert", text: "לא הצלחנו לטעון את הלידים." }));
  }
  if (leads === null) return fill(root, head, h("p", { role: "alert", text: "לחשבון הזה אין הרשאת ניהול." }));

  const state = { stage: "open", band: "all", expanded: new Set() };
  const tiles = h("ul", { class: "leads-tiles" });
  const tbody = h("tbody");
  const caption = h("caption", { class: "muted small" });

  const select = (id, label, options, key) => h("div", { class: "field" },
    h("label", { for: id, text: label }),
    h("select", {
      id, class: "input",
      onchange: (e) => { state[key] = e.target.value; render(); announce(caption.textContent); },
    }, options.map(([v, t]) => h("option", { value: v, selected: state[key] === v }, t))));

  const filters = h("div", { class: "leads-filters" },
    select("f-stage", "שלב", [["open", "פתוחים"], ["all", "הכול"], ...Object.entries(STAGES)], "stage"),
    select("f-band", "סיכוי להזמנה", [["all", "הכול"], ...Object.entries(BANDS)], "band"));

  function visible() {
    return leads
      .filter((l) => (state.stage === "all" ? true : state.stage === "open" ? OPEN.has(l.stage) : l.stage === state.stage))
      .filter((l) => state.band === "all" || l.band === state.band)
      .sort((a, b) => (BAND_ORDER[a.band] ?? 3) - (BAND_ORDER[b.band] ?? 3) || (b.score ?? 0) - (a.score ?? 0));
  }

  function renderTiles() {
    const open = leads.filter((l) => OPEN.has(l.stage));
    const won = leads.filter((l) => l.stage === "won").length;
    const closed = won + leads.filter((l) => l.stage === "lost").length;
    const tile = (label, value) => h("li", { class: "panel leads-tile" },
      h("span", { class: "muted small", text: label }), h("strong", { class: "num", text: value }));
    fill(tiles,
      tile("לידים פתוחים", String(open.length)),
      tile("סיכוי גבוה (פתוחים)", String(open.filter((l) => l.band === "high").length)),
      tile("שיעור סגירה", closed ? `${Math.round((won / closed) * 100)}%` : "אין נתונים"));
  }

  function rows(l) {
    const open = state.expanded.has(l.id);
    const main = h("tr", {},
      h("th", { scope: "row", text: l.name }),
      h("td", { text: l.event_type }),
      h("td", { class: "hide-sm num", text: l.guests ? `${l.guests} אורחים` : "" }),
      h("td", { class: "hide-sm", text: SOURCES[l.source] ?? l.source }),
      h("td", {}, h("span", { class: "badge badge-pareve", text: STAGES[l.stage] })),
      h("td", {}, l.band
        ? h("span", { class: `lead-band lead-band-${l.band}`, text: BANDS[l.band] })
        : h("span", { class: "muted", text: "טרם נוקד" })),
      h("td", {}, h("button", {
        class: "btn btn-ghost lead-toggle", type: "button", "aria-expanded": String(open),
        "aria-label": `${open ? "הסתרת" : "הצגת"} פרטים: ${l.name}`,
        onclick: () => { open ? state.expanded.delete(l.id) : state.expanded.add(l.id); render(); },
      }, open ? "−" : "+")));
    if (!open) return main;
    const facts = [l.budget ? `תקציב ${fmtMoney(l.budget)}` : "", l.quote_amount ? `הצעה ${fmtMoney(l.quote_amount)}` : "", dayLabel(l.days_until_event)]
      .filter(Boolean).join(" · ");
    const detail = h("tr", { class: "lead-detail" }, h("td", { colspan: 7 },
      h("p", { class: "small", text: facts }),
      l.factors?.length
        ? [h("p", { class: "small", text: "מה השפיע על הדירוג:" }),
          h("ul", { class: "small" }, l.factors.map((f) =>
            h("li", { text: `${f.label}: ${f.effect === "up" ? "מעלה את הסיכוי" : "מוריד את הסיכוי"}` })))]
        : h("p", { class: "muted small", text: "אין עדיין הסבר לדירוג." })));
    return [main, detail];
  }

  function render() {
    const list = visible();
    caption.textContent = `מוצגים ${list.length} מתוך ${leads.length} לידים, ממוינים לפי הסיכוי להזמנה`;
    fill(tbody, list.length
      ? list.map(rows)
      : h("tr", {}, h("td", { colspan: 7, class: "muted", text: "אין לידים שמתאימים לסינון." })));
    renderTiles();
  }

  fill(root, head,
    demo ? h("p", { class: "leads-demo", text: "נתוני הדגמה סינתטיים. השמות והמספרים בדויים ואינם לקוחות אמיתיים." }) : null,
    tiles,
    h("p", { class: "leads-note muted small", text: "הדירוג הוא המלצה בלבד. הוא עוזר לסדר את רשימת המעקב ואינו משנה הצעה, מחיר או הזמנה." }),
    filters,
    h("table", { class: "leads-table" }, caption,
      h("thead", {}, h("tr", {},
        ["ליד", "אירוע", "אורחים", "מקור", "שלב", "סיכוי להזמנה", ""].map((t, i) =>
          h("th", { scope: "col", class: i === 2 || i === 3 ? "hide-sm" : null, text: t })))),
      tbody),
    modelsSection(models));
  render();
}

main();
