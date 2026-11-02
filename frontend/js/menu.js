// Screens C2 (dish selection) and C3 (summary). Quantities are only requests: the backend checks
// steps, minimums and availability, and computes every price (ADR 0003). Text via textContent only.
import { api } from "/js/api.js";
import { call, session } from "/js/customer-session.js";

const KASHRUT = { meat: ["בשרי", "k-meat"], dairy: ["חלבי", "k-dairy"], pareve: ["פרווה", "k-parve"] };
const UNIT = { per_tray: "מגשים", per_guest: "מנות", per_weight: 'ק"ג', per_item: "יחידות" };
const UNIT_ONE = { per_tray: "מגש", per_guest: "מנה", per_weight: 'ק"ג', per_item: "יחידה" };
const units = (quantity, unit) => (Number(quantity) === 1 ? UNIT_ONE : UNIT)[unit] ?? "";
const PER = { per_tray: "למגש", per_guest: "לאורח", per_weight: 'לק"ג', per_item: "ליחידה" };
const CODES = {
  below_minimum: "הכמות נמוכה מהמינימום של המנה",
  dish_unavailable: "המנה הזו כבר לא זמינה",
  order_version_conflict: "ההזמנה עודכנה בחלון אחר. טענו את הדף מחדש",
  invalid_transition: "ההזמנה כבר נשלחה ולא ניתן לשנות אותה",
  validation_error: "הכמות לא תקינה",
  empty_order: "צריך לבחור לפחות מנה אחת",
  items_unavailable: "חלק מהמנות כבר לא זמינות. הסירו אותן מהסיכום ונסו שוב",
  slot_full: "השעה שבחרתם התמלאה בינתיים. בחרו שעה אחרת בפרטי האירוע",
  slot_unavailable: "השעה שבחרתם כבר לא זמינה. בחרו שעה אחרת בפרטי האירוע",
  date_unavailable: "אי אפשר להזמין לתאריך הזה יותר (סגור, או קרוב מדי). עדכנו את פרטי האירוע",
};
const DEBOUNCE_MS = 450;

const $ = (id) => document.getElementById(id);
const state = {
  orderId: null, order: null, dishes: [], categories: [], recs: new Map(),
  category: "", diet: null, editable: false,
};

const money = (v) => new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format(v);
const num = (v) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(v);
const day = (iso) => new Intl.DateTimeFormat("he-IL", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(`${iso}T00:00Z`));
const stepOf = (dish) => (dish.pricing_unit === "per_weight" ? 0.5 : 1);
const quantityOf = (dishId) => Number(state.order.items.find((i) => i.dish_id === dishId)?.quantity ?? 0);

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

let toastTimer;
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3000);
}

function notice(text) {
  $("page-notice").textContent = text;
  $("page-notice").hidden = !text;
}

// --- server changes go through one queue so each request carries the latest version ---
let queue = Promise.resolve();
const pending = new Map(); // dishId -> { timer, run }

function requestQuantity(dish, quantity) {
  clearTimeout(pending.get(dish.id)?.timer);
  const run = () => {
    pending.delete(dish.id);
    queue = queue.then(() => send(dish, quantity)).catch(() => {});
  };
  pending.set(dish.id, { timer: setTimeout(run, DEBOUNCE_MS), run });
}

// Send debounced changes now instead of waiting (before submitting).
function flushPending() {
  for (const { timer, run } of [...pending.values()]) {
    clearTimeout(timer);
    run();
  }
}

async function send(dish, quantity) {
  if (quantity === quantityOf(dish.id)) return;
  const url = `/api/orders/${state.orderId}/items/${dish.id}`;
  try {
    state.order = quantity > 0
      ? await call(url, { method: "PUT", body: JSON.stringify({ quantity: quantity.toFixed(2), version: state.order.version }) })
      : await call(`${url}?version=${state.order.version}`, { method: "DELETE" });
  } catch (err) {
    if (err.status === 401) { location.href = "/customer/"; return; }
    toast(CODES[err.code] ?? "לא הצלחנו לעדכן. נסו שוב");
    if (err.code === "order_version_conflict" || err.code === "invalid_transition") await loadOrder();
    renderDishes(); // put the cards back to what the server has (re-render only here: keeps focus)
  }
  await renderSummary();
}

// --- rendering ---
function badges(d) {
  const k = KASHRUT[d.dietary.kashrut_class];
  const out = [k ? el("span", { className: `badge ${k[1]}`, textContent: k[0] }) : el("span", { className: "badge unknown", textContent: "כשרות: לא ידוע" })];
  if (d.dietary.is_vegan) out.push(el("span", { className: "badge diet", textContent: "טבעוני" }));
  else if (d.dietary.is_vegetarian) out.push(el("span", { className: "badge diet", textContent: "צמחוני" }));
  return el("div", { className: "badges" }, ...out);
}

