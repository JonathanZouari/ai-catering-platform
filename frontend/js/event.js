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
  profile_required: "קודם משלימים שם וטלפון באזור האישי",
  order_version_conflict: "הטיוטה עודכנה בחלון אחר. טענו את הדף כדי לראות את הגרסה העדכנית",
  invalid_transition: "ההזמנה כבר נשלחה ולא ניתן לערוך אותה",
};
// Server field -> the input to mark and focus.
const FIELD_INPUT = {
  event_type: "other-type", event_date: "event-date", slot_id: "slot", delivery_address: "address",
  ...Object.fromEntries(COUNTERS.map(([key]) => [key, `c-${key}`])),
};

const $ = (id) => document.getElementById(id);
const state = { order: null, blocked: new Set(), slots: [], earliest: null };

// Dates are plain YYYY-MM-DD strings in Israel time; never parsed in the viewer's timezone.
const isoToday = () => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
const addDays = (iso, n) => new Date(Date.parse(`${iso}T00:00Z`) + n * 864e5).toISOString().slice(0, 10);
const weekday = (iso) => new Date(`${iso}T00:00Z`).getUTCDay(); // 0 = Sunday, like the backend
const localTime = (instant) => new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(instant));
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

function renderSlots(selectTime = null) {
  const date = $("event-date").value;
  const select = $("slot");
  const previous = selectTime ?? state.slots.find((s) => s.id === select.value)?.start_time?.slice(0, 5);
  const fitting = date && !state.blocked.has(date)
    ? state.slots
      .filter((s) => s.fulfillment_type === fulfillment() && (s.weekday === null || s.weekday === weekday(date)))
      .sort((a, b) => a.start_time.localeCompare(b.start_time))
    : [];
  select.replaceChildren(el("option", { value: "", textContent: fitting.length ? "בחרו שעה" : "—" }),
    ...fitting.map((s) => el("option", { value: s.id, textContent: `${hhmm(s.start_time)}–${hhmm(s.end_time)}` })));
  const match = fitting.find((s) => hhmm(s.start_time) === previous);
  if (match) select.value = match.id;
  select.disabled = fitting.length === 0;
  $("slot-help").textContent = !date ? "בוחרים קודם תאריך."
    : state.blocked.has(date) ? "התאריך הזה סגור להזמנות."
    : fitting.length ? (fulfillment() === "pickup" ? "שעת האיסוף ביום האירוע." : "חלון המשלוח ביום האירוע.")
    : "אין שעות פנויות ביום הזה. נסו יום אחר או סוג משלוח אחר.";
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
  if (body.fulfillment_type === "delivery" && !body.delivery_address) return ["delivery_address", "צריך כתובת למשלוח"];
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
  $("address-field").hidden = order.fulfillment_type !== "delivery";
  for (const [key] of COUNTERS) $(`c-${key}`).value = e[key];
  $("notes").value = e.dietary_notes ?? "";
  checkDate();
  renderSlots(localTime(order.requested_at));
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
  } catch {
    toast("לא הצלחנו לטעון את השעות הפנויות");
  }
  $("event-date").min = state.earliest;
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
