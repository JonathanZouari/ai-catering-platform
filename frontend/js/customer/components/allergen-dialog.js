import { fill, h, icon } from "../../lib/dom.js";
import { allergenSummary } from "../allergens.js";

let dialog;

// Disclaimer wording is a placeholder until OPEN_DECISIONS #8 is answered by the business.
const DISCLAIMER = "המידע מוזן על ידי העסק. במקרה של אלרגיה חמורה מומלץ לוודא ישירות מול העסק לפני האירוע.";

export function showAllergenInfo(dish) {
  if (!dialog) {
    dialog = h("dialog", { class: "dialog", "aria-labelledby": "allergen-title" });
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
    document.body.append(dialog);
  }

  const info = allergenSummary(dish);
  const body = h("div", {},
    info.contains.length ? h("p", {text: `מכיל: ${info.contains.join(", ")}`}) : null,
    info.free.length ? h("p", {text: `סומן שאינו מכיל: ${info.free.join(", ")}`}) : null,
    info.incomplete ? h("p", {class: "callout callout-warning"}, icon("warning"),
      h("span", {text: info.unknown.length
        ? `לא ידוע: ${info.unknown.join(", ")}. אין להסיק שהמנה נקייה מאלרגנים.`
        : "מידע האלרגנים אינו מלא. אין להסיק שהמנה נקייה מאלרגנים."})) : null,
  );

  fill(dialog, 
    h("div", { class: "dialog-body" },
      h("h2", { id: "allergen-title", class: "dialog-title", text: `מידע על אלרגנים: ${dish.name}` }),
      body,
      h("p", { class: "muted small", text: DISCLAIMER }),
      h("div", { class: "dialog-actions" },
        h("button", { class: "btn btn-primary", type: "button", onclick: () => dialog.close() }, "הבנתי"),
      ),
    ),
  );
  dialog.showModal();
}
