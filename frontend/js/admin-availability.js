// Owner screens A4 (blocked dates) and A5 (pickup/delivery time slots).
// All server data is written with textContent / input values only (never innerHTML).
import { $, call, confirmThen, el, mutate, startAdmin } from "/js/admin-common.js";

const TYPES = { pickup: "איסוף", delivery: "משלוח" };
// 0 = Sunday, same as the backend and Date.getDay(); "" = every day.
const DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
const ERRORS = { conflict: "התאריך הזה כבר חסום" };

const hhmm = (t) => t.slice(0, 5);
const longDate = (iso) => {
  try { return new Intl.DateTimeFormat("he-IL", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date(`${iso}T00:00`)); }
  catch { return iso; }
};

function options(select, entries) {
  select.replaceChildren(...entries.map(([value, label]) => el("option", { value, textContent: label })));
}
const typeOptions = () => Object.entries(TYPES);
const dayOptions = () => [["", "כל יום"], ...DAYS.map((d, i) => [String(i), d])];

async function load() {
  const [blocked, slots] = await Promise.all([call("/api/admin/blocked-dates"), call("/api/admin/time-slots")]);
  renderBlocked(blocked);
  renderSlots(slots);
}

function renderBlocked(blocked) {
  $("no-blocked").hidden = blocked.length > 0;
  $("blocked-rows").replaceChildren(...blocked.map((b) => {
    const del = el("button", { type: "button", className: "btn danger", textContent: "ביטול חסימה" });
    del.setAttribute("aria-label", `ביטול החסימה של ${longDate(b.date)}`);
    del.onclick = () => confirmThen(del, () => mutate(() => call(`/api/admin/blocked-dates/${b.id}`, { method: "DELETE" }), "החסימה בוטלה"));
    return el("tr", {},
      el("th", { scope: "row" }, el("time", { dateTime: b.date, textContent: longDate(b.date) })),
      el("td", { textContent: b.reason ?? "" }),
      el("td", {}, del));
  }));
}

function labelled(node, label) {
  node.setAttribute("aria-label", label);
  return node;
}

function renderSlots(slots) {
  $("no-slots").hidden = slots.length > 0;
  $("slot-rows").replaceChildren(...slots.map((t) => {
    const name = `${TYPES[t.fulfillment_type]} ${t.weekday === null ? "כל יום" : DAYS[t.weekday]} ${hhmm(t.start_time)}`;
    const type = labelled(el("select"), `סוג, ${name}`);
    options(type, typeOptions());
    type.value = t.fulfillment_type;
    const day = labelled(el("select"), `יום, ${name}`);
    options(day, dayOptions());
    day.value = t.weekday === null ? "" : String(t.weekday);
    const start = labelled(el("input", { type: "time", value: hhmm(t.start_time), required: true }), `משעה, ${name}`);
    const end = labelled(el("input", { type: "time", value: hhmm(t.end_time), required: true }), `עד שעה, ${name}`);
    const cap = labelled(el("input", { type: "number", min: 1, max: 10000, value: t.capacity ?? "", className: "num" }), `קיבולת, ${name}`);
    cap.style.inlineSize = "6em";
    const active = labelled(el("input", { type: "checkbox", checked: t.is_active }), `פעיל, ${name}`);
    const save = el("button", { type: "button", className: "btn ghost", textContent: "שמירה" });
    save.onclick = () => mutate(() => call(`/api/admin/time-slots/${t.id}`, {
      method: "PATCH", body: JSON.stringify({ ...slotBody(type, day, start, end, cap), is_active: active.checked }),
    }), "החלון נשמר");
    const del = el("button", { type: "button", className: "btn danger", textContent: "מחיקה" });
    del.onclick = () => confirmThen(del, () => mutate(() => call(`/api/admin/time-slots/${t.id}`, { method: "DELETE" }), "החלון נמחק"));
    return el("tr", {}, el("td", {}, type), el("td", {}, day), el("td", {}, start), el("td", {}, end),
      el("td", {}, cap), el("td", {}, active), el("td", {}, save, " ", del));
  }));
}

function slotBody(type, day, start, end, cap) {
  return {
    fulfillment_type: type.value,
    weekday: day.value === "" ? null : Number(day.value),
    start_time: start.value,
    end_time: end.value,
    capacity: cap.value === "" ? null : Number(cap.value),
  };
}

export function initAvailability() {
  options($("s-type"), typeOptions());
  options($("s-day"), dayOptions());

  $("blocked-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const date = $("b-date");
    const reason = $("b-reason");
    mutate(() => call("/api/admin/blocked-dates", {
      method: "POST", body: JSON.stringify({ date: date.value, reason: reason.value.trim() || null }),
    }), "התאריך נחסם").then((ok) => { if (ok) { date.value = ""; reason.value = ""; } });
  });

  $("slot-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const [start, end, cap] = [$("s-start"), $("s-end"), $("s-cap")];
    if (end.value <= start.value) {
      end.setCustomValidity("שעת הסיום צריכה להיות אחרי שעת ההתחלה");
      end.reportValidity();
      end.addEventListener("input", () => end.setCustomValidity(""), { once: true });
      return;
    }
    mutate(() => call("/api/admin/time-slots", {
      method: "POST", body: JSON.stringify(slotBody($("s-type"), $("s-day"), start, end, cap)),
    }), "החלון נוסף").then((ok) => { if (ok) { start.value = ""; end.value = ""; cap.value = ""; } });
  });

  startAdmin({ content: "availability", load, errors: ERRORS });
}
