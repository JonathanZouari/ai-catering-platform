// Owner dashboard: A1 orders (approve / reject quotes) and A2 dishes, prices and allergens.
// Runs on SAMPLE DATA in memory until the admin API exists (Phase 2); nothing here persists.
import {
  categories, dishes as sampleDishes, quoteRequests, draftOrder, assistantProposal, deliveryZone,
  unitLabels, unitNouns, kashrutLabels, dietLabels, allergenLabels, timeSlots,
} from "/js/sample-data.js";
import { formatPrice, formatDate } from "/js/format.js";
import { h, ltr, $ } from "/js/dom.js";

const quotes = structuredClone(quoteRequests);
const dishes = structuredClone(sampleDishes);
let orderFilter = "pending";
let selectedQuote = quotes.find((q) => q.status === "pending")?.id;
let dishFilter = "all";
let editingId = null;

const statusInfo = {
  pending: { label: "ממתין לאישור", icon: "🕓 ", cls: "status--pending" },
  approved: { label: "אושר", icon: "✓ ", cls: "status--approved" },
  rejected: { label: "נדחה", icon: "✕ ", cls: "status--rejected" },
};
const statusBadge = (s) => h("span", { class: `status ${statusInfo[s].cls}` }, statusInfo[s].icon, statusInfo[s].label);
const announce = (text) => { $("announcer").textContent = text; };

// Q-1042 carries the full line items in the sample data: the draft order with the assistant's approved changes.
const sampleLines = { ...draftOrder.lines };
for (const c of assistantProposal.changes) sampleLines[c.dishId] = c.to;

// ---------- Routing ----------

const views = ["orders", "dishes"];
function route() {
  const id = views.includes(location.hash.slice(1)) ? location.hash.slice(1) : "orders";
  for (const v of views) $(v).hidden = v !== id;
  document.querySelectorAll("#nav a[href]").forEach((a) =>
    a.toggleAttribute("aria-current", a.getAttribute("href") === `#${id}`));
  document.querySelectorAll('#nav a[href][aria-current]').forEach((a) => a.setAttribute("aria-current", "page"));
  document.title = `${$(id).dataset.title} · ניהול שולחן מלא`;
  $(id).querySelector("h1").focus({ preventScroll: true });
  // After the browser's own jump to the #anchor, so the view starts at the top.
  requestAnimationFrame(() => window.scrollTo(0, 0));
}

// ---------- A1 Orders ----------

function renderOrders() {
  const pending = quotes.filter((q) => q.status === "pending");
  const approvedSum = quotes.filter((q) => q.status === "approved").reduce((s, q) => s + q.total, 0);
  $("pending-count").textContent = pending.length ? `(${pending.length})` : "";
  $("orders-lead").textContent = pending.length
    ? `${pending.length} בקשות מחכות לאישור שלך.` : "אין בקשות שמחכות לאישור.";
  // Sample comparison figure; the real one comes from the reporting query.
  $("kpis").replaceChildren(
    h("div", {}, h("dt", {}, "בקשות ממתינות"), h("dd", {}, String(pending.length))),
    h("div", {}, h("dt", {}, "הצעות שאושרו החודש"), h("dd", {}, ltr(formatPrice(approvedSum))),
      h("p", { class: "hint" }, "בחודש שעבר: ", ltr(formatPrice(1400)))),
    h("div", {}, h("dt", {}, "אירועים מאושרים קרובים"), h("dd", {}, String(quotes.filter((q) => q.status === "approved").length))));

  const filters = [["pending", "ממתינות"], ["approved", "אושרו"], ["rejected", "נדחו"], ["all", "הכול"]];
  $("order-filters").replaceChildren(...filters.map(([id, label]) => h("button", {
    type: "button", class: "chip", "aria-pressed": String(orderFilter === id),
    onclick: () => { orderFilter = id; renderOrders(); },
  }, label, ` (${id === "all" ? quotes.length : quotes.filter((q) => q.status === id).length})`)));

  const rows = quotes.filter((q) => orderFilter === "all" || q.status === orderFilter)
    .sort((a, b) => a.date.localeCompare(b.date));
  $("orders-table").tBodies[0].replaceChildren(...(rows.length ? rows.map((q) => h("tr", {
    "aria-selected": String(q.id === selectedQuote),
  },
  h("th", { scope: "row" }, h("button", { type: "button", class: "link-btn", onclick: () => selectQuote(q.id) }, q.customer)),
  h("td", {}, q.eventType), h("td", {}, ltr(formatDate(q.date))), h("td", {}, String(q.guests)),
  h("td", {}, ltr(formatPrice(q.total))), h("td", {}, statusBadge(q.status))))
    : [h("tr", {}, h("td", { colspan: 6, class: "empty" }, "אין בקשות בסטטוס הזה."))]));
  renderDetail();
}

