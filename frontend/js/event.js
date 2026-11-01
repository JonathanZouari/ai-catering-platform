import { MAX_GUESTS, missingField, setGuests, setKids, setVegans, setVegetarians } from "./guests.js";

const EVENTS = [
  { name: "שבת חתן", cloth: "cloth-butter" },
  { name: "בר/בת מצווה", cloth: "cloth-sky" },
  { name: "יום הולדת", cloth: "cloth-peach" },
  { name: "חגיגה משפחתית", cloth: "cloth-sage" },
];
const RING = 2 * Math.PI * 69;

const $ = (id) => document.getElementById(id);
const today = new Date().toLocaleDateString("en-CA");

let state = { event: 0, guests: 50, kids: 0, vegetarians: 0, vegans: 0, date: "", delivery: false, address: "" };

// The address stays in memory only: personal data is not kept in the browser.
function save() {
  const { event, guests, kids, vegetarians, vegans } = state;
  try {
    sessionStorage.setItem("event", JSON.stringify({ name: EVENTS[event].name, guests, kids, vegetarians, vegans }));
  } catch {
    // Storage can be blocked; the next screen falls back to its sample event.
  }
}

function dateText() {
  if (!state.date) return "בחירת תאריך";
  return new Date(`${state.date}T00:00`).toLocaleDateString("he-IL", { day: "numeric", month: "long" });
}

function render() {
  const { event, guests, kids, vegetarians, vegans, delivery, date } = state;
  const adults = guests - kids;

  $("cloth").className = `cloth ${EVENTS[event].cloth}`;
  document.querySelectorAll("[data-event]").forEach((b) => {
    b.setAttribute("aria-pressed", String(Number(b.dataset.event) === event));
  });

  $("field-event").textContent = EVENTS[event].name;
  $("field-guests").textContent = guests;
  $("field-date").textContent = dateText();
  $("field-supply").textContent = delivery ? "תביאו אלינו" : "נאסוף בעצמנו";

  const rows = { guests: [guests, 1, MAX_GUESTS], kids: [kids, 0, guests], vegetarians: [vegetarians, 0, guests - vegans], vegans: [vegans, 0, guests - vegetarians] };
  for (const [key, [value, min, max]] of Object.entries(rows)) {
    $(`count-${key}`).textContent = value;
    document.querySelector(`[data-step="${key}"][data-by^="-"]`).disabled = value <= min;
    document.querySelector(`[data-step="${key}"]:not([data-by^="-"])`).disabled = value >= max;
  }

  $("date-past").hidden = !date || date >= today;
  $("pick-pickup").setAttribute("aria-pressed", String(!delivery));
  $("pick-delivery").setAttribute("aria-pressed", String(delivery));
  $("address-field").hidden = !delivery;

  $("plate-count").textContent = guests;
  $("plate").setAttribute("aria-label", `${guests} אורחים: ${adults} מבוגרים ו-${kids} ילדים`);
  const adultLen = (RING * adults) / guests;
  $("ring-adults").style.strokeDasharray = `${adultLen} ${RING}`;
  $("ring-kids").style.strokeDasharray = `${(RING * kids) / guests} ${RING}`;
  $("ring-kids").style.strokeDashoffset = -adultLen;

  $("note-event").textContent = EVENTS[event].name;
  $("note-date").textContent = date ? dateText() : "עוד לא נבחר";
  $("note-adults").textContent = adults;
  $("note-kids").textContent = kids;
  $("note-vegetarians").textContent = vegetarians;
  $("note-vegans").textContent = vegans;
  $("note-supply").textContent = delivery ? "משלוח" : "איסוף עצמי";

  const missing = missingField(state, today);
  $("continue").hidden = !!missing;
  $("missing").hidden = !missing;
  $("missing").textContent = missing;
  save();
}

const update = (next) => {
  state = next;
  render();
};

document.querySelectorAll("[data-panel]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-panel]").forEach((b) => {
      const open = b === button;
      b.setAttribute("aria-expanded", String(open));
      $(b.dataset.panel).hidden = !open;
    });
  });
});

document.querySelectorAll("[data-event]").forEach((b) => {
  b.addEventListener("click", () => update({ ...state, event: Number(b.dataset.event) }));
});

const steppers = { guests: setGuests, kids: setKids, vegetarians: setVegetarians, vegans: setVegans };
document.querySelectorAll("[data-step]").forEach((b) => {
  b.addEventListener("click", () => {
    const key = b.dataset.step;
    update(steppers[key](state, state[key] + Number(b.dataset.by)));
  });
});

$("date").min = today;
$("date").addEventListener("input", (e) => update({ ...state, date: e.target.value }));
$("pick-pickup").addEventListener("click", () => update({ ...state, delivery: false }));
$("pick-delivery").addEventListener("click", () => update({ ...state, delivery: true }));
$("address").addEventListener("input", (e) => update({ ...state, address: e.target.value }));

render();
