// Owner leads screen: open drafts with the model's purchase probability, highest first.
// All server data is written with textContent only (never innerHTML).
import { $, call, el, startAdmin } from "/js/admin-common.js";

const FULFILLMENT = { pickup: "איסוף עצמי", delivery: "משלוח" };
const MODEL = { linear: "רגרסיה ליניארית", logistic: "רגרסיה לוגיסטית" };

const day = (iso) => new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "short", year: "numeric" }).format(new Date(`${iso}T00:00`));
const when = (iso) => new Intl.DateTimeFormat("he-IL", { dateStyle: "medium" }).format(new Date(iso));
const percent = (v) => new Intl.NumberFormat("he-IL", { style: "percent" }).format(v);

function contact(lead) {
  const links = [];
  if (lead.phone) links.push(el("a", { href: `tel:${lead.phone}`, dir: "ltr", textContent: lead.phone }));
  if (lead.email) links.push(el("a", { href: `mailto:${lead.email}`, dir: "ltr", textContent: lead.email }));
  return links.length ? links.flatMap((a, i) => (i ? [el("br"), a] : [a])) : ["—"];
}

async function load() {
  const data = await call("/api/admin/leads");
  $("synthetic-note").hidden = data.model_source !== "synthetic";
  $("model-line").textContent = `מודל: ${MODEL[data.model_kind]} · אומן ב-${when(data.trained_at)}`;
  $("no-leads").hidden = data.leads.length > 0;
  $("lead-table").hidden = data.leads.length === 0;
  $("lead-rows").replaceChildren(...data.leads.map((lead) => el("tr", {},
    el("th", { scope: "row", textContent: lead.customer_name }),
    el("td", { textContent: `${lead.event_type} · ${day(lead.event_date)}` }),
    el("td", { className: "num", textContent: lead.guests }),
    el("td", { textContent: FULFILLMENT[lead.fulfillment_type] }),
    el("td", {}, ...contact(lead)),
    el("td", { textContent: when(lead.created_at) }),
    // last column: .lines styles it bold and end-aligned, like the totals in the order tables
    el("td", { className: "num", textContent: percent(lead.score) }))));
}

export function initLeads() {
  startAdmin({ content: "leads", load });
}
