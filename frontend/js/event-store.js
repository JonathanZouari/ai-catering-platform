// Event details, the draft order and the submitted quote, kept in sessionStorage until the API and customer
// auth exist (OPEN #1). All of it is demo state: nothing here reaches a server.
//   event:      { date: "YYYY-MM-DD", time: "HH:MM", adults, children, vegetarians, vegans, mode: "delivery" | "pickup", address, type }
//   order:      { [dishId]: quantity }
//   submission: { event, address, notes, lines: [{ id, name, qty, unit, price }], total, status: "pending_approval", submittedAt }
const KEYS = { event: "catering.event", order: "catering.order", submission: "catering.submission" };

const read = (key) => { try { return JSON.parse(sessionStorage.getItem(key)); } catch { return null; } };
const write = (key, value) => { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable: carry on without it */ } };

export const saveEvent = (event) => write(KEYS.event, event);
export const loadEvent = () => read(KEYS.event);
export const saveOrder = (order) => write(KEYS.order, order);
export const loadOrder = () => read(KEYS.order);
export const saveSubmission = (submission) => write(KEYS.submission, submission);
export const loadSubmission = () => read(KEYS.submission);

// Display-ready facts. Also accepts the mock EVENT (which carries dateLabel / guests / mode text).
export function eventFacts(event) {
  const guests = event.guests ?? event.adults + event.children;
  const date = event.dateLabel ?? new Date(`${event.date}T00:00`).toLocaleDateString("he-IL", { weekday: "long", day: "numeric", month: "long" });
  const mode = event.mode === "delivery" ? "משלוח" : event.mode === "pickup" ? "איסוף" : event.mode;
  const adults = event.adults === 1 ? "מבוגר אחד" : `${event.adults} מבוגרים`;
  const children = event.children === 1 ? "ילד אחד" : `${event.children} ילדים`;
  return {
    date, time: event.time, mode, isDelivery: mode === "משלוח", address: event.address ?? "",
    guests: guests === 1 ? "אורח אחד" : `${guests} אורחים`, guestsDetail: `${adults}, ${children}`,
  };
}

// One-line description for the menu page header.
export function describeEvent(event) {
  const f = eventFacts(event);
  return `${f.date} · ${f.time} · ${f.guests} (${f.guestsDetail}) · ${f.mode}`;
}
