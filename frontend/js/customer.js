// Customer ordering flow (C1–C5): one page, steps switched by the URL hash.
// Runs on SAMPLE DATA until the order API exists. Totals are computed here only for display;
// the backend is authoritative for prices, quantities and order state (ADR 0003).
import {
  categories, dishes, unitLabels, unitNouns, kashrutLabels, dietLabels, allergenLabels,
  eventTypes, timeSlots, deliveryZone, blockedDates, draftOrder, assistantProposal, recommendedSaladTrays,
} from "/js/sample-data.js";
import { formatPrice, formatSignedPrice, formatWeekdayDate, formatDateTime } from "/js/format.js";
import { h, ltr, $ } from "/js/dom.js";

const order = structuredClone(draftOrder);
let proposal = { ...assistantProposal, state: "pending", baseVersion: order.version };
let activeCategory = "salads";
let submittedAt = null;

const dishById = Object.fromEntries(dishes.map((d) => [d.id, d]));

const guestTotal = () => order.event.adults + order.event.kids;
const subtotal = (lines = order.lines) =>
  Object.entries(lines).reduce((sum, [id, qty]) => sum + dishById[id].price * qty, 0);
const deliveryFee = () => (order.event.delivery ? deliveryZone.fee : 0);
const lineCount = () => Object.values(order.lines).filter((q) => q > 0).length;

function setQty(id, qty) {
  order.lines[id] = Math.max(0, qty);
  if (order.lines[id] === 0) delete order.lines[id];
  order.version += 1; // a manual change makes an open proposal stale
  renderAll();
}

// ---------- Routing ----------

const steps = ["event", "menu", "summary", "status"];

function route() {
  const id = steps.includes(location.hash.slice(1)) ? location.hash.slice(1) : "event";
  for (const s of steps) $(s).hidden = s !== id;
  [...$("progress").children].forEach((li, i) => {
    const current = steps[i] === id;
    li.querySelector("a").toggleAttribute("aria-current", current);
    if (current) li.querySelector("a").setAttribute("aria-current", "step");
    li.classList.toggle("done", i < steps.indexOf(id));
  });
  // The summary has its own "ask the assistant" button in the action bar.
  document.querySelector(".assistant-fab").hidden = id !== "menu";
  document.title = `${$(id).dataset.title} · שולחן מלא`;
  $(id).querySelector("h1").focus({ preventScroll: true });
  // After the browser's own jump to the #anchor, so each step starts at the top.
  requestAnimationFrame(() => window.scrollTo(0, 0));
}

// ---------- C1 Event details ----------

function radioChips(container, items, isSelected, onSelect) {
  container.replaceChildren(...items.map((item) => h("button", {
    type: "button", class: "chip", role: "radio",
    "aria-checked": String(isSelected(item)),
    "aria-disabled": item.full ? "true" : false,
    onclick: () => { if (!item.full) onSelect(item); },
  }, item.label, item.full ? h("span", { class: "chip__note" }, "מלא") : null)));
}

function renderEvent() {
  const e = order.event;
  radioChips($("event-types"), eventTypes.map((t) => ({ label: t })), (t) => t.label === e.type,
    (t) => { e.type = t.label; renderEvent(); });
  radioChips($("slots"), timeSlots, (s) => s.id === e.slot, (s) => { e.slot = s.id; renderEvent(); });
  document.querySelectorAll("[data-delivery]").forEach((b) =>
    b.setAttribute("aria-checked", String(String(e.delivery) === b.dataset.delivery)));
  $("address-field").hidden = !e.delivery;
  $("zone").textContent = `אזור ${deliveryZone.name}, דמי משלוח ${formatPrice(deliveryZone.fee)}`;
  $("guests").replaceChildren(
    guestRow("adults", "מבוגרים", "מגיל 12"),
    guestRow("kids", "ילדים", "גילאי 3 עד 12"),
    h("p", { class: "guest-rows__sub" }, "מתוכם"),
    guestRow("vegetarian", "צמחונים"),
    guestRow("vegan", "טבעונים"),
  );
  $("event-summary").textContent = `${guestTotal()} אורחים, ${e.delivery ? "משלוח" : "איסוף עצמי"}`;
}

function guestRow(key, label, note) {
  const e = order.event;
  const change = (d) => { e[key] = Math.max(0, e[key] + d); renderEvent(); $(`${key}-out`).focus(); };
  return h("div", { class: "guest-row" },
    h("span", { id: `${key}-label` }, label, note ? h("span", { class: "hint" }, ` ${note}`) : null),
    h("div", { class: "stepper", role: "group", "aria-labelledby": `${key}-label` },
      h("button", { type: "button", "aria-label": `פחות ${label}`, onclick: () => change(-1) }, "−"),
      h("output", { id: `${key}-out`, tabindex: "-1", "aria-live": "polite" }, String(e[key])),
      h("button", { type: "button", "aria-label": `עוד ${label}`, onclick: () => change(1) }, "+")));
}