function selectQuote(id) {
  selectedQuote = id;
  renderOrders();
  $("order-detail").focus();
}

function renderDetail() {
  const q = quotes.find((x) => x.id === selectedQuote);
  const panel = $("order-detail");
  panel.tabIndex = -1;
  if (!q) { panel.replaceChildren(h("p", { class: "empty" }, "בחרו בקשה מהרשימה כדי לראות את הפרטים.")); return; }

  const e = draftOrder.event;
  const detailed = q.id === "Q-1042";
  // replaceChildren does not flatten nested arrays the way h() does, so flatten here.
  panel.replaceChildren(...[
    h("header", { class: "panel__head" },
      h("h2", {}, "בקשה ", ltr(`#${q.id}`), `, ${q.customer}`), statusBadge(q.status)),
    h("dl", { class: "facts" },
      h("dt", {}, "אירוע"), h("dd", {}, `${q.eventType}, `, ltr(formatDate(q.date)),
        detailed ? [", ", ltr(timeSlots.find((s) => s.id === e.slot).label)] : null),
      h("dt", {}, "אורחים"), h("dd", {}, detailed ? `${e.adults} מבוגרים, ${e.kids} ילדים (${e.vegetarian} צמחונים, ${e.vegan} טבעונים)` : String(q.guests)),
      detailed ? [h("dt", {}, "משלוח"), h("dd", {}, e.address)] : null),
    detailed ? h("p", { class: "hint" }, "2 שינויים נוספו על ידי הלקוח דרך העוזר, אחרי אישור שלו.") : null,
    detailed ? lineTable() : h("p", { class: "hint" }, "בנתוני הדוגמה יש פירוט מנות רק לבקשה Q-1042."),
    h("p", { class: "hint" }, "המחירים קפואים מרגע שהלקוח שלח את הבקשה."),
    q.status === "pending" ? [
      h("div", { class: "field" },
        h("label", { for: "owner-note" }, "הערה ללקוח (לא חובה)"),
        h("textarea", { class: "input", id: "owner-note", rows: 2, dir: "auto" })),
      h("div", { class: "panel__actions" },
        h("button", { type: "button", class: "btn btn--danger", onclick: () => rejectQuote(q) }, "דחיית הבקשה"),
        h("button", { type: "button", class: "btn btn--primary", onclick: () => approveQuote(q) }, "אישור ההצעה")),
    ] : null,
  ].flat().filter(Boolean));
}

function lineTable() {
  const rows = Object.entries(sampleLines).map(([id, qty]) => {
    const d = dishes.find((x) => x.id === id) ?? sampleDishes.find((x) => x.id === id);
    return h("tr", {}, h("th", { scope: "row" }, d.name), h("td", {}, `${qty} ${unitNouns[d.unit]}`),
      h("td", {}, ltr(formatPrice(d.price))), h("td", {}, ltr(formatPrice(d.price * qty))));
  });
  const subtotal = Object.entries(sampleLines).reduce((s, [id, qty]) => s + sampleDishes.find((x) => x.id === id).price * qty, 0);
  return h("table", { class: "table table--compact" },
    h("thead", {}, h("tr", {}, ["מנה", "כמות", "מחיר יחידה", "סה״כ"].map((t) => h("th", { scope: "col" }, t)))),
    h("tbody", {}, rows, h("tr", {}, h("th", { scope: "row", colspan: 3 }, `דמי משלוח (${deliveryZone.name})`), h("td", {}, ltr(formatPrice(deliveryZone.fee))))),
    h("tfoot", {}, h("tr", {}, h("th", { scope: "row", colspan: 3 }, "סה״כ"), h("td", {}, ltr(formatPrice(subtotal + deliveryZone.fee))))));
}

function approveQuote(q) {
  q.status = "approved";
  announce(`הבקשה של ${q.customer} אושרה.`);
  renderOrders();
  $("order-detail").focus();
}

function rejectQuote(q) {
  confirmAction({
    title: `לדחות את הבקשה של ${q.customer}?`,
    // PRD §7: rejected is a final state; there is no revision state in the MVP.
    text: "הלקוח יראה בדף הסטטוס שהבקשה נדחתה. אחרי דחייה אי אפשר להחזיר אותה להמתנה.",
    ok: "דחיית הבקשה",
    onConfirm: () => {
      q.status = "rejected";
      announce(`הבקשה של ${q.customer} נדחתה.`);
      renderOrders();
      $("order-detail").focus();
    },
  });
}

