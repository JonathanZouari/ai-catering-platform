// Screens C2 (dish selection) and C3 (summary). Quantities are only requests: the backend checks
// steps, minimums and availability, and computes every price (ADR 0003). Text via textContent only.
import { api } from "/js/api.js";
import { initAssistant } from "/js/assistant.js";
import { call, session } from "/js/customer-session.js";
import { hydrateIllustrations } from "/js/illustrations.js";

const KASHRUT = { meat: ["בשרי", "k-meat"], pareve: ["פרווה", "k-parve"] }; // no dairy (OPEN #9)
const UNIT = { per_tray: "מגשים", per_guest: "מנות", per_weight: 'ק"ג', per_item: "יחידות" };
const UNIT_ONE = { per_tray: "מגש", per_guest: "מנה", per_weight: 'ק"ג', per_item: "יחידה" };
// per-guest lines read "for N guests": the unit is a guest, whether food or a place setting
const qtyText = (q, unit) => unit === "per_guest" ? (Number(q) === 1 ? "לאורח אחד" : `ל-${num(q)} אורחים`)
  : `${num(q)} ${(Number(q) === 1 ? UNIT_ONE : UNIT)[unit] ?? ""}`;
const PER = { per_tray: "למגש", per_guest: "לאורח", per_weight: 'לק"ג', per_item: "ליחידה" };
const CODES = {
  below_minimum: "הכמות נמוכה מהמינימום של המנה",
  dish_unavailable: "המנה הזו כבר לא זמינה",
  order_version_conflict: "ההזמנה עודכנה בחלון אחר. טענו את הדף מחדש",
  invalid_transition: "ההזמנה כבר נשלחה ולא ניתן לשנות אותה",
  validation_error: "הכמות לא תקינה",
  empty_order: "צריך לבחור לפחות מנה אחת",
  age_confirmation_required: "ההזמנה כוללת אלכוהול: סמנו שאתם מעל גיל 18",
  items_unavailable: "חלק מהמנות כבר לא זמינות. הסירו אותן מהסיכום ונסו שוב",
  slot_full: "השעה שבחרתם התמלאה בינתיים. בחרו שעה אחרת בפרטי האירוע",
  city_not_served: "אין כרגע משלוחים לעיר שבחרתם. עדכנו את פרטי האירוע (עיר אחרת או איסוף עצמי)",
  slot_unavailable: "השעה שבחרתם כבר לא זמינה. בחרו שעה אחרת בפרטי האירוע",
  date_unavailable: "אי אפשר להזמין לתאריך הזה יותר (סגור, או קרוב מדי). עדכנו את פרטי האירוע",
};
const DEBOUNCE_MS = 450;

const $ = (id) => document.getElementById(id);
const state = {
  orderId: null, order: null, dishes: [], categories: [], recs: new Map(),
  category: "", diet: null, editable: false,
  want: new Map(), // dishId -> quantity asked for but not yet confirmed by the server
};
// shortcut: placeholder art by category position (matches the seeded menu order); add a
// per-category icon field if the owner reorders categories.
const CATEGORY_ART = ["olive", "grill", "pot", "lemon", "plate", "basket", "glass"];

const money = (v) => new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format(v);
const num = (v) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(v);
const day = (iso) => new Intl.DateTimeFormat("he-IL", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(`${iso}T00:00Z`));
const stepOf = (dish) => (dish.pricing_unit === "per_weight" ? 0.5 : 1);
const quantityOf = (dishId) => Number(state.order.items.find((i) => i.dish_id === dishId)?.quantity ?? 0);
const qty = (dishId) => state.want.get(dishId) ?? quantityOf(dishId); // what the customer sees

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
  const settle = () => { if (state.want.get(dish.id) === quantity) state.want.delete(dish.id); };
  if (quantity === quantityOf(dish.id)) { settle(); return; }
  const url = `/api/orders/${state.orderId}/items/${dish.id}`;
  try {
    state.order = quantity > 0
      ? await call(url, { method: "PUT", body: JSON.stringify({ quantity: quantity.toFixed(2), version: state.order.version }) })
      : await call(`${url}?version=${state.order.version}`, { method: "DELETE" });
    settle();
  } catch (err) {
    if (err.status === 401) { location.href = "/customer/"; return; }
    toast(CODES[err.code] ?? "לא הצלחנו לעדכן. נסו שוב");
    state.want.delete(dish.id);
    if (err.code === "order_version_conflict" || err.code === "invalid_transition") await loadOrder();
    keepFocus(() => { renderDishes(); renderSide(); }); // back to what the server has
  }
  await renderSummary();
}

