import { readEvent, totalFor } from "./proposal.js";

const RING = 2 * Math.PI * 69;
const $ = (id) => document.getElementById(id);

let stored = null;
try {
  stored = sessionStorage.getItem("event");
} catch {
  // Storage can be blocked; readEvent falls back to the sample event.
}
const event = readEvent(stored);
let status = event.vegans > 0 ? "pending" : "approved";

const COPY = {
  pending: ["עוד מנות, ושלא יחסר.", "כמעט סיימנו. נשאר לבחור מנות לאורחים הטבעונים."],
  approved: ["כולם מסודרים.", "הכול מוכן להמשך."],
  rejected: ["בסדר גמור.", "ההזמנה נשארה כמו שהייתה."],
};

function render() {
  const added = status === "approved";
  const seated = added ? event.guests : event.guests - event.vegans;
  const [headline, subline] = COPY[status];
  const total = totalFor(event, added).toLocaleString("he-IL");

  $("strip").textContent = `${event.name} / ${event.guests} אורחים`;
  $("headline").textContent = status === "pending" ? `עוד ${event.vegans} מנות, ושלא יחסר.` : headline;
  $("subline").textContent = status === "approved" && event.vegans > 0 ? "המנות נוספו והמחיר עודכן." : subline;
  $("seated").textContent = seated;
  $("of").textContent = `מתוך ${event.guests}`;
  $("seat-plate").setAttribute("aria-label", `${seated} מתוך ${event.guests} אורחים מסודרים`);
  $("ring").style.strokeDasharray = `${(RING * seated) / event.guests} ${RING}`;
  $("ring").style.stroke = added ? "#6e9a7a" : "#a9c7b0";
  const extra = (totalFor(event, true) - totalFor(event, false)).toLocaleString("he-IL");
  $("add").textContent = `הוספת ${event.vegans} מנות טבעוניות · ₪${extra}+`;
  $("propose").hidden = status !== "pending";
  $("back").hidden = status === "pending" || event.vegans === 0;
  $("total").textContent = `₪${total}`;
  $("nav-total").textContent = `₪${total}`;
}

const set = (next) => () => {
  status = next;
  render();
};
$("add").addEventListener("click", set("approved"));
$("skip").addEventListener("click", set("rejected"));
$("back").addEventListener("click", set("pending"));

render();
