// Screen C1: event configuration -> draft order. The browser only helps the customer pick valid
// values; every rule is enforced again by the backend (ADR 0003). Text goes in via textContent.
import { api } from "/js/api.js";
import { call, session } from "/js/customer-session.js";

const TZ = "Asia/Jerusalem";
const EVENT_TYPES = ["בר / בת מצווה", "ברית", "חתונה", "אירוסין", "יום הולדת", "אירוע חברה", "שבת"];
const OTHER = "__other__";
const COUNTERS = [
  ["adults", "מבוגרים", ""],
  ["children", "ילדים", ""],
  ["vegetarian_guests", "צמחונים", "מתוך סך האורחים"],
  ["vegan_guests", "טבעונים", "מתוך סך האורחים"],
  ["restricted_guests", "עם הגבלות תזונה אחרות", "מתוך סך האורחים"],
];
const SUBSETS = ["vegetarian_guests", "vegan_guests", "restricted_guests"];
const CODES = {
  date_unavailable: "אי אפשר להזמין לתאריך הזה (סגור, או קרוב מדי). בחרו תאריך אחר",
  slot_unavailable: "השעה הזו כבר לא פנויה ביום הזה. בחרו שעה אחרת",
  slot_full: "השעה הזו כבר מלאה ביום הזה. בחרו שעה אחרת",
  city_not_served: "אין לנו משלוחים לעיר הזו. בחרו עיר מהרשימה או איסוף עצמי",
  profile_required: "קודם משלימים שם וטלפון באזור האישי",
  order_version_conflict: "הטיוטה עודכנה בחלון אחר. טענו את הדף כדי לראות את הגרסה העדכנית",
  invalid_transition: "ההזמנה כבר נשלחה ולא ניתן לערוך אותה",
};
// Server field -> the input to mark and focus.
const FIELD_INPUT = {
  event_type: "other-type", event_date: "event-date", slot_id: "slot", delivery_address: "address", delivery_city: "city",
  ...Object.fromEntries(COUNTERS.map(([key]) => [key, `c-${key}`])),
};

const $ = (id) => document.getElementById(id);
// cities: the served ones with fees; places: those plus every other Israeli locality (fee null).
const state = { order: null, blocked: new Set(), slots: [], earliest: null, full: new Set(), cities: [], places: [] };
const MAX_SUGGESTIONS = 50;

// Dates are plain YYYY-MM-DD strings in Israel time; never parsed in the viewer's timezone.
const isoToday = () => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
const addDays = (iso, n) => new Date(Date.parse(`${iso}T00:00Z`) + n * 864e5).toISOString().slice(0, 10);
const weekday = (iso) => new Date(`${iso}T00:00Z`).getUTCDay(); // 0 = Sunday, like the backend
const hhmm = (t) => t.slice(0, 5);
const shortDate = (iso) => new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(`${iso}T00:00Z`));
const tooSoon = () => `צריך להזמין מראש. התאריך הכי מוקדם: ${shortDate(state.earliest)}`;

let toastTimer;
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

function buildTypes() {
  const chip = (value, label) => {
    const input = el("input", { type: "radio", name: "event-type", value });
    input.addEventListener("change", () => { $("other-type-field").hidden = value !== OTHER; });
    return el("label", { className: "chip" }, input, el("span", { textContent: label }));
  };
  $("event-types").replaceChildren(...EVENT_TYPES.map((t) => chip(t, t)), chip(OTHER, "אחר"));
}

function buildCounters() {
  $("counters").replaceChildren(...COUNTERS.map(([key, label, help]) => {
    const input = el("input", { id: `c-${key}`, type: "number", inputMode: "numeric", min: 0, max: 5000, value: 0 });
    const step = (delta, text, name) => {
      const b = el("button", { type: "button", className: "step-btn", textContent: text });
      b.setAttribute("aria-label", `${name} ${label}`);
      b.addEventListener("click", () => {
        input.value = Math.min(5000, Math.max(0, (Number(input.value) || 0) + delta));
        input.dispatchEvent(new Event("input"));
      });
      return b;
    };
    const text = el("div", { className: "counter-text" }, el("label", { className: "counter-label", htmlFor: input.id, textContent: label }));
    if (help) text.append(el("span", { className: "help", textContent: help }));
    return el("div", { className: "counter" }, text, el("div", { className: "stepper" }, step(-1, "−", "פחות"), input, step(1, "+", "עוד")));
  }));
}

const fulfillment = () => document.querySelector('input[name="fulfillment"]:checked').value;

