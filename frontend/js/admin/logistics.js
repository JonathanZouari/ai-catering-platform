// A4/A5: blocked dates, time slots, and delivery zones.
import { adminApi, patchJson, postJson, remove } from "/js/admin/auth.js";
import { attempt, confirmDelete, field, h, numberOrNull, openDialog, select, textOrNull } from "/js/admin/ui.js";

// Matches time_slots.weekday: 0 = Sunday.
const WEEKDAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
const WEEKDAY_OPTIONS = [["", "כל יום"], ...WEEKDAYS.map((day, index) => [String(index), day])];
const TYPES = [["pickup", "איסוף עצמי"], ["delivery", "משלוח"]];

const shortTime = (value) => value.slice(0, 5);

function deleteButton(label, url, refresh) {
  return h("button", {
    className: "secondary danger",
    onclick: () => confirmDelete(label, async () => {
      await remove(url);
      await refresh();
    }),
  }, "מחיקה");
}

export async function renderAvailability(view) {
  const [blocked, slots] = await Promise.all([
    adminApi("/api/admin/blocked-dates"),
    adminApi("/api/admin/time-slots"),
  ]);
  const refresh = () => renderAvailability(view);

  const date = h("input", { type: "date", required: true });
  const reason = h("input", { maxLength: 200 });
  const blockForm = h("form", {
    className: "inline-form",
    onsubmit: async (event) => {
      event.preventDefault();
      await attempt(async () => {
        await postJson("/api/admin/blocked-dates", { date: date.value, reason: textOrNull(reason.value) });
        await refresh();
      });
    },
  }, field("תאריך", date), field("סיבה", reason), h("button", { type: "submit" }, "חסימת תאריך"));

  view.replaceChildren(
    h("h1", {}, "זמינות"),
    h("section", { className: "card" },
      h("header", { className: "screen-header" },
        h("h2", {}, "חלונות זמן"),
        h("button", { onclick: () => openSlotForm(null, refresh) }, "חלון זמן חדש")),
      slots.length
        ? h("ul", { className: "rows" }, slots.map((slot) => h("li", {},
          h("div", {},
            h("strong", {}, TYPES.find(([value]) => value === slot.fulfillment_type)[1]),
            slot.is_active ? null : h("span", { className: "badge" }, "לא פעיל"),
            h("div", { className: "muted" },
              `${slot.weekday === null ? "כל יום" : `יום ${WEEKDAYS[slot.weekday]}`} · `,
              h("bdi", {}, `${shortTime(slot.start_time)}–${shortTime(slot.end_time)}`),
              slot.capacity === null ? "" : ` · עד ${slot.capacity} הזמנות`)),
          h("div", { className: "actions" },
            h("button", { className: "secondary", onclick: () => openSlotForm(slot, refresh) }, "עריכה"),
            deleteButton("חלון הזמן", `/api/admin/time-slots/${slot.id}`, refresh)))))
        : h("p", { className: "empty" }, "עדיין לא הוגדרו חלונות זמן. בלעדיהם לקוחות לא יוכלו לבחור שעה.")),
    h("section", { className: "card" },
      h("h2", {}, "תאריכים חסומים"),
      blockForm,
      blocked.length
        ? h("ul", { className: "rows" }, blocked.map((item) => h("li", {},
          h("div", {}, h("strong", {}, h("bdi", {}, item.date)),
            item.reason ? h("div", { className: "muted" }, item.reason) : null),
          deleteButton(item.date, `/api/admin/blocked-dates/${item.id}`, refresh))))
        : h("p", { className: "empty" }, "אין תאריכים חסומים.")),
  );
}

function openSlotForm(slot, refresh) {
  const type = select(TYPES, slot?.fulfillment_type);
  const weekday = select(WEEKDAY_OPTIONS, slot?.weekday === null || !slot ? "" : String(slot.weekday));
  const start = h("input", { type: "time", required: true, value: slot ? shortTime(slot.start_time) : "" });
  const end = h("input", { type: "time", required: true, value: slot ? shortTime(slot.end_time) : "" });
  const capacity = h("input", { type: "number", min: "0", value: slot?.capacity ?? "" });
  const active = h("input", { type: "checkbox", checked: slot?.is_active ?? true });

  openDialog(slot ? "עריכת חלון זמן" : "חלון זמן חדש", [
    field("סוג", type),
    field("יום", weekday),
    h("div", { className: "grid" }, field("משעה", start), field("עד שעה", end)),
    field("מקסימום הזמנות", capacity, "ריק = ללא הגבלה"),
    slot ? field("פעיל", active) : null,
  ], async () => {
    const data = {
      fulfillment_type: type.value,
      weekday: numberOrNull(weekday.value),
      start_time: start.value,
      end_time: end.value,
      capacity: numberOrNull(capacity.value),
    };
    if (slot) await patchJson(`/api/admin/time-slots/${slot.id}`, { ...data, is_active: active.checked });
    else await postJson("/api/admin/time-slots", data);
    await refresh();
  });
}

export async function renderDelivery(view) {
  const zones = await adminApi("/api/admin/delivery-zones");
  const refresh = () => renderDelivery(view);

  view.replaceChildren(
    h("header", { className: "screen-header" },
      h("h1", {}, "אזורי משלוח"),
      h("button", { onclick: () => openZoneForm(null, refresh) }, "אזור חדש")),
    h("section", { className: "card" },
      zones.length
        ? h("ul", { className: "rows" }, zones.map((zone) => h("li", {},
          h("div", {},
            h("strong", {}, zone.name),
            zone.is_active ? null : h("span", { className: "badge" }, "לא פעיל"),
            h("div", { className: "muted" }, h("bdi", {}, `₪${zone.fee}`), ` · ${zone.cities.join(", ")}`)),
          h("div", { className: "actions" },
            h("button", { className: "secondary", onclick: () => openZoneForm(zone, refresh) }, "עריכה"),
            deleteButton(zone.name, `/api/admin/delivery-zones/${zone.id}`, refresh)))))
        : h("p", { className: "empty" }, "עדיין לא הוגדרו אזורי משלוח.")),
  );
}

function openZoneForm(zone, refresh) {
  const name = h("input", { required: true, maxLength: 120, value: zone?.name ?? "" });
  const fee = h("input", { type: "number", min: "0", step: "0.01", required: true, value: zone?.fee ?? "" });
  const cities = h("textarea", { rows: 3, required: true, value: zone?.cities.join("\n") ?? "" });
  const active = h("input", { type: "checkbox", checked: zone?.is_active ?? true });

  openDialog(zone ? "עריכת אזור" : "אזור חדש", [
    field("שם האזור", name),
    field("דמי משלוח בש״ח", fee),
    field("ערים", cities, "עיר אחת בכל שורה"),
    zone ? field("פעיל", active) : null,
  ], async () => {
    const data = {
      name: name.value.trim(),
      fee: fee.value,
      cities: cities.value.split("\n").map((city) => city.trim()).filter(Boolean),
    };
    if (zone) await patchJson(`/api/admin/delivery-zones/${zone.id}`, { ...data, is_active: active.checked });
    else await postJson("/api/admin/delivery-zones", data);
    await refresh();
  });
}
