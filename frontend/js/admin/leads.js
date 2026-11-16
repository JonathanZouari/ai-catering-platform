// Owner's leads list: each open lead with its estimated chance of a purchase.
// The backend computes and sorts by the probability; this file only displays it.
// Reads go through the backend with the admin's own token. Status changes go straight to
// Supabase. In both cases row level security, not this page, enforces the admin role.
import { api } from "../api.js";
import { announce } from "../lib/announce.js";
import { fill, h } from "../lib/dom.js";
import { fmtDateShort, fmtMoney, fmtNumber, fmtPercent } from "../lib/format.js";
import { isAdmin, requireSession, sb } from "../lib/supabase.js";

const LEADS_URL = "/api/admin/leads";
const LOADING_DELAY_MS = 400; // a faster response shows no loading message at all

const STATUS_LABELS = {
  new: "חדש",
  contacted: "נוצר קשר",
  quoted: "נשלחה הצעה",
  won: "נסגר בהזמנה",
  lost: "לא נסגר",
};
const SOURCE_LABELS = { referral: "המלצה", google: "גוגל", instagram: "אינסטגרם", website: "האתר" };
const OPEN_STATUSES = ["new", "contacted", "quoted"];
const FILTERS = [
  ["open", "לידים פתוחים"],
  ["all", "כל הלידים"],
  ...Object.entries(STATUS_LABELS),
];

const listEl = document.getElementById("leads");
const countEl = document.getElementById("leads-count");
const filterEl = document.getElementById("status-filter");

let leads = [];

fill(filterEl, FILTERS.map(([value, label]) => h("option", { value }, label)));
filterEl.addEventListener("change", renderList);

const session = await requireSession();
if (isAdmin(session)) {
  load();
} else {
  document.querySelector(".leads-toolbar").hidden = true;
  fill(listEl, h("p", { class: "leads-message", role: "alert" }, "לחשבון הזה אין הרשאת ניהול."));
}

async function load() {
  countEl.textContent = "";
  fill(listEl);
  const timer = setTimeout(() => fill(listEl, h("p", { class: "leads-message", role: "status" }, "טוען לידים…")), LOADING_DELAY_MS);
  try {
    // getSession returns a refreshed token when the stored one has expired.
    const { data } = await sb.auth.getSession();
    leads = await api(LEADS_URL, { headers: { Authorization: `Bearer ${data.session?.access_token ?? ""}` } });
    renderList();
  } catch {
    renderLoadError();
  } finally {
    clearTimeout(timer);
  }
}

function renderLoadError() {
  fill(listEl,
    h("div", { class: "leads-message", role: "alert" },
      h("p", {}, "טעינת הלידים נכשלה. הנתונים לא השתנו."),
      h("button", { class: "btn btn-secondary", type: "button", onClick: load }, "ניסיון נוסף")));
}

function matchesFilter(lead) {
  const filter = filterEl.value;
  if (filter === "all") return true;
  if (filter === "open") return OPEN_STATUSES.includes(lead.status);
  return lead.status === filter;
}

function renderList() {
  if (leads.length === 0) {
    countEl.textContent = "";
    fill(listEl, h("p", { class: "leads-message" }, "עדיין אין לידים. פניות חדשות יופיעו כאן."));
    return;
  }
  const visible = leads.filter(matchesFilter);
  countEl.textContent = `מוצגים ${fmtNumber(visible.length)} מתוך ${fmtNumber(leads.length)} לידים`;
  if (visible.length === 0) {
    fill(listEl, h("p", { class: "leads-message" }, "אין לידים בסטטוס הזה. אפשר לבחור סטטוס אחר."));
    return;
  }
  // Explicit ARIA roles keep the table structure for screen readers when the narrow layout
  // turns rows into cards with CSS.
  fill(listEl,
    h("table", { class: "leads-table", role: "table" },
      h("caption", { class: "visually-hidden" }, "לידים, מהסיכוי הגבוה לרכישה לנמוך"),
      h("thead", { role: "rowgroup" },
        h("tr", { role: "row" },
          ["שם", "אירוע", "אורחים", "תקציב לאורח", "מקור", "סטטוס"].map((label) =>
            h("th", { role: "columnheader", scope: "col" }, label)),
          h("th", { role: "columnheader", scope: "col", "aria-sort": "descending" }, "סיכוי לרכישה"))),
      h("tbody", { role: "rowgroup" }, visible.map(renderRow))));
}

function cell(label, ...children) {
  return h("td", { role: "cell", "data-label": label }, ...children);
}

function renderRow(lead) {
  const chance = cell("סיכוי לרכישה");
  fillChance(chance, lead);
  const error = h("p", { class: "leads-error", role: "alert", hidden: true });
  const select = h("select", {
    class: "input",
    "aria-label": `סטטוס של ${lead.full_name}`,
    onChange: () => saveStatus(lead, select, chance, error),
  }, Object.entries(STATUS_LABELS).map(([value, label]) =>
    h("option", { value, selected: value === lead.status }, label)));

  return h("tr", { role: "row" },
    h("th", { role: "rowheader", scope: "row", "data-label": "שם" },
      h("bdi", {}, lead.full_name),
      lead.phone && h("a", { class: "leads-phone", href: `tel:${lead.phone}`, dir: "ltr" }, lead.phone)),
    cell("אירוע", lead.event_type, h("span", { class: "leads-sub", dir: "ltr" }, fmtDateShort(lead.event_date))),
    cell("אורחים", fmtNumber(lead.guests)),
    cell("תקציב לאורח", fmtMoney(lead.budget_per_guest)),
    cell("מקור", SOURCE_LABELS[lead.source] ?? lead.source),
    cell("סטטוס", select, error),
    chance);
}

function fillChance(el, lead) {
  if (!OPEN_STATUSES.includes(lead.status)) {
    fill(el, h("span", { class: "leads-sub" }, "ליד סגור"));
    return;
  }
  const bar = h("span", { class: "chance-bar", "aria-hidden": "true" }, h("span", {}));
  // Width comes from the data, so it is set at runtime rather than in the stylesheet.
  bar.firstChild.style.inlineSize = `${Math.round(lead.purchase_probability * 100)}%`;
  fill(el, h("span", { class: "chance" }, h("span", { class: "chance-value" }, fmtPercent(lead.purchase_probability)), bar));
}

async function saveStatus(lead, select, chanceEl, errorEl) {
  const status = select.value;
  errorEl.hidden = true;
  select.disabled = true;
  try {
    const { error } = await sb.from("leads").update({ status }).eq("id", lead.id).select("id").single();
    if (error) throw error;
    lead.status = status;
    fillChance(chanceEl, lead);
    announce(`הסטטוס של ${lead.full_name} עודכן: ${STATUS_LABELS[lead.status]}`);
  } catch {
    select.value = lead.status;
    errorEl.textContent = "הסטטוס לא נשמר. אפשר לנסות שוב.";
    errorEl.hidden = false;
  } finally {
    select.disabled = false;
    select.focus();
  }
}
