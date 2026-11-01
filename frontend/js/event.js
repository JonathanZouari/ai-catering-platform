// Event details form (C1). Saves to sessionStorage and continues to the menu. No pricing or capacity rules here:
// blocked dates (OPEN #5), the veg/vegan subset rule (OPEN #4) and delivery zones (OPEN #19) are not decided yet.
import { h } from "./dom.js";
import { reducedMotion } from "./format.js";
import { createStepper } from "./components/stepper.js";
import { loadEvent, saveEvent } from "./event-store.js";

const form = document.getElementById("event-form");
const saved = loadEvent() ?? {};
const values = { adults: saved.adults ?? 20, children: saved.children ?? 0, vegetarians: saved.vegetarians ?? 0, vegans: saved.vegans ?? 0 };

const COUNTERS = [
  { key: "adults", label: "מבוגרים", hint: "" },
  { key: "children", label: "ילדים", hint: "עד גיל 12" },
  { key: "vegetarians", label: "מתוכם צמחונים", hint: "נספרים בתוך הסך הכולל" },
  { key: "vegans", label: "מתוכם טבעונים", hint: "נספרים בתוך הסך הכולל" },
];

const countEl = document.getElementById("guest-count");
const wordEl = document.getElementById("guest-word");
let shown = null;
let frame = 0;

function showGuests(total) {
  countEl.textContent = Math.round(total);
  wordEl.textContent = Math.round(total) === 1 ? "אורח" : "אורחים";
}

// The number on the CTA counts to its new value (380 ms, ease-out).
function rollGuests(to) {
  cancelAnimationFrame(frame);
  const from = shown ?? to;
  shown = to;
  if (reducedMotion() || from === to) return showGuests(to);
  const t0 = performance.now();
  const tick = (now) => {
    const p = Math.min(1, (now - t0) / 380);
    showGuests(from + (to - from) * (1 - (1 - p) ** 3));
    if (p < 1) frame = requestAnimationFrame(tick);
  };
  frame = requestAnimationFrame(tick);
}

const guests = () => values.adults + values.children;

document.getElementById("counters").append(...COUNTERS.map(({ key, label, hint }) => {
  const stepper = createStepper({
    label, value: values[key], min: 0, max: 999,
    onChange: (next) => { values[key] = next; stepper.set(next); rollGuests(guests()); },
  });
  return h("div", { class: "counter" },
    h("div", { class: "counter__label" }, h("strong", {}, label), hint ? h("span", {}, hint) : null),
    stepper.el);
}));
shown = guests();
showGuests(shown);

// Prefill (e.g. coming back from the menu) and sensible bounds.
const field = (name) => form.elements[name];
const today = new Date().toLocaleDateString("sv-SE");
field("date").min = today;
if (saved.date) field("date").value = saved.date;
if (saved.time) field("time").value = saved.time;
if (saved.address) field("address").value = saved.address;
if (saved.type) field("type").value = saved.type;
if (saved.mode) form.querySelector(`input[name="mode"][value="${saved.mode}"]`).checked = true;

const addressField = document.getElementById("address-field");
const syncMode = () => { addressField.hidden = field("mode").value !== "delivery"; };
form.addEventListener("change", (e) => { if (e.target.name === "mode") syncMode(); });
syncMode();

const errorEl = document.getElementById("form-error");
function fail(input, message) {
  for (const el of form.querySelectorAll("[aria-invalid]")) el.removeAttribute("aria-invalid");
  input?.setAttribute("aria-invalid", "true");
  errorEl.textContent = message;
  input?.focus();
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  errorEl.textContent = "";
  const mode = field("mode").value;
  if (!field("date").value) return fail(field("date"), "יש לבחור תאריך לאירוע.");
  if (field("date").value < today) return fail(field("date"), "התאריך שנבחר כבר עבר.");
  if (!field("time").value) return fail(field("time"), "יש לבחור שעת הגעה או איסוף.");
  if (guests() < 1) return fail(null, "יש להזין לפחות אורח אחד.");
  if (mode === "delivery" && !field("address").value.trim()) return fail(field("address"), "יש להזין כתובת למשלוח.");

  saveEvent({
    date: field("date").value, time: field("time").value, ...values, mode,
    address: mode === "delivery" ? field("address").value.trim() : "", type: field("type").value,
  });
  location.href = "/customer/";
});