// ---------- Confirm dialog (irreversible actions only) ----------

function confirmAction({ title, text, ok, onConfirm }) {
  const dlg = $("confirm");
  $("confirm-title").textContent = title;
  $("confirm-text").textContent = text;
  $("confirm-ok").textContent = ok;
  $("confirm-ok").onclick = () => { dlg.close(); onConfirm(); };
  $("confirm-cancel").onclick = () => dlg.close();
  dlg.showModal(); // autofocus lands on "ביטול", never on the destructive button
}

// ---------- A2 Dishes ----------

function allergenSummary(d) {
  const contains = Object.keys(d.allergens).filter((a) => d.allergens[a] === "contains").map((a) => allergenLabels[a]);
  const unknown = Object.keys(d.allergens).filter((a) => d.allergens[a] === "unknown").map((a) => allergenLabels[a]);
  return [contains.length ? contains.join(", ") : "אין",
    unknown.length ? h("span", { class: "tag tag--warning" }, `? לא ידוע: ${unknown.join(", ")}`) : null];
}

function renderDishes() {
  $("dishes-lead").textContent = `${dishes.length} מנות בתפריט. נתוני דוגמה.`;
  const filters = [{ id: "all", name: "הכול" }, ...categories];
  $("dish-filters").replaceChildren(...filters.map((c) => h("button", {
    type: "button", class: "chip", "aria-pressed": String(dishFilter === c.id),
    onclick: () => { dishFilter = c.id; renderDishes(); },
  }, c.name)));

  const rows = dishes.filter((d) => dishFilter === "all" || d.category === dishFilter)
    .sort((a, b) => a.name.localeCompare(b.name, "he"));
  $("dishes-table").tBodies[0].replaceChildren(...(rows.length ? rows.map((d) => h("tr", { id: `row-${d.id}` },
    h("td", {}, d.photo ? h("div", { class: "photo-frame thumb" }, h("img", { src: d.photo, alt: "", width: 56, height: 56, loading: "lazy" })) : null),
    h("th", { scope: "row" }, d.name, h("p", { class: "hint truncate", title: d.description }, d.description)),
    h("td", {}, ltr(formatPrice(d.price)), ` ${unitLabels[d.unit]}`),
    h("td", {}, h("span", { class: "tag" }, kashrutLabels[d.kashrut])),
    h("td", {}, allergenSummary(d)),
    h("td", {}, h("button", {
      type: "button", class: "switch", role: "switch", "aria-checked": String(d.available),
      "aria-label": `${d.name} זמינה להזמנה`,
      onclick: () => { d.available = !d.available; announce(`${d.name}: ${d.available ? "זמינה" : "לא זמינה"}`); renderDishes(); $(`row-${d.id}`).querySelector(".switch").focus(); },
    }, d.available ? "כן" : "לא")),
    h("td", {}, h("button", { type: "button", class: "btn", onclick: () => openEditor(d.id) }, "עריכה", h("span", { class: "visually-hidden" }, `: ${d.name}`)))))
    : [h("tr", {}, h("td", { colspan: 7, class: "empty" }, "אין מנות בקטגוריה הזו. אפשר להוסיף מנה חדשה."))]));
}

function radioGroup(name, legend, options, value) {
  return h("fieldset", { class: "field" }, h("legend", {}, legend),
    h("div", { class: "chips" }, Object.entries(options).map(([v, label]) =>
      h("label", { class: "choice" }, h("input", { type: "radio", name, value: v, checked: v === value }), label))));
}