// Keeps the chosen slot when date or type changes: same slot id, else same start time.
function renderSlots(selectId = null) {
  const date = $("event-date").value;
  const select = $("slot");
  const wanted = selectId ?? select.value;
  const previous = state.slots.find((s) => s.id === wanted)?.start_time?.slice(0, 5);
  const isFull = (s) => state.full.has(`${s.id}|${date}`);
  const fitting = date && !state.blocked.has(date)
    ? state.slots
      .filter((s) => s.fulfillment_type === fulfillment() && (s.weekday === null || s.weekday === weekday(date)))
      .sort((a, b) => a.start_time.localeCompare(b.start_time))
    : [];
  select.replaceChildren(el("option", { value: "", textContent: fitting.length ? "בחרו שעה" : "—" }),
    ...fitting.map((s) => el("option", {
      value: s.id, disabled: isFull(s),
      textContent: `${hhmm(s.start_time)}–${hhmm(s.end_time)}${isFull(s) ? " · מלא" : ""}`,
    })));
  const open = fitting.filter((s) => !isFull(s));
  const match = open.find((s) => s.id === wanted) ?? open.find((s) => hhmm(s.start_time) === previous);
  if (match) select.value = match.id;
  select.disabled = fitting.length === 0;
  $("slot-help").textContent = !date ? "בוחרים קודם תאריך."
    : state.blocked.has(date) ? "התאריך הזה סגור להזמנות."
    : !open.length && fitting.length ? "כל השעות ביום הזה מלאות. נסו יום אחר."
    : fitting.length ? (fulfillment() === "pickup" ? "שעת האיסוף ביום האירוע." : "חלון המשלוח ביום האירוע.")
    : "אין שעות פנויות ביום הזה. נסו יום אחר או סוג משלוח אחר.";
}

const money = (v) => new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format(v);

