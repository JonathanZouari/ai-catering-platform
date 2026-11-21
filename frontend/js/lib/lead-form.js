// "Leave your details" form, used on the landing page and in the menu step.
import { api } from "../api.js";
import { h } from "./dom.js";
import { leadSignals } from "./lead-tracker.js";

const EVENT_TYPES = ["יום הולדת", "אירוע משפחתי", "בר או בת מצווה", "ארוחת שבת", "יום נישואין", "חגיגה פרטית", "אחר"];

function field(id, label, input, hint) {
  return h("div", { class: "field" },
    h("label", { for: id }, label, input.required ? h("span", { class: "req", "aria-hidden": "true", text: " *" }) : null),
    input,
    hint ? h("p", { class: "hint", id: `${id}-hint`, text: hint }) : null);
}

export function createLeadForm({ idPrefix = "lead", eventType = "" } = {}) {
  const id = (name) => `${idPrefix}-${name}`;
  const today = new Date().toISOString().slice(0, 10);
  const name = h("input", { id: id("name"), class: "input", name: "full_name", autocomplete: "name", required: true, minlength: "2", maxlength: "80" });
  const phone = h("input", { id: id("phone"), class: "input", name: "phone", type: "tel", autocomplete: "tel", inputmode: "tel", dir: "ltr", required: true, pattern: "0\\d{1,2}-?\\d{7}", placeholder: "050-1234567" });
  const type = h("select", { id: id("type"), class: "input", name: "event_type", required: true },
    h("option", { value: "", text: "בחרו" }),
    EVENT_TYPES.map((t) => h("option", { value: t, text: t, selected: t === eventType })));
  const guests = h("input", { id: id("guests"), class: "input", name: "guests", type: "number", inputmode: "numeric", min: "1", max: "2000", required: true });
  const date = h("input", { id: id("date"), class: "input", name: "event_date", type: "date", min: today, required: true });
  const budget = h("input", { id: id("budget"), class: "input", name: "budget_per_guest", type: "number", inputmode: "numeric", min: "0", max: "2000", required: true });
  const consent = h("input", { id: id("consent"), type: "checkbox", name: "consent", required: true });
  const status = h("p", { class: "lead-status", role: "status", "aria-live": "polite" });
  const submit = h("button", { class: "btn btn-primary", type: "submit" }, "שליחה");

  const form = h("form", { class: "lead-form", novalidate: false },
    h("div", { class: "lead-grid" },
      field(id("name"), "שם מלא", name),
      field(id("phone"), "טלפון", phone),
      field(id("type"), "סוג האירוע", type),
      field(id("guests"), "מספר אורחים", guests),
      field(id("date"), "תאריך האירוע", date),
      field(id("budget"), "תקציב משוער לאורח (₪)", budget)),
    h("label", { class: "admin-check", for: id("consent") }, consent, "אני מסכים/ה שיחזרו אליי בטלפון לגבי האירוע"),
    submit, status);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!form.reportValidity()) return;
    submit.disabled = true;
    status.textContent = "שולחים...";
    try {
      await api("/api/leads", {
        method: "POST",
        body: JSON.stringify({
          full_name: name.value,
          phone: phone.value.trim(),
          event_type: type.value,
          guests: Number(guests.value),
          event_date: date.value,
          budget_per_guest: Number(budget.value),
          consent: consent.checked,
          ...leadSignals(),
        }),
      });
      form.replaceChildren(h("p", { class: "lead-done", role: "status", text: "תודה! הפרטים התקבלו ונחזור אליכם בהקדם." }));
    } catch {
      status.textContent = "השליחה לא הצליחה. בדקו את הפרטים ונסו שוב.";
      submit.disabled = false;
    }
  });
  return form;
}