function openEditor(id) {
  editingId = id;
  const d = dishes.find((x) => x.id === id) ?? {
    name: "", description: "", category: dishFilter === "all" ? "salads" : dishFilter, unit: "tray", price: "",
    kashrut: "parve", diet: [], allergens: Object.fromEntries(Object.keys(allergenLabels).map((a) => [a, "unknown"])),
  };
  $("editor-title").textContent = id ? `עריכת מנה: ${d.name}` : "מנה חדשה";
  $("delete-dish").hidden = !id;
  $("dish-fields").replaceChildren(
    h("div", { class: "field" }, h("label", { for: "f-name" }, "שם המנה"),
      h("input", { class: "input", id: "f-name", name: "name", value: d.name, dir: "auto", "aria-describedby": "f-name-error" }),
      h("p", { class: "error", id: "f-name-error", hidden: true })),
    h("div", { class: "field" }, h("label", { for: "f-desc" }, "תיאור"),
      h("textarea", { class: "input", id: "f-desc", name: "description", rows: 2, dir: "auto" }, d.description)),
    h("div", { class: "field" }, h("label", { for: "f-cat" }, "קטגוריה"),
      h("select", { class: "input", id: "f-cat", name: "category" },
        categories.map((c) => h("option", { value: c.id, selected: c.id === d.category }, c.name)))),
    radioGroup("unit", "יחידת תמחור", unitLabels, d.unit),
    h("div", { class: "field" }, h("label", { for: "f-price" }, "מחיר ליחידה (₪)"),
      h("input", { class: "input", id: "f-price", name: "price", type: "number", min: 1, step: 1, inputmode: "numeric", value: d.price, dir: "ltr", "aria-describedby": "f-price-error" }),
      h("p", { class: "error", id: "f-price-error", hidden: true })),
    radioGroup("kashrut", "כשרות", kashrutLabels, d.kashrut),
    h("fieldset", { class: "field" }, h("legend", {}, "תכונות"),
      h("div", { class: "chips" }, Object.entries(dietLabels).map(([v, label]) =>
        h("label", { class: "choice" }, h("input", { type: "checkbox", name: "diet", value: v, checked: d.diet.includes(v) }), label)))),
    h("fieldset", { class: "field allergen-editor" }, h("legend", {}, "אלרגנים"),
      h("p", { class: "hint" }, "״לא ידוע״ מוצג ללקוח כאזהרה, אף פעם לא כ״ללא״."),
      Object.entries(allergenLabels).map(([a, label]) => h("fieldset", { class: "allergen-row" },
        h("legend", {}, label),
        h("div", { class: "segmented3" }, [["contains", "מכיל"], ["free", "לא מכיל"], ["unknown", "לא ידוע"]].map(([v, text]) =>
          h("label", { class: "choice" }, h("input", { type: "radio", name: `al-${a}`, value: v, checked: d.allergens[a] === v }), text)))))));
  $("dish-editor").showModal();
}

function saveDish(ev) {
  ev.preventDefault();
  const f = $("dish-form");
  const name = f.elements.name.value.trim();
  const price = Number(f.elements.price.value);
  const errors = { "f-name": !name ? "כתבו שם למנה." : null, "f-price": !(price > 0) ? "כתבו מחיר גדול מאפס, בשקלים." : null };
  for (const [id, msg] of Object.entries(errors)) {
    $(`${id}-error`).textContent = msg ?? "";
    $(`${id}-error`).hidden = !msg;
    $(id).toggleAttribute("aria-invalid", Boolean(msg));
  }
  const first = Object.keys(errors).find((k) => errors[k]);
  if (first) { $(first).focus(); return; }

  const values = {
    name, price, description: f.elements.description.value.trim(), category: f.elements.category.value,
    unit: f.elements.unit.value, kashrut: f.elements.kashrut.value,
    diet: [...f.querySelectorAll('input[name="diet"]:checked')].map((i) => i.value),
    allergens: Object.fromEntries(Object.keys(allergenLabels).map((a) => [a, f.elements[`al-${a}`].value])),
  };
  if (editingId) Object.assign(dishes.find((x) => x.id === editingId), values);
  else dishes.push({ id: `new-${Date.now()}`, photo: null, serves: null, available: true, ...values });
  $("dish-editor").close();
  announce(`המנה ${name} נשמרה.`);
  renderDishes();
}

function deleteDish() {
  const index = dishes.findIndex((x) => x.id === editingId);
  const dish = dishes[index];
  confirmAction({
    title: `למחוק את ${dish.name}?`,
    text: "המנה תימחק מהתפריט לצמיתות. בקשות שכבר נשלחו שומרות את המחיר שלהן.",
    ok: "מחיקת המנה",
    onConfirm: () => {
      dishes.splice(index, 1);
      $("dish-editor").close();
      announce(`המנה ${dish.name} נמחקה.`);
      renderDishes();
      // Focus the next row, or the previous one if the deleted dish was last.
      const rows = $("dishes-table").tBodies[0].rows;
      rows[Math.min(index, rows.length - 1)]?.querySelector("button")?.focus();
    },
  });
}

// ---------- Wiring ----------

$("dish-form").addEventListener("submit", saveDish);
$("delete-dish").addEventListener("click", deleteDish);
$("new-dish").addEventListener("click", () => openEditor(null));
document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => $("dish-editor").close()));
document.querySelectorAll('#nav [aria-disabled="true"]').forEach((a) => a.addEventListener("click", (e) => e.preventDefault()));
window.addEventListener("hashchange", route);

renderOrders();
renderDishes();
route();