function allergens(d) {
  const contains = d.allergens.filter((a) => a.status === "contains").map((a) => a.name);
  const free = d.allergens.filter((a) => a.status === "free").map((a) => a.name);
  const lines = [];
  if (contains.length) lines.push(el("p", { textContent: `מכיל: ${contains.join(", ")}` }));
  if (free.length) lines.push(el("p", { textContent: `לא מכיל: ${free.join(", ")}` }));
  lines.push(el("p", { className: "unknown", textContent: contains.length || free.length ? "כל אלרגן אחר: לא ידוע" : "מידע על אלרגנים: לא ידוע" }));
  return el("details", { className: "allergens" }, el("summary", { textContent: "מידע על אלרגנים" }), ...lines);
}

function stepper(d) {
  const current = quantityOf(d.id);
  const input = el("input", { type: "number", inputMode: "decimal", min: 0, step: stepOf(d), value: current, disabled: !state.editable });
  input.setAttribute("aria-label", `כמות ${d.name} (${UNIT[d.pricing_unit]})`);
  const min = Number(d.min_quantity ?? 0);
  const apply = (value) => {
    let v = Math.max(0, Math.round(value / stepOf(d)) * stepOf(d));
    if (v > 0 && v < min) v = value > current ? min : 0; // jump over the forbidden range
    input.value = v;
    input.closest(".dish").classList.toggle("in-order", v > 0);
    requestQuantity(d, v);
  };
  const btn = (delta, text, label) => {
    const b = el("button", { type: "button", className: "step-btn", textContent: text, disabled: !state.editable });
    b.setAttribute("aria-label", `${label} ${d.name}`);
    b.addEventListener("click", () => apply((Number(input.value) || 0) + delta));
    return b;
  };
  input.addEventListener("change", () => apply(Number(input.value) || 0));
  return el("div", { className: "stepper" }, btn(-stepOf(d), "−", "פחות"), input, btn(stepOf(d), "+", "עוד"));
}

function recommendation(d) {
  const r = state.recs.get(d.id);
  if (!r) return null;
  const line = el("span", { className: "rec", textContent: `מומלץ: ${num(r.quantity)} ${UNIT[d.pricing_unit]} ל-${r.eligible_guests} אורחים` });
  if (!state.editable || Number(r.quantity) === quantityOf(d.id)) return line;
  const use = el("button", { type: "button", className: "chip-btn", textContent: "לפי ההמלצה" });
  use.addEventListener("click", () => {
    const input = use.closest(".dish").querySelector(".stepper input");
    input.value = Number(r.quantity);
    input.dispatchEvent(new Event("change"));
  });
  return el("div", { className: "chips" }, line, use);
}

function visible(d) {
  if (state.category && d.category_id !== state.category) return false;
  if (state.diet === "vegan") return d.dietary.is_vegan === true;
  if (state.diet === "vegetarian") return d.dietary.is_vegetarian === true || d.dietary.is_vegan === true;
  return true;
}

function renderDishes() {
  const shown = state.dishes.filter(visible);
  $("no-dishes").hidden = shown.length > 0;
  $("dishes").replaceChildren(...shown.map((d) => {
    const foot = el("div", { className: "dish-foot" }, stepper(d));
    if (d.min_quantity) foot.append(el("span", { className: "help", textContent: `מינימום ${num(d.min_quantity)} ${UNIT[d.pricing_unit]}` }));
    const rec = recommendation(d);
    if (rec) foot.append(rec);
    const body = el("div", { className: "dish-body" },
      el("h3", { textContent: d.name }),
      badges(d),
      d.description ? el("p", { className: "dish-desc", textContent: d.description }) : "",
      el("p", { className: "price num" }, money(d.unit_price), " ", el("span", { textContent: d.unit_label || PER[d.pricing_unit] })),
      allergens(d),
      foot);
    return el("article", { className: `dish${quantityOf(d.id) > 0 ? " in-order" : ""}` }, body);
  }));
}

function renderCategories() {
  const chip = (id, name) => {
    const b = el("button", { type: "button", className: "chip-btn", textContent: name });
    b.setAttribute("aria-pressed", String(state.category === id));
    b.addEventListener("click", () => { state.category = id; renderCategories(); renderDishes(); });
    return b;
  };
  $("categories").replaceChildren(chip("", "הכל"), ...state.categories.map((c) => chip(c.id, c.name)));
}

const fact = (term, value, cls = "") => el("div", { className: cls }, el("dt", { textContent: term }), el("dd", { textContent: value }));