// The customer asks for a quantity: normalise it to the dish's step and minimum, show it at
// once everywhere, and queue the request (the server stays the authority, ADR 0003).
function setQuantity(d, value) {
  const current = qty(d.id);
  let v = Math.max(0, Math.round(value / stepOf(d)) * stepOf(d));
  const min = Number(d.min_quantity ?? 0);
  if (v > 0 && v < min) v = value > current ? min : 0; // jump over the forbidden range
  state.want.set(d.id, v);
  requestQuantity(d, v);
  keepFocus(() => { syncCard(d); renderSide(); });
}

// First amount when a dish lands on the table: the recommendation, else the smallest allowed.
const startQuantity = (d) => Number(state.recs.get(d.id)?.quantity) || Math.max(Number(d.min_quantity ?? 0), stepOf(d));

function addToTable(d) {
  const current = qty(d.id);
  setQuantity(d, current > 0 ? current + stepOf(d) : startQuantity(d));
  toast(`${current > 0 ? "עוד" : "נוסף לשולחן"}: ${d.name} (${qtyText(qty(d.id), d.pricing_unit)})`);
  const tray = $("tray");
  tray.classList.remove("bump");
  void tray.offsetWidth; // restart the animation
  tray.classList.add("bump");
}

// Re-rendering replaces buttons; put focus back on the same control (data-key), or on the
// control that took its place when a dish crossed zero.
function keepFocus(render) {
  const key = document.activeElement?.dataset?.key;
  render();
  if (!key || document.activeElement?.dataset?.key === key) return;
  const id = key.split(":")[1];
  const find = (k) => document.querySelector(`[data-key="${CSS.escape(k)}"]`);
  (find(key) ?? find(`inc:${id}`) ?? find(`add:${id}`) ?? $("tray-toggle"))?.focus();
}

