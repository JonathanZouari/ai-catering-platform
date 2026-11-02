// Owner screen A1: submitted orders, detail from the frozen price snapshot, approve / reject.
// All server data is written with textContent only (never innerHTML).
import { $, call, el, explain, startAdmin, toast } from "/js/admin-common.js";

const STATUS = { pending_approval: "ממתינה לאישור", approved: "אושרה", rejected: "נדחתה" };
const FILTERS = [["pending_approval", "ממתינות"], ["approved", "אושרו"], ["rejected", "נדחו"], ["", "הכל"]];
const FULFILLMENT = { pickup: "איסוף עצמי", delivery: "משלוח" };
const UNIT = { per_guest: "לאורח", per_tray: "למגש", per_weight: 'לק"ג', per_item: "ליחידה" };
const ERRORS = { invalid_transition: "ההזמנה כבר טופלה. הרשימה עודכנה" };

const state = { filter: "pending_approval", orders: [], selected: null };

// shortcut: fixed ILS until currency is decided (OPEN_DECISIONS #17).
const money = (v) => (v === null || v === undefined ? "—" : new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format(v));
const day = (iso) => new Intl.DateTimeFormat("he-IL", { weekday: "short", day: "numeric", month: "short", year: "numeric" }).format(new Date(`${iso}T00:00`));
const when = (iso) => new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
const qty = (v) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(v);

function renderFilters() {
  $("filters").replaceChildren(...FILTERS.map(([value, label]) => {
    const b = el("button", { type: "button", className: "chip-btn", textContent: label });
    b.setAttribute("aria-pressed", String(state.filter === value));
    b.onclick = () => { state.filter = value; renderFilters(); load().catch(fail); };
    return b;
  }));
}

async function load() {
  state.orders = await call(`/api/admin/orders${state.filter ? `?status=${state.filter}` : ""}`);
  renderList();
  if (state.selected && !state.orders.some((o) => o.id === state.selected)) {
    state.selected = null;
    $("detail").hidden = true;
  }
}

function renderList() {
  $("no-orders").hidden = state.orders.length > 0;
  $("order-list").replaceChildren(...state.orders.map((o) => {
    const row = el("button", { type: "button", className: `order-row${o.id === state.selected ? " selected" : ""}` },
      el("span", { className: "o-id", dir: "ltr", textContent: `#${o.id.slice(0, 8)}` }),
      el("span", { className: "o-name", textContent: o.customer_name }),
      el("span", { className: "o-total num", textContent: money(o.total) }),
      el("span", { className: "o-meta", textContent: `${o.event_type} · ${day(o.event_date)} · ${o.guests} אורחים · ${FULFILLMENT[o.fulfillment_type]}` }),
      el("span", { className: `pill s-${o.status}`, textContent: STATUS[o.status] }));
    if (o.id === state.selected) row.setAttribute("aria-current", "true");
    row.onclick = () => openOrder(o.id).catch(fail);
    return el("li", {}, row);
  }));
}

const fact = (term, value) => el("div", {}, el("dt", { textContent: term }), el("dd", { textContent: value }));

async function openOrder(id) {
  const o = await call(`/api/admin/orders/${id}`);
  state.selected = o.id;
  renderList();
  const e = o.event;
  $("detail-h").textContent = `${o.customer.full_name} · ${e.event_type}`;
  $("d-status").className = `pill s-${o.status}`;
  $("d-status").textContent = STATUS[o.status];

  const facts = [
    ["תאריך האירוע", day(e.event_date)],
    ["אורחים", `${e.adults} מבוגרים, ${e.children} ילדים`],
    ["צמחונים / טבעונים / הגבלות", `${e.vegetarian_guests} / ${e.vegan_guests} / ${e.restricted_guests}`],
    [FULFILLMENT[o.fulfillment_type], when(o.requested_at)],
  ];
  if (o.delivery_address) facts.push(["כתובת", o.delivery_address]);
  if (e.dietary_notes) facts.push(["הערות תזונה", e.dietary_notes]);
  facts.push(["טלפון", o.customer.phone ?? "—"], ["אימייל", o.customer.email ?? "—"]);
  if (o.submitted_at) facts.push(["נשלחה", when(o.submitted_at)]);
  $("d-facts").replaceChildren(...facts.map(([t, v]) => fact(t, v)));

  $("d-items").replaceChildren(...o.items.map((i) => el("tr", {},
    el("th", { scope: "row", textContent: i.name ?? "—" }),
    el("td", { className: "num", textContent: `${qty(i.quantity)} ${UNIT[i.pricing_unit] ?? ""}` }),
    el("td", { className: "num", textContent: money(i.unit_price) }),
    el("td", { className: "num", textContent: money(i.line_total) }))));

  const totals = [fact("ביניים", money(o.subtotal))];
  if (o.delivery_fee !== null) totals.push(fact("משלוח", money(o.delivery_fee)));
  const grand = fact('סה"כ', money(o.total));
  grand.className = "grand";
  $("d-totals").replaceChildren(...totals, grand);

  const note = $("d-note");
  note.hidden = !o.decision_note && !o.decided_at;
  note.replaceChildren(
    o.decision_note ?? "",
    el("footer", { textContent: o.decided_at ? `${STATUS[o.status]} ב-${when(o.decided_at)}` : "" }));

  $("decision").hidden = o.status !== "pending_approval";
  $("decision").reset();
  $("decision-error").hidden = true;
  $("note").removeAttribute("aria-invalid");
  $("detail").hidden = false;
  if (matchMedia("(max-width: 899px)").matches) {
    $("detail").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }
}

async function decide(approve) {
  const note = $("note").value.trim();
  const error = $("decision-error");
  if (!approve && !note) {
    error.textContent = "כדי לדחות צריך לכתוב ללקוח למה";
    error.hidden = false;
    $("note").setAttribute("aria-invalid", "true");
    $("note").focus();
    return;
  }
  for (const b of [$("approve"), $("reject")]) b.disabled = true;
  try {
    await call(`/api/admin/orders/${state.selected}/${approve ? "approve" : "reject"}`, {
      method: "POST", body: JSON.stringify({ note: note || null }),
    });
    toast(approve ? "ההזמנה אושרה" : "ההזמנה נדחתה");
    const id = state.selected;
    await load();
    if (state.orders.some((o) => o.id === id)) await openOrder(id);
  } catch (err) {
    if (err.status === 401) return;
    if (err.code === "invalid_transition") {
      // Someone else decided it meanwhile: show the current state instead of a stale form.
      const id = state.selected;
      await load().catch(() => {});
      if (state.orders.some((o) => o.id === id)) await openOrder(id).catch(() => {});
      toast(explain(err));
      return;
    }
    error.textContent = explain(err);
    error.hidden = false;
  } finally {
    for (const b of [$("approve"), $("reject")]) b.disabled = false;
  }
}

function fail(err) {
  if (err.status !== 401) toast(explain(err));
}

export function initOrders() {
  renderFilters();
  $("approve").addEventListener("click", () => decide(true));
  $("reject").addEventListener("click", () => decide(false));
  $("note").addEventListener("input", () => $("note").removeAttribute("aria-invalid"));
  startAdmin({ content: "orders", load, errors: ERRORS });
}
