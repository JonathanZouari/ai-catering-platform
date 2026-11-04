// Owner screens A4 (blocked dates, order rules) and A5 (time slots, delivery zones).
// All server data is written with textContent / input values only (never innerHTML).
import { $, call, confirmThen, el, mutate, startAdmin } from "/js/admin-common.js";

const TYPES = { pickup: "איסוף", delivery: "משלוח" };
// 0 = Sunday, same as the backend and Date.getDay(); "" = every day.
const DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
const ERRORS = {
  conflict: "התאריך או שם האזור כבר קיימים",
  city_taken: "אחת הערים כבר שייכת לאזור אחר",
};
// "תל אביב-יפו, רמת גן" -> ["תל אביב-יפו", "רמת גן"]; the server trims and dedupes as well.
const cityList = (text) => text.split(/[,،\n]/).map((c) => c.trim()).filter(Boolean);

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
  const [blocked, slots, settings, zones] = await Promise.all([
    call("/api/admin/blocked-dates"), call("/api/admin/time-slots"), call("/api/admin/settings"),
    call("/api/admin/delivery-zones"),
  ]);
  renderBlocked(blocked);
  renderSlots(slots);
  renderZones(zones);
  $("lead-days").value = settings.lead_days;
  $("child-portion").value = Number(settings.child_portion);
  $("assistant-limit").value = settings.assistant_daily_limit;
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

function renderZones(zones) {
  $("no-zones").hidden = zones.length > 0;
  $("zone-rows").replaceChildren(...zones.map((z) => {
    const name = labelled(el("input", { value: z.name, maxLength: 60, required: true }), `שם האזור ${z.name}`);
    const fee = labelled(el("input", { type: "number", min: 0, max: 10000, step: "0.01", value: z.fee, className: "num" }), `דמי משלוח, ${z.name}`);
    fee.style.inlineSize = "7em";
    const cities = labelled(el("input", { value: z.cities.join(", ") }), `ערים, ${z.name}`);
    cities.style.minInlineSize = "16em";
    const active = labelled(el("input", { type: "checkbox", checked: z.is_active }), `פעיל, ${z.name}`);
    const save = el("button", { type: "button", className: "btn ghost", textContent: "שמירה" });
    save.onclick = () => mutate(() => call(`/api/admin/delivery-zones/${z.id}`, {
      method: "PATCH",
      body: JSON.stringify({ name: name.value.trim(), fee: Number(fee.value).toFixed(2), cities: cityList(cities.value), is_active: active.checked }),
    }), "האזור נשמר");
    const del = el("button", { type: "button", className: "btn danger", textContent: "מחיקה" });
    del.onclick = () => confirmThen(del, () => mutate(() => call(`/api/admin/delivery-zones/${z.id}`, { method: "DELETE" }), "האזור נמחק"));
    return el("tr", {}, el("td", {}, name), el("td", {}, fee), el("td", {}, cities), el("td", {}, active), el("td", {}, save, " ", del));
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

  $("zone-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const [name, fee, cities] = [$("z-name"), $("z-fee"), $("z-cities")];
    const bad = [name, fee, cities].filter((i) => !i.checkValidity() || !i.value.trim());
    for (const i of [name, fee, cities]) i.setAttribute("aria-invalid", String(bad.includes(i)));
    if (bad.length) { bad[0].reportValidity(); return; }
    mutate(() => call("/api/admin/delivery-zones", {
      method: "POST",
      body: JSON.stringify({ name: name.value.trim(), fee: Number(fee.value).toFixed(2), cities: cityList(cities.value) }),
    }), "האזור נוסף").then((ok) => { if (ok) { name.value = ""; fee.value = ""; cities.value = ""; } });
  });

  $("settings-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const lead = $("lead-days");
    const child = $("child-portion");
    const limit = $("assistant-limit");
    const fields = [lead, child, limit];
    const bad = fields.filter((i) => !i.checkValidity() || i.value === "");
    for (const i of fields) i.setAttribute("aria-invalid", String(bad.includes(i)));
    if (bad.length) { bad[0].reportValidity(); return; }
    mutate(() => call("/api/admin/settings", {
      method: "PUT",
      body: JSON.stringify({
        lead_days: Number(lead.value), child_portion: Number(child.value).toFixed(2),
        assistant_daily_limit: Number(limit.value),
      }),
    }), "הכללים נשמרו");
  });

  startAdmin({ content: "availability", load, errors: ERRORS });
}