function showError(field, message) {
  const err = $(`${field}-error`);
  err.textContent = message ?? "";
  err.hidden = !message;
  const input = $(field);
  if (input) input.toggleAttribute("aria-invalid", Boolean(message));
}

function submitEvent(ev) {
  ev.preventDefault();
  const e = order.event;
  e.date = $("date").value;
  e.address = $("address").value.trim();
  e.notes = $("notes").value;
  const errors = {
    date: !e.date ? "בחרו תאריך לאירוע." : blockedDates.includes(e.date) ? "התאריך הזה תפוס. בחרו תאריך אחר." : null,
    address: e.delivery && !e.address ? "כתבו כתובת למשלוח, או בחרו איסוף עצמי." : null,
    guests: guestTotal() === 0 ? "הוסיפו לפחות אורח אחד."
      : e.vegetarian + e.vegan > guestTotal() ? "מספר הצמחונים והטבעונים גדול ממספר האורחים." : null,
  };
  Object.entries(errors).forEach(([field, msg]) => showError(field, msg));
  const first = Object.keys(errors).find((f) => errors[f]);
  if (first) { ($(first) ?? $(`${first}-out`) ?? $("adults-out")).focus(); return; }
  location.hash = "#menu";
}

// ---------- C2 Dish catalog ----------

function dietTags(dish) {
  return [
    h("span", { class: "tag" }, kashrutLabels[dish.kashrut]),
    ...dish.diet.map((d) => h("span", { class: "tag" }, dietLabels[d])),
  ];
}

function allergenLine(dish) {
  const contains = Object.keys(dish.allergens).filter((a) => dish.allergens[a] === "contains").map((a) => allergenLabels[a]);
  const unknown = Object.keys(dish.allergens).filter((a) => dish.allergens[a] === "unknown").map((a) => allergenLabels[a]);
  return h("p", { class: "allergens" },
    `אלרגנים: ${contains.length ? contains.join(", ") : "אין ידועים"}`,
    unknown.length ? h("span", { class: "tag tag--warning" }, `? אין מידע על ${unknown.join(", ")}`) : null);
}

function renderMenu() {
  $("categories").replaceChildren(...categories.map((c) => h("button", {
    type: "button", class: "chip", "aria-pressed": String(c.id === activeCategory),
    onclick: () => { activeCategory = c.id; renderMenu(); },
  }, c.name)));

  const list = dishes.filter((d) => d.category === activeCategory);
  $("dish-list").replaceChildren(...(list.length ? list.map(dishItem)
    : [h("li", { class: "empty" }, "אין עדיין מנות בקטגוריה הזו. נסו קטגוריה אחרת.")]));

  const saladTrays = Object.entries(order.lines)
    .filter(([id]) => dishById[id].category === "salads").reduce((s, [, q]) => s + q, 0);
  $("recommendation").textContent =
    `לפי ${guestTotal()} אורחים מומלץ ${recommendedSaladTrays(guestTotal())} מגשי סלט. בחרתם ${saladTrays}.`;
  $("menu-count").textContent = `${lineCount()} מנות`;
  $("menu-total").textContent = formatPrice(subtotal());
}

function dishItem(dish) {
  const qty = order.lines[dish.id] ?? 0;
  return h("li", { class: "dish" },
    dish.photo ? h("div", { class: "photo-frame dish__photo" }, h("img", { src: dish.photo, alt: "", loading: "lazy", width: 96, height: 96 })) : null,
    h("div", { class: "dish__body" },
      h("h2", { class: "dish__name" }, dish.name),
      h("p", { class: "muted" }, dish.description),
      h("p", {}, ltr(formatPrice(dish.price)), ` ${unitLabels[dish.unit]}`, dish.serves ? `, ${dish.serves} סועדים` : ""),
      h("div", { class: "tags" }, dietTags(dish)),
      allergenLine(dish),
      qty
        ? h("div", { class: "stepper", role: "group", "aria-label": `כמות: ${dish.name}` },
          h("button", { type: "button", "aria-label": `פחות ${dish.name}`, onclick: () => setQty(dish.id, qty - 1) }, "−"),
          h("output", { "aria-live": "polite" }, `${qty} ${unitNouns[dish.unit]}`),
          h("button", { type: "button", "aria-label": `עוד ${dish.name}`, onclick: () => setQty(dish.id, qty + 1) }, "+"))
        : h("button", { type: "button", class: "btn", onclick: () => setQty(dish.id, 1) }, `הוספה: ${dish.name}`)));
}

// ---------- C3 Summary ----------

