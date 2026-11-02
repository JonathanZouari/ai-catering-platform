// Screen C5: where the customer's order stands, its frozen prices, and the one action the customer
// has while it awaits approval: take it back to draft (OPEN_DECISIONS #7), and the answer to an
// owner change proposal (OPEN_DECISIONS #6). Text via textContent.
import { call, session } from "/js/customer-session.js";

const TZ = "Asia/Jerusalem";
const UNIT = { per_tray: "מגשים", per_guest: "מנות", per_weight: 'ק"ג', per_item: "יחידות" };
const UNIT_ONE = { per_tray: "מגש", per_guest: "מנה", per_weight: 'ק"ג', per_item: "יחידה" };
const units = (quantity, unit) => (Number(quantity) === 1 ? UNIT_ONE : UNIT)[unit] ?? "";
const FULFILLMENT = { pickup: "איסוף עצמי", delivery: "משלוח" };
const LEDE = {
  draft: "ההזמנה עדיין טיוטה. אפשר להמשיך לערוך ולשלוח אותה.",
  pending_approval: "ההזמנה נשלחה ומחכה לאישור בעל העסק. נעדכן אתכם במייל.",
  approved: "ההזמנה אושרה. לשינויים מעכשיו דברו עם בעל העסק.",
  rejected: "ההזמנה לא אושרה. ההסבר של בעל העסק מופיע למטה.",
};
const OP = { add_item: ["נוספה", "add"], set_quantity: ["שינוי", "chg"], remove_item: ["הוסרה", "chg"] };
const PROPOSAL_ERRORS = {
  proposal_expired: "ההזמנה השתנתה מאז ההצעה, ולכן היא כבר לא בתוקף.",
  proposal_not_pending: "ההצעה כבר לא פתוחה.",
};
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const $ = (id) => document.getElementById(id);
let order = null;

const money = (v) => new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format(v);
const num = (v) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(v);
const when = (iso) => new Intl.DateTimeFormat("he-IL", { timeZone: TZ, dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
const day = (iso) => new Intl.DateTimeFormat("he-IL", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}T00:00Z`));

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

function notice(text) {
  $("page-notice").textContent = text;
  $("page-notice").hidden = !text;
}

function timeline() {
  const s = order.status;
  const decided = s === "approved" || s === "rejected";
  const steps = [
    ["טיוטה", true, s === "draft", null],
    ["נשלחה לאישור", s !== "draft", s === "pending_approval", order.submitted_at],
    [s === "rejected" ? "לא אושרה" : "אושרה", decided, decided, order.decided_at],
  ];
  $("timeline").replaceChildren(...steps.map(([label, done, now, at]) => {
    const li = el("li", { className: now ? "now" : done ? "done" : "" }, label);
    if (at) li.append(el("span", { className: "help", textContent: when(at) }));
    if (now) li.setAttribute("aria-current", "step");
    return li;
  }));
}

function actions() {
  const out = [];
  const id = encodeURIComponent(order.id);
  if (order.status === "draft") {
    out.push(el("a", { className: "btn primary", href: `/customer/menu/?order=${id}`, textContent: "המשך עריכה ושליחה" }));
  }
  if (order.status === "pending_approval") {
    const back = el("button", { type: "button", className: "btn ghost", textContent: "החזרה לעריכה" });
    back.addEventListener("click", withdraw);
    out.push(back);
  }
  out.push(el("a", { className: "btn ghost", href: "/customer/", textContent: "לאזור האישי" }));
  $("actions").replaceChildren(...out);
}

function proposalCard(p) {
  const delta = Number(p.price_after) - Number(p.price_before);
  const list = el("ul", { className: "diff" }, ...p.changes.map((c) => {
    const [label, cls] = OP[c.op];
    const amounts = c.op === "set_quantity" ? ` ${num(c.from_quantity)} → ${num(c.to_quantity)}`
      : c.op === "add_item" ? ` × ${num(c.to_quantity)}` : "";
    return el("li", {}, el("span", { className: `op ${cls}`, textContent: label }), `${c.name}${amounts}`);
  }));
  const card = el("div", { className: "proposal" },
    el("h4", { textContent: "בעל העסק הציע שינוי בהזמנה" }), list,
    el("p", { className: "diff-total" }, `סה"כ ${money(p.price_before)} → ${money(p.price_after)} `,
      el("span", { textContent: `(${delta >= 0 ? "+" : ""}${money(delta)})` })));
  if (p.note) card.append(el("p", { className: "why", textContent: p.note }));
  card.append(el("p", { className: "fine", textContent: "אם תאשרו, ההזמנה מאושרת מיד עם השינויים. אם תדחו, ההזמנה נשארת כמו שהייתה ובעל העסק יחליט." }));

  const reason = el("textarea", { id: "decline-note", rows: 2, maxLength: 1000 });
  const reasonField = el("div", { className: "field" }, el("label", { htmlFor: "decline-note", textContent: "סיבה לדחייה (לא חובה)" }), reason);
  reasonField.hidden = true;
  const decline = el("button", { type: "button", className: "btn ghost", textContent: "דחיית ההצעה" });
  const accept = el("button", { type: "button", className: "btn primary", textContent: "אישור ההצעה" });
  const answer = async (action, body) => {
    accept.disabled = decline.disabled = true;
    $("action-error").hidden = true;
    try {
      await call(`/api/orders/${order.id}/proposals/${p.id}/${action}`, { method: "POST", body: body ? JSON.stringify(body) : undefined });
    } catch (err) {
      if (err.status === 401) { location.href = "/customer/"; return; }
      $("action-error").textContent = PROPOSAL_ERRORS[err.code] ?? "לא הצלחנו לשלוח את התשובה. נסו שוב.";
      $("action-error").hidden = false;
    }
    await load();
  };
  accept.addEventListener("click", () => answer("accept"));
  decline.addEventListener("click", () => {
    if (reasonField.hidden) { reasonField.hidden = false; decline.textContent = "שליחת הדחייה"; reason.focus(); return; }
    answer("decline", { note: reason.value.trim() || null });
  });
  card.append(reasonField, el("div", { className: "proposal-actions" }, decline, accept));
  return card;
}

