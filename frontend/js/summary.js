// Summary & quote (C3). Reads the event details and the draft order from sessionStorage (mock until the API exists).
// Sending only records a price snapshot locally and shows the confirmation: no payment, no VAT, no coverage block.
import { h } from "./dom.js";
import { ils } from "./format.js";
import { EVENT, UNITS, dishById } from "./mock/menu.js";
import { loadEvent, loadOrder, loadSubmission, saveSubmission, eventFacts } from "./event-store.js";
import { statusPill } from "./components/status-pill.js";

const $ = (id) => document.getElementById(id);
const event = loadEvent() ?? EVENT; // the menu falls back to the same demo event
const currentOrder = loadOrder() ?? {};
const quantities = (entries) => JSON.stringify(entries.filter(([, q]) => q > 0).sort(([a], [b]) => (a < b ? -1 : 1)));

// A sent quote is only shown while it still matches the current event and order. After a new event or a changed
// order this is a new draft, not the old quote with old (e.g. delivery) details.
const stored = loadSubmission();
const submission = stored && JSON.stringify(stored.event) === JSON.stringify(event)
  && quantities(stored.lines.map((l) => [l.id, l.qty])) === quantities(Object.entries(currentOrder)) ? stored : null;
const facts = eventFacts(event);

// Lines: from the sent snapshot if there is one, otherwise from the current order at current mock prices.
const lines = submission?.lines ?? Object.entries(currentOrder)
  .filter(([id, qty]) => qty > 0 && dishById(id))
  .map(([id, qty]) => { const d = dishById(id); return { id, name: d.name, qty, unit: d.unit, price: d.price }; });
const total = lines.reduce((sum, l) => sum + l.price * l.qty, 0);

function renderFacts(address = "") {
  const fact = (label, value, detail) => h("div", {}, h("dt", {}, label), h("dd", {}, value, detail ? h("small", {}, detail) : null));
  $("facts").replaceChildren(
    fact("תאריך", facts.date),
    fact("שעה", facts.time),
    fact("אורחים", facts.guests, facts.guestsDetail),
    fact(facts.isDelivery ? "משלוח" : "קבלה", facts.isDelivery ? (address || "כתובת תוזן למטה") : facts.mode),
  );
}

function renderLines() {
  $("lines").replaceChildren(...lines.map((l) => {
    const unit = UNITS[l.unit];
    return h("li", {},
      h("span", { class: "quote__name" }, l.name),
      h("span", { class: "quote__calc num" }, `${l.qty} ${l.qty === 1 ? unit.one : unit.many} × ${ils(l.price)}`),
      h("span", { class: "quote__line num" }, ils(l.price * l.qty)));
  }));
  $("total").textContent = ils(total);
  $("delivery-row").hidden = !facts.isDelivery;
  $("sum-label").textContent = facts.isDelivery ? "סה״כ (ללא משלוח)" : "סה״כ"; // pickup has no delivery wording
}

function showSent(sent) {
  $("status-slot").replaceChildren(statusPill("pending")); // "ממתין לאישור", never shown as confirmed
  $("send-form").hidden = true;
  $("confirmation").hidden = false;
  renderFacts(sent.address);
  // Screen readers get the confirmation; sighted visitors land on the top of the page with the new status pill.
  $("confirmation").focus({ preventScroll: true });
  scrollTo(0, 0);
}

if (!lines.length) {
  $("status-slot").replaceChildren(statusPill("draft", "טיוטה · עוד לא נשלחה"));
  $("quote").hidden = true;
  $("send-form").hidden = true;
  $("empty").hidden = false;
} else if (submission) {
  renderLines();
  showSent(submission);
} else {
  $("status-slot").replaceChildren(statusPill("draft", "טיוטה · עוד לא נשלחה"));
  renderFacts(event.address);
  renderLines();
  $("address-field").hidden = !facts.isDelivery;
  $("address").value = event.address ?? "";

  $("send-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const address = $("address").value.trim();
    if (facts.isDelivery && !address) {
      $("address").setAttribute("aria-invalid", "true");
      $("form-error").textContent = "יש להזין כתובת למשלוח.";
      $("address").focus();
      return;
    }
    // Price snapshot at submission (PRD: later catalog changes must not affect it).
    const sent = { event, address: facts.isDelivery ? address : "", notes: $("notes").value.trim(), lines, total, status: "pending_approval", submittedAt: new Date().toISOString() };
    saveSubmission(sent);
    showSent(sent);
  });
}