function renderSummary() {
  const e = order.event;
  const slot = timeSlots.find((s) => s.id === e.slot)?.label ?? "";
  $("summary-event").replaceChildren(
    h("dt", {}, "אירוע"), h("dd", {}, `${e.type}, ${formatWeekdayDate(e.date)}, `, ltr(slot)),
    h("dt", {}, e.delivery ? "משלוח" : "איסוף"), h("dd", {}, e.delivery ? e.address : "איסוף עצמי מהעסק"),
    h("dt", {}, "אורחים"), h("dd", {}, `${guestTotal()} (${e.vegetarian} צמחונים, ${e.vegan} טבעונים)`));

  const ids = Object.keys(order.lines);
  $("lines").replaceChildren(...(ids.length ? ids.map((id) => {
    const dish = dishById[id];
    const qty = order.lines[id];
    return h("li", { class: "line" },
      h("div", {},
        h("h2", { class: "dish__name" }, dish.name, " ", h("span", { class: "tag" }, kashrutLabels[dish.kashrut])),
        h("p", { class: "muted" }, `${qty} ${unitNouns[dish.unit]} × `, ltr(formatPrice(dish.price))),
        proposal.state === "applied" && proposal.changes.some((c) => c.dishId === id)
          ? h("p", { class: "hint" }, "שונה בעקבות הצעת העוזר") : null),
      h("div", { class: "line__end" },
        h("strong", {}, ltr(formatPrice(dish.price * qty))),
        h("div", { class: "stepper", role: "group", "aria-label": `כמות: ${dish.name}` },
          h("button", { type: "button", "aria-label": `פחות ${dish.name}`, onclick: () => setQty(id, qty - 1) }, "−"),
          h("button", { type: "button", "aria-label": `עוד ${dish.name}`, onclick: () => setQty(id, qty + 1) }, "+"))));
  }) : [h("li", { class: "empty" }, "עוד לא בחרתם מנות. ", h("a", { href: "#menu" }, "לבחירת מנות"))]));

  const kinds = new Set(ids.map((id) => dishById[id].kashrut));
  $("kashrut-notice").hidden = !(kinds.has("meat") && kinds.has("dairy"));
  $("totals").replaceChildren(
    h("dt", {}, "ביניים"), h("dd", {}, ltr(formatPrice(subtotal()))),
    h("dt", {}, `דמי משלוח (${deliveryZone.name})`), h("dd", {}, ltr(formatPrice(deliveryFee()))),
    h("dt", { class: "totals__grand" }, "סה״כ"), h("dd", { class: "totals__grand" }, ltr(formatPrice(subtotal() + deliveryFee()))));
  $("submit-request").setAttribute("aria-disabled", String(ids.length === 0));
}

// ---------- C4 Assistant (proposal → explicit approval) ----------

function proposalState() {
  if (proposal.state === "pending" && proposal.baseVersion !== order.version) return "expired";
  return proposal.state;
}

function renderAssistant() {
  const state = proposalState();
  const after = { ...order.lines };
  if (state === "pending") for (const c of proposal.changes) after[c.dishId] = c.to;
  const statusText = { pending: "ממתין לאישורכם", applied: "השינוי בוצע", rejected: "ההצעה נדחתה", expired: "ההזמנה השתנתה" }[state];

  const card = h("article", { class: `proposal proposal--${state}`, "aria-labelledby": "proposal-title", tabindex: "-1" },
    h("header", { class: "proposal__head" },
      h("h3", { id: "proposal-title" }, "הצעה לשינוי"),
      h("span", { class: `status ${state === "applied" ? "status--approved" : state === "pending" ? "status--pending" : "status--draft"}` },
        state === "pending" ? "🕓 " : state === "applied" ? "✓ " : "", statusText)),
    h("ul", { class: "proposal__changes" }, proposal.changes.map((c) => {
      const dish = dishById[c.dishId];
      return h("li", {},
        h("span", {}, c.from === 0 ? "הוספה: " : "שינוי כמות: ", dish.name, ", ",
          c.from === 0 ? `${c.to} ${unitNouns[dish.unit]}` : h("span", {}, ltr(`${c.from} → ${c.to}`), ` ${unitNouns[dish.unit]}`)),
        h("strong", {}, ltr(formatSignedPrice((c.to - c.from) * dish.price))));
    })),
    state === "pending" ? h("p", { class: "proposal__total" },
      "סה״כ ", ltr(`${formatPrice(subtotal())} → ${formatPrice(subtotal(after))}`)) : null,
    h("p", { class: "hint" }, state === "expired"
      ? "ההזמנה השתנתה מאז שההצעה נוצרה. בקשו מהעוזר הצעה חדשה."
      : "המחירים מחושבים במערכת, לא על ידי העוזר."),
    state === "pending" ? h("div", { class: "proposal__actions" },
      h("button", { type: "button", class: "btn", onclick: () => decide("rejected") }, "לא, תודה"),
      h("button", { type: "button", class: "btn btn--primary", onclick: () => decide("applied") }, "אישור השינוי")) : null);

  $("assistant-log").replaceChildren(
    h("p", { class: "msg msg--user" }, proposal.question),
    h("p", { class: "msg msg--assistant" }, proposal.answer),
    card,
    ...(proposal.followUps ?? []).map((t) => h("p", { class: `msg ${t.from === "user" ? "msg--user" : "msg--assistant"}` }, t.text)));
}

