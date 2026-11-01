// Portions per guest, used for the quantities customers are recommended.
import { adminApi, putJson, remove } from "/js/admin/auth.js";
import { attempt, field, h } from "/js/ui.js";

const TYPES = {
  salad: "סלטים",
  main: "מנות עיקריות",
  side: "תוספות",
  dessert: "קינוחים",
  drink: "שתייה",
  other: "אחר",
};

function ruleForm(rule, view) {
  const label = TYPES[rule.category_type];
  const number = (value) => h("input", {
    type: "number", min: "0", max: "99", step: "0.05", required: true, value: Number(value),
  });
  const adult = number(rule.portions_per_adult);
  const child = number(rule.portions_per_child);
  const url = `/api/admin/quantity-rules/${rule.category_type}`;
  return h("form", {
    className: "inline-form",
    "aria-label": label,
    onsubmit: async (event) => {
      event.preventDefault();
      await attempt(async () => {
        await putJson(url, { portions_per_adult: adult.value, portions_per_child: child.value });
        await renderQuantities(view);
      }, "הכמויות נשמרו");
    },
  },
  h("h3", {}, label, rule.is_default ? h("span", { className: "badge" }, "ברירת מחדל") : null),
  field(`מנות למבוגר: ${label}`, adult),
  field(`מנות לילד: ${label}`, child),
  h("div", { className: "actions" },
    h("button", { type: "submit" }, "שמירה"),
    rule.is_default ? null : h("button", {
      type: "button",
      className: "secondary",
      onclick: () => attempt(async () => {
        await remove(url);
        await renderQuantities(view);
      }, "חזרנו לברירת המחדל"),
    }, "חזרה לברירת המחדל")));
}

export async function renderQuantities(view) {
  const rules = await adminApi("/api/admin/quantity-rules");
  view.replaceChildren(
    h("h1", {}, "כמויות מומלצות"),
    h("section", { className: "card" },
      h("p", { className: "muted" }, "כמה מנות אדם מכל סוג מומלץ לכל סועד. ברירות המחדל הן הערכה ראשונית שטרם אומתה. בדקו שהן מתאימות לעסק."),
      rules.map((rule) => ruleForm(rule, view))),
  );
}