async function withdraw(e) {
  const button = e.currentTarget;
  button.disabled = true;
  $("action-error").hidden = true;
  try {
    await call(`/api/orders/${order.id}/withdraw`, { method: "POST", body: JSON.stringify({ version: order.version }) });
    location.href = `/customer/menu/?order=${encodeURIComponent(order.id)}`;
  } catch (err) {
    if (err.status === 401) { location.href = "/customer/"; return; }
    $("action-error").textContent = err.code === "invalid_transition"
      ? "בעל העסק כבר טיפל בהזמנה, ולכן אי אפשר להחזיר אותה לעריכה."
      : "לא הצלחנו להחזיר לעריכה. נסו שוב.";
    $("action-error").hidden = false;
    await load();
  }
}

const fact = (term, value, cls = "") => el("div", { className: cls }, el("dt", { textContent: term }), el("dd", { textContent: value }));

async function load() {
  order = await call(`/api/orders/${order?.id ?? new URLSearchParams(location.search).get("order")}`);
  const [pricing, proposals] = await Promise.all([
    call(`/api/orders/${order.id}/pricing`), call(`/api/orders/${order.id}/proposals`),
  ]);
  const pending = proposals.find((p) => p.status === "pending");
  $("proposal-area").replaceChildren(...(pending ? [proposalCard(pending)] : []));
  const e = order.event;
  $("title").textContent = `${e.event_type}, ${day(e.event_date)}`;
  $("lede").textContent = pending ? "בעל העסק הציע שינוי. עיינו בהצעה ואשרו או דחו אותה." : LEDE[order.status];
  timeline();
  actions();

  const note = $("owner-note");
  note.hidden = !order.decision_note;
  note.replaceChildren(order.decision_note ?? "", el("footer", { textContent: "הודעה מבעל העסק" }));

  const facts = [
    ["תאריך", day(e.event_date)],
    ["אורחים", `${e.adults} מבוגרים, ${e.children} ילדים`],
    ["צמחונים / טבעונים / הגבלות", `${e.vegetarian_guests} / ${e.vegan_guests} / ${e.restricted_guests}`],
    [FULFILLMENT[order.fulfillment_type], when(order.requested_at)],
  ];
  if (order.delivery_address) facts.push(["כתובת", [order.delivery_address, order.delivery_city].filter(Boolean).join(", ")]);
  if (e.dietary_notes) facts.push(["הערות תזונה", e.dietary_notes]);
  $("facts").replaceChildren(...facts.map(([t, v]) => fact(t, v)));

  $("lines").replaceChildren(...pricing.lines.map((l) => el("tr", {},
    el("th", { scope: "row", textContent: l.name }),
    el("td", { className: "num", textContent: `${num(l.quantity)} ${units(l.quantity, l.pricing_unit)}` }),
    el("td", { className: "num", textContent: money(l.unit_price) }),
    el("td", { className: "num", textContent: money(l.line_total) }))));
  const rows = [fact("ביניים", money(pricing.subtotal))];
  if (order.fulfillment_type === "delivery") {
    rows.push(fact("משלוח", pricing.delivery_fee === null ? "אין משלוח לעיר שנבחרה" : money(pricing.delivery_fee)));
  }
  rows.push(fact('סה"כ כולל מע"מ', money(pricing.total), "grand"));
  $("totals").replaceChildren(...rows);
  $("price-note").textContent = order.status === "draft"
    ? "המחירים מתעדכנים לפי התפריט עד שליחת ההזמנה."
    : "המחירים נקבעו ברגע השליחה ולא ישתנו.";
  $("status").hidden = false;
}

export async function initOrderStatus() {
  const id = new URLSearchParams(location.search).get("order") ?? "";
  try {
    if (!(await session())) { location.href = "/customer/"; return; }
  } catch {
    notice("הכניסה ללקוחות עוד לא מוגדרת באתר. נסו שוב מאוחר יותר.");
    return;
  }
  if (!UUID.test(id)) { location.href = "/customer/"; return; }
  try {
    await load();
  } catch (err) {
    if (err.status === 401) { location.href = "/customer/"; return; }
    notice(err.status === 404 ? "לא מצאנו את ההזמנה הזו." : "לא הצלחנו לטעון את ההזמנה. נסו שוב.");
  }
}