function decide(state) {
  if (proposalState() !== "pending") return;
  if (state === "applied") {
    for (const c of proposal.changes) order.lines[c.dishId] = c.to;
    order.version += 1;
  }
  proposal = { ...proposal, state };
  renderAll();
  // The decision buttons are gone now, so keep keyboard focus on the card that changed.
  $("assistant-log").querySelector(".proposal").focus();
}

function sendToAssistant(ev) {
  ev.preventDefault();
  const text = $("assistant-text").value.trim();
  if (!text) return;
  // Placeholder until the agent API (Phase 4): the prototype only shows the sample proposal.
  proposal.followUps = [...(proposal.followUps ?? []),
    { from: "user", text },
    { from: "assistant", text: "בגרסת התצוגה הזו העוזר עוד לא מחובר. ההצעה למעלה היא הצעה לדוגמה." }];
  $("assistant-text").value = "";
  renderAssistant();
}

// ---------- C5 Status ----------

function submitRequest() {
  if ($("submit-request").getAttribute("aria-disabled") === "true") return;
  submittedAt = new Date().toISOString();
  renderStatus(); // the timeline shows the submission time
  location.hash = "#status";
}

function renderStatus() {
  const total = subtotal() + deliveryFee();
  const timeline = [
    ["done", "טיוטה", null],
    ["current", "נשלחה לאישור", submittedAt ? formatDateTime(submittedAt) : null],
    ["todo", "אישור או דחייה של בעל העסק", "מענה צפוי תוך 48 שעות"],
    ["todo", "תיאום סופי", "פרטי איסוף או משלוח"],
  ];
  $("status-body").replaceChildren(
    h("p", {}, h("span", { class: "status status--pending" }, "🕓 ממתין לאישור העסק"), " בקשה ", ltr("#Q-1042")),
    h("ol", { class: "timeline" }, timeline.map(([state, label, note]) =>
      h("li", { class: `timeline__step timeline__step--${state}`, "aria-current": state === "current" ? "step" : false },
        h("span", {}, label), note ? h("span", { class: "hint" }, ltr(note)) : null))),
    h("dl", { class: "totals" },
      h("dt", {}, "סה״כ להצעה"), h("dd", { class: "totals__grand" }, ltr(formatPrice(total)))),
    h("p", { class: "hint" }, "המחירים נשמרו ברגע השליחה, ולא ישתנו גם אם התפריט יתעדכן."),
    h("h2", {}, "מה כל סטטוס אומר"),
    h("dl", { class: "legend" },
      h("dt", {}, h("span", { class: "status status--draft" }, "טיוטה")), h("dd", {}, "הבקשה עדיין אצלכם ולא נשלחה."),
      h("dt", {}, h("span", { class: "status status--pending" }, "🕓 ממתין לאישור העסק")), h("dd", {}, "העסק בודק תאריך, זמינות ומחיר."),
      h("dt", {}, h("span", { class: "status status--approved" }, "✓ אושר")), h("dd", {}, "העסק אישר. האירוע שמור ביומן."),
      h("dt", {}, h("span", { class: "status status--rejected" }, "✕ נדחה")), h("dd", {}, "העסק לא יכול לספק את ההזמנה בתאריך הזה.")),
    h("a", { class: "btn", href: "/" }, "חזרה לדף הבית"));
}

// ---------- Wiring ----------

function renderAll() {
  renderEvent();
  renderMenu();
  renderSummary();
  renderAssistant();
  renderStatus();
}

$("date").value = order.event.date;
$("date").min = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
$("address").value = order.event.address;
$("notes").value = order.event.notes;
document.querySelectorAll("[data-delivery]").forEach((b) => b.addEventListener("click", () => {
  order.event.delivery = b.dataset.delivery === "true";
  renderEvent();
}));
$("event-form").addEventListener("submit", submitEvent);
$("submit-request").addEventListener("click", submitRequest);
$("assistant-form").addEventListener("submit", sendToAssistant);
document.querySelectorAll("[data-open-assistant]").forEach((b) => b.addEventListener("click", () => $("assistant").showModal()));
$("close-assistant").addEventListener("click", () => $("assistant").close());
window.addEventListener("hashchange", route);

renderAll();
route();