// City autocomplete: spaces, hyphens and quote marks don't matter ("תל אביב" finds "תל אביב-יפו").
const norm = (s) => s.replace(/[-־'"׳״]/g, " ").replace(/\s+/g, " ").trim();
// For comparing names only: also ignores doubled yod/vav, so the CBS "קרית אונו" is the zone's "קריית אונו".
const key = (s) => norm(s).replace(/יי/g, "י").replace(/וו/g, "ו");

// Served cities first, then every other locality from /data/cities.json that isn't one of them.
function mergePlaces(served, names) {
  const seen = new Set(served.map((c) => key(c.city)));
  return [...served, ...names.filter((n) => !seen.has(key(n))).map((city) => ({ city, fee: null }))];
}

async function loadPlaces() {
  try {
    const res = await fetch("/data/cities.json");
    if (res.ok) return await res.json();
  } catch { /* the served cities alone still work */ }
  return [];
}

function cityMatches(query) {
  const q = key(query);
  if (!q) return state.cities;
  // Exact name first, then served cities, then names that start with the text, then a later word.
  const rank = (c) => (key(c.city) === q ? 0 : c.fee !== null ? 1 : key(c.city).startsWith(q) ? 2 : 3);
  return state.places.filter((c) => key(c.city).split(" ").some((_, i, w) => w.slice(i).join(" ").startsWith(q)))
    .sort((a, b) => rank(a) - rank(b))
    .slice(0, MAX_SUGGESTIONS);
}

// The locality the text means: an exact name, or the only one it is the start of. A served city
// wins over a CBS spelling of it, because mergePlaces dropped that spelling.
function resolveCity(text) {
  const q = key(text);
  if (!q) return null;
  const exact = state.places.find((c) => key(c.city) === q);
  if (exact) return exact.city;
  const starts = state.places.filter((c) => key(c.city).startsWith(q));
  return starts.length === 1 ? starts[0].city : null;
}

function renderCities(selected = $("city").value) {
  $("city").value = selected ?? ""; // a city no longer served stays, and the help says so
  showFee();
}

function showFee() {
  const text = $("city").value;
  const city = state.cities.find((c) => c.city === text);
  const known = !city && norm(text) && state.places.find((c) => key(c.city) === key(text));
  $("city-help").textContent = city ? `דמי משלוח: ${money(city.fee)}`
    : known ? "לעיר הזו אין כרגע משלוחים. אפשר לבחור איסוף עצמי."
    : norm(text) && !cityMatches(text).length ? "לא מצאנו יישוב בשם הזה." : "משלוחים רק לערים שמופיע לידן מחיר.";
}

function initCityCombo() {
  const input = $("city");
  const list = $("city-list");
  let shown = [];
  let active = -1;
  const options = () => [...list.children];
  const highlight = (i) => {
    active = i;
    options().forEach((li, j) => li.setAttribute("aria-selected", String(j === i)));
    if (i < 0) { input.removeAttribute("aria-activedescendant"); return; }
    input.setAttribute("aria-activedescendant", options()[i].id);
    options()[i].scrollIntoView({ block: "nearest" });
  };
  const close = () => {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    highlight(-1);
  };
  const open = () => {
    shown = cityMatches(input.value);
    const q = norm(input.value);
    list.replaceChildren(...shown.map((c, i) => {
      const at = q ? norm(c.city).indexOf(q) : -1; // norm keeps the length, so offsets line up
      const name = at < 0 ? el("span", { textContent: c.city })
        : el("span", {}, c.city.slice(0, at), el("mark", { textContent: c.city.slice(at, at + q.length) }), c.city.slice(at + q.length));
      const li = el("li", { id: `city-opt-${i}` }, name, el("span", { className: "combo-fee", textContent: c.fee === null ? "אין משלוח" : money(c.fee) }));
      li.setAttribute("role", "option");
      return li;
    }));
    list.hidden = shown.length === 0;
    input.setAttribute("aria-expanded", String(shown.length > 0));
    highlight(shown.length === 1 && q ? 0 : -1);
  };
  const pick = (c) => {
    input.value = c.city;
    input.removeAttribute("aria-invalid");
    close();
    showFee();
  };
  input.addEventListener("focus", open);
  input.addEventListener("input", () => { open(); showFee(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (list.hidden) open();
      if (!shown.length) return;
      const n = shown.length;
      highlight(e.key === "ArrowDown" ? (active + 1) % n : (active <= 0 ? n - 1 : active - 1));
    } else if (e.key === "Enter" && !list.hidden && active >= 0) {
      e.preventDefault(); // pick, don't submit the form
      pick(shown[active]);
    } else if (e.key === "Escape" && !list.hidden) {
      e.preventDefault();
      close();
    }
  });
  list.addEventListener("mousedown", (e) => e.preventDefault()); // keep focus in the input
  list.addEventListener("click", (e) => {
    const li = e.target.closest('[role="option"]');
    if (li) pick(shown[options().indexOf(li)]);
  });
  input.addEventListener("blur", () => {
    close();
    const city = resolveCity(input.value);
    if (city) input.value = city;
    showFee();
  });
}

function checkDate() {
  const date = $("event-date").value;
  const help = $("date-help");
  const problem = !date ? "" : date < state.earliest ? tooSoon() : state.blocked.has(date) ? "אנחנו לא מקבלים הזמנות לתאריך הזה" : "";
  help.textContent = problem;
  help.hidden = !problem;
  $("event-date").setAttribute("aria-invalid", String(Boolean(problem)));
  renderSlots();
}

function onFulfillment() {
  $("address-field").hidden = fulfillment() !== "delivery";
  renderSlots();
}

function eventType() {
  const picked = document.querySelector('input[name="event-type"]:checked')?.value;
  return picked === OTHER ? $("other-type").value.trim() : picked ?? "";
}

function readForm() {
  const counts = Object.fromEntries(COUNTERS.map(([key]) => [key, Number($(`c-${key}`).value) || 0]));
  return {
    event: { event_type: eventType(), event_date: $("event-date").value, ...counts, dietary_notes: $("notes").value.trim() || null },
    fulfillment_type: fulfillment(),
    slot_id: $("slot").value,
    delivery_address: fulfillment() === "delivery" ? $("address").value.trim() || null : null,
    delivery_city: fulfillment() === "delivery" ? resolveCity($("city").value) ?? ($("city").value.trim() || null) : null,
  };
}

// Same rules as the backend, only to give feedback before the round trip.
function clientProblem(body) {
  const e = body.event;
  const guests = e.adults + e.children;
  if (e.event_type.length < 2) return ["event_type", "בחרו סוג אירוע"];
  if (!e.event_date) return ["event_date", "בחרו תאריך"];
  if (e.event_date < state.earliest) return ["event_date", tooSoon()];
  if (state.blocked.has(e.event_date)) return ["event_date", CODES.date_unavailable];
  if (!body.slot_id) return ["slot_id", "בחרו שעה"];
  if (guests === 0) return ["adults", "צריך לפחות אורח אחד"];
  const over = SUBSETS.find((k) => e[k] > guests);
  if (over) return [over, `לא יכול להיות יותר מסך האורחים (${guests})`];
  if (e.vegetarian_guests + e.vegan_guests > guests) return ["vegan_guests", `צמחונים וטבעונים יחד לא יכולים לעבור את סך האורחים (${guests})`];
  if (body.fulfillment_type === "delivery" && !body.delivery_city) return ["delivery_city", "בחרו עיר למשלוח"];
  if (body.fulfillment_type === "delivery" && !state.cities.some((c) => c.city === body.delivery_city)) {
    return ["delivery_city", CODES.city_not_served];
  }
  if (body.fulfillment_type === "delivery" && !body.delivery_address) return ["delivery_address", "צריך רחוב ומספר למשלוח"];
  return null;
}

function showProblem(field, message) {
  for (const id of Object.values(FIELD_INPUT)) $(id)?.removeAttribute("aria-invalid");
  $("form-error").textContent = message;
  $("form-error").hidden = !message;
  const target = field === "event_type" && $("other-type-field").hidden
    ? document.querySelector('input[name="event-type"]') : $(FIELD_INPUT[field]);
  if (target) {
    target.setAttribute("aria-invalid", "true");
    target.focus();
  }
}

function fill(order) {
  const e = order.event;
  const known = EVENT_TYPES.includes(e.event_type);
  const radio = document.querySelector(`input[name="event-type"][value="${known ? CSS.escape(e.event_type) : OTHER}"]`);
  radio.checked = true;
  $("other-type-field").hidden = known;
  $("other-type").value = known ? "" : e.event_type;
  $("event-date").value = e.event_date;
  document.querySelector(`input[name="fulfillment"][value="${order.fulfillment_type}"]`).checked = true;
  $("address").value = order.delivery_address ?? "";
  renderCities(order.delivery_city);
  $("address-field").hidden = order.fulfillment_type !== "delivery";
  for (const [key] of COUNTERS) $(`c-${key}`).value = e[key];
  $("notes").value = e.dietary_notes ?? "";
  checkDate();
  renderSlots(order.slot_id);
}

function setOrder(order) {
  state.order = order;
  const editable = order.status === "draft";
  $("event-form").querySelectorAll("input, select, textarea, button[type=submit], .step-btn").forEach((n) => { n.disabled = !editable; });
  if (!editable) {
    $("blocked-notice").textContent = "ההזמנה הזו כבר נשלחה, ולכן אי אפשר לערוך אותה.";
    $("blocked-notice").hidden = false;
  }
  $("title").textContent = `תכנון האירוע: ${order.event.event_type}`;
  $("to-menu").href = `/customer/menu/?order=${encodeURIComponent(order.id)}`;
  $("next-step").hidden = !editable;
}

async function save(e) {
  e.preventDefault();
  const body = readForm();
  const problem = clientProblem(body);
  if (problem) { showProblem(...problem); return; }
  showProblem(null, "");
  $("save").disabled = true;
  try {
    const order = state.order
      ? await call(`/api/orders/${state.order.id}`, { method: "PATCH", body: JSON.stringify({ ...body, version: state.order.version }) })
      : await call("/api/orders", { method: "POST", body: JSON.stringify(body) });
    setOrder(order);
    history.replaceState(null, "", `/customer/event/?order=${encodeURIComponent(order.id)}`);
    toast("הטיוטה נשמרה");
  } catch (err) {
    if (err.status === 401) { location.href = "/customer/"; return; }
    showProblem(err.details?.field ?? null, CODES[err.code] ?? "בדקו את הפרטים ונסו שוב");
  } finally {
    if (!state.order || state.order.status === "draft") $("save").disabled = false;
  }
}

export async function initEvent() {
  try {
    if (!(await session())) { location.href = "/customer/"; return; }
  } catch {
    $("blocked-notice").textContent = "הכניסה ללקוחות עוד לא מוגדרת באתר. נסו שוב מאוחר יותר.";
    $("blocked-notice").hidden = false;
    return;
  }
  buildTypes();
  buildCounters();
  const today = isoToday();
  state.earliest = today;
  try {
    const availability = await api(`/api/availability?from=${today}&to=${addDays(today, 365)}`);
    state.blocked = new Set(availability.blocked_dates);
    state.slots = availability.time_slots;
    state.earliest = availability.earliest_date;
    state.full = new Set(availability.full_slots.map((f) => `${f.slot_id}|${f.date}`));
    state.cities = await api("/api/delivery/cities");
  } catch {
    toast("לא הצלחנו לטעון את השעות הפנויות");
  }
  state.places = mergePlaces(state.cities, await loadPlaces());
  $("event-date").min = state.earliest;
  renderCities();
  if (!state.cities.length) {  // no zones yet: delivery can't be chosen
    $("delivery-option").disabled = true;
    $("delivery-option").closest("label").title = "אין כרגע משלוחים";
  }
  initCityCombo();
  $("event-date").addEventListener("change", checkDate);
  for (const r of document.querySelectorAll('input[name="fulfillment"]')) r.addEventListener("change", onFulfillment);
  $("event-form").addEventListener("submit", save);
  for (const id of Object.values(FIELD_INPUT)) $(id)?.addEventListener("input", () => $(id).removeAttribute("aria-invalid"));

  const id = new URLSearchParams(location.search).get("order");
  if (id) {
    try {
      const order = await call(`/api/orders/${encodeURIComponent(id)}`);
      fill(order);
      setOrder(order);
    } catch (err) {
      if (err.status === 401) { location.href = "/customer/"; return; }
      $("blocked-notice").textContent = "לא מצאנו את ההזמנה הזו. אפשר להתחיל תכנון חדש.";
      $("blocked-notice").hidden = false;
      history.replaceState(null, "", "/customer/event/");
    }
  }
  renderSlots();
  $("event-form").hidden = false;
}