async function renderSummary() {
  const p = await call(`/api/orders/${state.orderId}/pricing`);
  $("no-lines").hidden = p.lines.length > 0;
  $("lines").replaceChildren(...p.lines.map((l) => {
    const name = el("th", { scope: "row", textContent: l.name });
    if (!l.available) {
      name.append(el("span", { className: "help unknown", textContent: "לא זמינה יותר, לא נכללת בסכום" }));
      // It's gone from the menu grid, so this is the only place to take it out of the order.
      if (state.editable) {
        const remove = el("button", { type: "button", className: "btn ghost", textContent: "הסרה מההזמנה" });
        remove.setAttribute("aria-label", `הסרת ${l.name} מההזמנה`);
        remove.addEventListener("click", () => {
          queue = queue.then(() => send({ id: l.dish_id }, 0)).catch(() => {});
        });
        name.append(remove);
      }
    }
    return el("tr", {}, name,
      el("td", { className: "num", textContent: `${num(l.quantity)} ${units(l.quantity, l.pricing_unit)}` }),
      el("td", { className: "num", textContent: money(l.unit_price) }),
      el("td", { className: "num", textContent: money(l.line_total) }));
  }));
  const rows = [fact("ביניים", money(p.subtotal))];
  if (state.order.fulfillment_type === "delivery") {
    rows.push(fact("משלוח", p.delivery_fee === null ? "ייקבע לפי האזור" : money(p.delivery_fee)));
  }
  rows.push(fact('סה"כ כולל מע"מ', money(p.total), "grand"));
  $("totals").replaceChildren(...rows);
  const count = p.lines.filter((l) => l.available).length;
  const dishes = count === 1 ? "מנה אחת" : `${count} מנות`;
  $("submit").disabled = !state.editable || count === 0 || p.lines.some((l) => !l.available);
  $("bar-text").textContent = count ? `${dishes} · ${money(p.total)}` : "עוד לא נבחרו מנות";
}

async function loadOrder() {
  state.order = await call(`/api/orders/${state.orderId}`);
  state.editable = state.order.status === "draft";
  const e = state.order.event;
  $("event-line").textContent = `${e.event_type} · ${day(e.event_date)} · ${e.adults + e.children} אורחים`;
  $("nav-event").href = `/customer/event/?order=${encodeURIComponent(state.orderId)}`;
  notice(state.editable ? "" : "ההזמנה הזו כבר נשלחה, ולכן אי אפשר לשנות את המנות.");
}

async function submit() {
  const button = $("submit");
  const error = $("submit-error");
  button.disabled = true;
  error.hidden = true;
  flushPending();
  try {
    await queue; // every quantity change has reached the server
    await call(`/api/orders/${state.orderId}/submit`, { method: "POST", body: JSON.stringify({ version: state.order.version }) });
    location.href = `/customer/order/?order=${encodeURIComponent(state.orderId)}`;
  } catch (err) {
    if (err.status === 401) { location.href = "/customer/"; return; }
    const names = err.details?.dishes?.length ? ` (${err.details.dishes.join(", ")})` : "";
    error.textContent = (CODES[err.code] ?? "לא הצלחנו לשלוח. נסו שוב") + names;
    error.hidden = false;
    if (err.code === "order_version_conflict") await loadOrder();
    await renderSummary();
  }
}

export async function initMenu() {
  state.orderId = new URLSearchParams(location.search).get("order");
  try {
    if (!(await session())) { location.href = "/customer/"; return; }
  } catch {
    notice("הכניסה ללקוחות עוד לא מוגדרת באתר. נסו שוב מאוחר יותר.");
    return;
  }
  // Only a UUID may reach API paths built from it (no "../" tricks with the customer's token).
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(state.orderId ?? "")) {
    location.href = "/customer/";
    return;
  }
  try {
    await loadOrder();
    const [dishes, categories, recs] = await Promise.all([
      api("/api/catalog/dishes"), api("/api/catalog/categories"),
      call(`/api/orders/${state.orderId}/recommendations`),
    ]);
    state.dishes = dishes;
    state.categories = categories;
    state.recs = new Map(recs.map((r) => [r.dish_id, r]));
  } catch (err) {
    if (err.status === 401) { location.href = "/customer/"; return; }
    notice(err.status === 404 ? "לא מצאנו את ההזמנה הזו." : "לא הצלחנו לטעון את התפריט. נסו שוב.");
    return;
  }
  for (const b of $("diet-filters").querySelectorAll("button")) {
    b.addEventListener("click", () => {
      state.diet = state.diet === b.dataset.diet ? null : b.dataset.diet;
      for (const o of $("diet-filters").querySelectorAll("button")) o.setAttribute("aria-pressed", String(o.dataset.diet === state.diet));
      renderDishes();
    });
  }
  $("submit").addEventListener("click", submit);
  $("edit-event").href = `/customer/event/?order=${encodeURIComponent(state.orderId)}`;
  renderCategories();
  renderDishes();
  await renderSummary();
  $("menu").hidden = false;
}