// --- rendering ---
function badges(d) {
  const k = KASHRUT[d.dietary.kashrut_class]; // null = not food (disposables): no food badges
  const out = k ? [el("span", { className: `badge ${k[1]}`, textContent: k[0] })] : [];
  if (!k) { /* not food */ } else if (d.dietary.is_vegan) out.push(el("span", { className: "badge diet", textContent: "טבעוני" }));
  else if (d.dietary.is_vegetarian) out.push(el("span", { className: "badge diet", textContent: "צמחוני" }));
  if (d.contains_alcohol) out.push(el("span", { className: "badge diet", textContent: "אלכוהול 18+" }));
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

function stepper(d, prefix = "") {
  const input = el("input", { type: "number", inputMode: "decimal", min: 0, step: stepOf(d), value: qty(d.id), disabled: !state.editable });
  input.dataset.key = `${prefix}qty:${d.id}`;
  input.setAttribute("aria-label", `כמות ${d.name} (${UNIT[d.pricing_unit]})`);
  const btn = (delta, text, label, kind) => {
    const b = el("button", { type: "button", className: "step-btn", textContent: text, disabled: !state.editable });
    b.dataset.key = `${prefix}${kind}:${d.id}`;
    b.setAttribute("aria-label", `${label} ${d.name}`);
    b.addEventListener("click", () => setQuantity(d, qty(d.id) + delta));
    return b;
  };
  input.addEventListener("change", () => setQuantity(d, Number(input.value) || 0));
  return el("div", { className: "stepper" }, btn(-stepOf(d), "−", "פחות", "dec"), input, btn(stepOf(d), "+", "עוד", "inc"));
}

function recommendation(d) {
  const r = state.recs.get(d.id);
  if (!r) return null;
  const line = el("span", { className: "rec", textContent: `מומלץ: ${num(r.quantity)} ${UNIT[d.pricing_unit]} ל-${r.eligible_guests} אורחים` });
  if (!state.editable || Number(r.quantity) === qty(d.id)) return line;
  const use = el("button", { type: "button", className: "chip-btn", textContent: "לפי ההמלצה" });
  use.addEventListener("click", () => setQuantity(d, Number(r.quantity)));
  return el("div", { className: "chips" }, line, use);
}

function visible(d) {
  if (state.category && d.category_id !== state.category) return false;
  if (d.dietary.kashrut_class === null) return true; // not food: diet filters don't apply
  if (state.diet === "vegan") return d.dietary.is_vegan === true;
  if (state.diet === "vegetarian") return d.dietary.is_vegetarian === true || d.dietary.is_vegan === true;
  return true;
}

// --- drag to the table: Pointer Events, so mouse and touch share one path. On touch a long
// press starts the drag, so a normal swipe still scrolls. Buttons are the keyboard equivalent.
const LONG_PRESS_MS = 300;
const overTray = (ev) => {
  const r = $("tray").getBoundingClientRect();
  return ev.clientX >= r.left && ev.clientX <= r.right && ev.clientY >= r.top && ev.clientY <= r.bottom;
};

function draggable(node, label, onDrop) {
  node.addEventListener("contextmenu", (e) => { if (document.documentElement.classList.contains("dragging")) e.preventDefault(); });
  node.addEventListener("pointerdown", (e) => {
    if (!state.editable || !e.isPrimary || e.button !== 0) return;
    if (e.target.closest("button, input, a, summary, label, select")) return;
    const touch = e.pointerType !== "mouse";
    const start = { x: e.clientX, y: e.clientY };
    let ghost = null;
    let last = e;
    const place = (ev) => {
      ghost.style.translate = `${ev.clientX}px ${ev.clientY}px`;
      $("tray").classList.toggle("drop-hot", overTray(ev));
    };
    const begin = () => {
      ghost = el("div", { className: "drag-ghost", textContent: label });
      ghost.setAttribute("aria-hidden", "true");
      document.body.append(ghost);
      document.documentElement.classList.add("dragging");
      node.classList.add("drag-src");
      place(last);
    };
    const timer = touch ? setTimeout(begin, LONG_PRESS_MS) : 0;
    const move = (ev) => {
      last = ev;
      if (ghost) return place(ev);
      if (Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 8) return;
      if (touch) stop(); // moved before the long press: that's a scroll, not a drag
      else begin();
    };
    const blockScroll = (ev) => { if (ghost) ev.preventDefault(); };
    function stop(ev) {
      clearTimeout(timer);
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", stop);
      removeEventListener("pointercancel", stop);
      removeEventListener("touchmove", blockScroll);
      if (!ghost) return;
      ghost.remove();
      document.documentElement.classList.remove("dragging");
      node.classList.remove("drag-src");
      $("tray").classList.remove("drop-hot");
      if (ev?.type === "pointerup") onDrop(overTray(ev));
    }
    addEventListener("pointermove", move);
    addEventListener("pointerup", stop);
    addEventListener("pointercancel", stop);
    addEventListener("touchmove", blockScroll, { passive: false });
  });
}

// --- rendering ---
function media(d) {
  if (/^\/assets\/img\/[\w-]+\.(jpg|png|webp)$/.test(d.image_path ?? "")) { // only our own photos
    const img = el("img", { src: d.image_path, alt: "", loading: "lazy", width: 400, height: 300, draggable: false });
    return el("div", { className: "dish-media" }, img);
  }
  const art = document.createElement("i");
  art.dataset.ill = CATEGORY_ART[state.categories.findIndex((c) => c.id === d.category_id)] ?? "plate";
  return el("div", { className: "dish-media no-photo in" }, art); // "in": drawn, no draw-in per card
}

function cardFoot(d) {
  const foot = el("div", { className: "dish-foot" });
  if (qty(d.id) > 0 || !state.editable) foot.append(stepper(d));
  else {
    const add = el("button", { type: "button", className: "btn ghost add-btn", textContent: "+ לשולחן" });
    add.dataset.key = `add:${d.id}`;
    add.setAttribute("aria-label", `הוספת ${d.name} לשולחן`);
    add.addEventListener("click", () => addToTable(d));
    foot.append(add);
  }
  if (d.min_quantity) foot.append(el("span", { className: "help", textContent: `מינימום ${num(d.min_quantity)} ${UNIT[d.pricing_unit]}` }));
  const rec = recommendation(d);
  if (rec) foot.append(rec);
  return foot;
}

function card(d) {
  const body = el("div", { className: "dish-body" },
    el("h4", { textContent: d.name }),
    badges(d),
    d.description ? el("p", { className: "dish-desc", textContent: d.description }) : "",
    el("p", { className: "price num" }, money(d.unit_price), " ", el("span", { textContent: d.unit_label || PER[d.pricing_unit] })),
    allergens(d),
    cardFoot(d));
  const node = el("article", { className: `dish${qty(d.id) > 0 ? " in-order" : ""}` }, media(d), body);
  node.dataset.dish = d.id;
  draggable(node, d.name, (onTray) => { if (onTray) addToTable(d); });
  return node;
}

function syncCard(d) {
  const node = document.querySelector(`.dish[data-dish="${CSS.escape(d.id)}"]`);
  if (!node) return;
  node.classList.toggle("in-order", qty(d.id) > 0);
  node.querySelector(".dish-foot").replaceWith(cardFoot(d));
}

function renderDishes() {
  const shown = state.dishes.filter(visible);
  $("no-dishes").hidden = shown.length > 0;
  // "All" reads as a menu: one titled section per category, in the owner's order.
  const groups = state.category ? [[null, shown]]
    : state.categories.map((c) => [c, shown.filter((d) => d.category_id === c.id)]).filter(([, ds]) => ds.length);
  $("dishes").replaceChildren(...groups.map(([c, ds]) => el("section", { className: "dish-group" },
    c ? el("h3", { className: "group-h", textContent: c.name }) : "",
    el("div", { className: "dish-grid" }, ...ds.map(card)))));
  hydrateIllustrations($("dishes"));
}

function trayItem(d) {
  const remove = el("button", { type: "button", className: "tray-del", textContent: "✕" });
  remove.dataset.key = `tdel:${d.id}`;
  remove.setAttribute("aria-label", `הסרת ${d.name} מהשולחן`);
  remove.addEventListener("click", () => { setQuantity(d, 0); toast(`הוסר מהשולחן: ${d.name}`); });
  const item = el("li", { className: "tray-item" },
    el("span", { className: "tray-name" }, d.name, el("small", { textContent: qtyText(qty(d.id), d.pricing_unit) })),
    stepper(d, "t"), remove);
  // dragging an item off the table takes it out of the order
  draggable(item, d.name, (onTray) => { if (!onTray) { setQuantity(d, 0); toast(`הוסר מהשולחן: ${d.name}`); } });
  return item;
}

// The table panel and the per-category counters.
function renderSide() {
  const chosen = state.dishes.filter((d) => qty(d.id) > 0);
  const names = new Map(state.categories.map((c) => [c.id, c.name]));
  const ids = new Set([...names.keys(), ...chosen.map((d) => d.category_id)]);
  $("tray-list").replaceChildren(...[...ids].map((id) => {
    const ds = chosen.filter((d) => d.category_id === id);
    return ds.length ? el("div", { className: "tray-group" }, el("h4", { textContent: names.get(id) ?? "אחר" }), el("ul", {}, ...ds.map(trayItem))) : "";
  }), chosen.length ? "" : el("p", { className: "empty", textContent: "השולחן עוד ריק. גררו לכאן מנות." }));
  renderCategories();
}

function renderCategories() {
  const chosen = state.dishes.filter((d) => qty(d.id) > 0);
  const chip = (id, name) => {
    const count = chosen.filter((d) => !id || d.category_id === id).length;
    const b = el("button", { type: "button", className: "chip-btn", textContent: name });
    if (count) b.append(el("span", { className: "chip-count", textContent: String(count) }));
    b.dataset.key = `cat:${id}`;
    b.setAttribute("aria-label", count ? `${name}, ${count} נבחרו` : name);
    b.setAttribute("aria-pressed", String(state.category === id));
    b.addEventListener("click", () => { state.category = id; keepFocus(() => { renderCategories(); renderDishes(); }); });
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
      el("td", { className: "num", textContent: qtyText(l.quantity, l.pricing_unit) }),
      el("td", { className: "num", textContent: money(l.unit_price) }),
      el("td", { className: "num", textContent: money(l.line_total) }));
  }));
  const rows = [fact("ביניים", money(p.subtotal))];
  if (state.order.fulfillment_type === "delivery") {
    rows.push(fact("משלוח", p.delivery_fee === null ? "אין משלוח לעיר שנבחרה" : money(p.delivery_fee)));
  }
  rows.push(fact('סה"כ כולל מע"מ', money(p.total), "grand"));
  $("totals").replaceChildren(...rows);
  const count = p.lines.filter((l) => l.available).length;
  const dishes = count === 1 ? "מנה אחת" : `${count} מנות`;
  const alcohol = new Set(state.dishes.filter((d) => d.contains_alcohol).map((d) => d.id));
  $("adult-wrap").hidden = !state.editable || !p.lines.some((l) => l.available && alcohol.has(l.dish_id));
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
    await call(`/api/orders/${state.orderId}/submit`, { method: "POST", body: JSON.stringify({ version: state.order.version, adult_confirmed: $("adult").checked }) });
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
    const [dishes, categories, recs, business] = await Promise.all([
      api("/api/catalog/dishes"), api("/api/catalog/categories"),
      call(`/api/orders/${state.orderId}/recommendations`), api("/api/catalog/business"),
    ]);
    const cert = business.kashrut_certificate;
    $("kashrut-line").textContent = `המטבח כשר${cert ? ` (${cert})` : ""}: מנות בשריות ופרווה בלבד, בלי חלבי.`;
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
  $("tray-toggle").addEventListener("click", () => {
    const open = $("tray-toggle").getAttribute("aria-expanded") !== "true";
    $("tray-toggle").setAttribute("aria-expanded", String(open));
    $("tray-list").hidden = !open;
  });
  $("tray").addEventListener("animationend", () => $("tray").classList.remove("bump"));
  renderSide();
  renderDishes();
  await renderSummary();
  $("menu").hidden = false;
  if (state.editable) {
    initAssistant(state.orderId, {
      beforeAnswer: async () => { flushPending(); await queue; }, // own edits land first
      afterAccept: async () => { await loadOrder(); renderSide(); renderDishes(); await renderSummary(); },
    });
  }
}
