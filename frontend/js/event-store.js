// Event details from the C1 form, kept in sessionStorage until the API and customer auth exist (OPEN #1).
// Shape: { date: "YYYY-MM-DD", time: "HH:MM", adults, children, vegetarians, vegans, mode: "delivery" | "pickup", address, type }.
const KEY = "catering.event";

export function saveEvent(event) {
  try { sessionStorage.setItem(KEY, JSON.stringify(event)); } catch { /* storage unavailable: carry on without it */ }
}

export function loadEvent() {
  try { return JSON.parse(sessionStorage.getItem(KEY)); } catch { return null; }
}

// One-line description for the menu page header. Also accepts the mock EVENT, which has dateLabel/guests/mode text.
export function describeEvent(event) {
  const guests = event.guests ?? event.adults + event.children;
  const date = event.dateLabel ?? new Date(`${event.date}T00:00`).toLocaleDateString("he-IL", { weekday: "long", day: "numeric", month: "long" });
  const mode = event.mode === "delivery" ? "משלוח" : event.mode === "pickup" ? "איסוף" : event.mode;
  const adults = event.adults === 1 ? "מבוגר אחד" : `${event.adults} מבוגרים`;
  const children = event.children === 1 ? "ילד אחד" : `${event.children} ילדים`;
  return `${date} · ${event.time} · ${guests === 1 ? "אורח אחד" : `${guests} אורחים`} (${adults}, ${children}) · ${mode}`;
}
