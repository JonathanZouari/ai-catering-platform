// Owner screen A2/A3: categories, dishes, pricing, dietary + allergens.
// All server data is written with textContent only (never innerHTML).
import { $, call, confirmThen, el, explain, mutate, startAdmin, toast } from "/js/admin-common.js";

const UNIT = { per_guest: "לאורח", per_tray: "למגש", per_weight: "לפי משקל", per_item: "ליחידה" };
const KASHRUT = { meat: ["בשרי", "k-meat"], dairy: ["חלבי", "k-dairy"], pareve: ["פרווה", "k-parve"] };
const ERRORS = {
  conflict: "השם הזה כבר קיים",
  category_not_empty: "יש מנות בקטגוריה. העבירו או מחקו אותן קודם",
  dish_in_orders: "המנה מופיעה בהזמנות ולא ניתן למחוק אותה. אפשר לסמן אותה כלא זמינה",
};

const state = { categories: [], dishes: [], allergens: [], editing: null };

const money = (value, currency) => {
  try { return new Intl.NumberFormat("he-IL", { style: "currency", currency }).format(value); }
  catch { return `${value} ${currency}`; }
};

async function load() {
  [state.categories, state.dishes, state.allergens] = await Promise.all([
    call("/api/admin/categories"), call("/api/admin/dishes"), call("/api/admin/allergens"),
  ]);
  renderCategories();
  renderDishes();
  renderAllergenFields(dietaryPayload().allergens); // keep unsaved choices
}

function renderCategories() {
  const options = state.categories.map((c) => el("option", { value: c.id, textContent: c.name }));
  const filter = $("filter");
  const current = filter.value;
  filter.replaceChildren(el("option", { value: "", textContent: "כל הקטגוריות" }), ...options.map((o) => o.cloneNode(true)));
  filter.value = state.categories.some((c) => c.id === current) ? current : "";
  const select = $("d-category");
  const chosen = select.value;
  select.replaceChildren(...options);
  if (chosen) select.value = chosen;

  $("cat-rows").replaceChildren(...state.categories.map((c) => {
    const name = el("input", { value: c.name, maxLength: 120, required: true });
    name.setAttribute("aria-label", `שם הקטגוריה ${c.name}`);
    const order = el("input", { type: "number", min: 0, max: 10000, value: c.sort_order, className: "num" });
    order.setAttribute("aria-label", `סדר הקטגוריה ${c.name}`);
    order.style.inlineSize = "6em";
    const active = el("input", { type: "checkbox", checked: c.is_active });
    active.setAttribute("aria-label", `הקטגוריה ${c.name} פעילה`);
    const save = el("button", { type: "button", className: "btn ghost", textContent: "שמירה" });
    save.onclick = () => mutate(() => call(`/api/admin/categories/${c.id}`, {
      method: "PATCH", body: JSON.stringify({ name: name.value, sort_order: Number(order.value) || 0, is_active: active.checked }),
    }), "הקטגוריה נשמרה");
    const del = el("button", { type: "button", className: "btn danger", textContent: "מחיקה" });
    del.onclick = () => confirmThen(del, () => mutate(() => call(`/api/admin/categories/${c.id}`, { method: "DELETE" }), "הקטגוריה נמחקה"));
    const tr = el("tr", {}, el("td", {}, name), el("td", {}, order), el("td", {}, active), el("td", {}, save, " ", del));
    return tr;
  }));
}

function renderDishes() {
  const filter = $("filter").value;
  const names = Object.fromEntries(state.categories.map((c) => [c.id, c.name]));
  const shown = state.dishes.filter((d) => !filter || d.category_id === filter);
  $("no-dishes").hidden = shown.length > 0;
  $("dish-rows").replaceChildren(...shown.map((d) => {
    const title = el("th", { scope: "row" }, el("span", { className: "o-name", textContent: d.name }),
      el("span", { className: "help", textContent: names[d.category_id] ?? "" }));
    if (!d.is_available) title.append(el("span", { className: "pill s-rejected", textContent: "לא זמינה" }));
    const price = el("td", { className: "num" }, money(d.unit_price, d.currency), " ",
      el("span", { className: "help", textContent: d.unit_label || UNIT[d.pricing_unit] }));
    const k = KASHRUT[d.dietary.kashrut_class];
    const kashrut = el("td", {}, k ? el("span", { className: `badge ${k[1]}`, textContent: k[0] })
      : el("span", { className: "unknown", textContent: "לא ידוע" }));
    const edit = el("button", { type: "button", className: "btn ghost", textContent: "עריכה" });
    edit.setAttribute("aria-label", `עריכת ${d.name}`);
    edit.onclick = () => openEditor(d);
    return el("tr", {}, title, price, kashrut, el("td", {}, edit));
  }));
}

function renderAllergenFields(current) {
  const status = Object.fromEntries(current.map((a) => [a.allergen_id, a.status]));
  $("allergen-fields").replaceChildren(...state.allergens.map((a) => {
    const id = `allergen-${a.id}`;
    const select = el("select", { id, name: "allergen" },
      el("option", { value: "unknown", textContent: "לא ידוע" }),
      el("option", { value: "contains", textContent: "מכיל" }),
      el("option", { value: "free", textContent: "לא מכיל" }));
    select.dataset.allergenId = a.id;
    select.value = status[a.id] ?? "unknown";
    return el("div", { className: "field" }, el("label", { htmlFor: id, textContent: a.name }), select);
  }));
}

const triState = (v) => (v === null || v === undefined ? "" : String(v));
const fromTriState = (v) => (v === "" ? null : v === "true");

function openEditor(dish) {
  state.editing = dish;
  const f = $("dish-form");
  f.reset();
  $("form-error").hidden = true;
  $("form-h").textContent = dish ? `עריכה: ${dish.name}` : "מנה חדשה";
  $("delete-dish").hidden = !dish;
  if (dish) {
    $("d-name").value = dish.name;
    $("d-category").value = dish.category_id;
    $("d-desc").value = dish.description ?? "";
    $("d-unit").value = dish.pricing_unit;
    $("d-price").value = dish.unit_price;
    $("d-label").value = dish.unit_label ?? "";
    $("d-min").value = dish.min_quantity ?? "";
    $("d-serves").value = dish.serves_adults ?? "";
    $("d-avail").checked = dish.is_available;
    $("d-kashrut").value = dish.dietary.kashrut_class ?? "";
    $("d-veg").value = triState(dish.dietary.is_vegetarian);
    $("d-vegan").value = triState(dish.dietary.is_vegan);
  } else if ($("filter").value) {
    $("d-category").value = $("filter").value;
  }
  renderAllergenFields(dish?.allergens ?? []);
  $("d-name").focus({ preventScroll: true });
  f.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
}

function dishPayload() {
  const text = (id) => $(id).value.trim() || null;
  return {
    category_id: $("d-category").value || null,
    name: $("d-name").value.trim(),
    description: text("d-desc"),
    pricing_unit: $("d-unit").value,
    unit_price: $("d-price").value,
    unit_label: text("d-label"),
    min_quantity: text("d-min"),
    serves_adults: text("d-serves"),
    is_available: $("d-avail").checked,
  };
}

function dietaryPayload() {
  return {
    kashrut_class: $("d-kashrut").value || null,
    is_vegetarian: fromTriState($("d-veg").value),
    is_vegan: fromTriState($("d-vegan").value),
    allergens: [...$("allergen-fields").querySelectorAll("select")]
      .map((s) => ({ allergen_id: Number(s.dataset.allergenId), status: s.value })),
  };
}

function validate(form) {
  let ok = true;
  for (const input of form.querySelectorAll("#d-name, #d-category, #d-price, #d-min, #d-serves")) {
    const bad = !input.checkValidity();
    input.setAttribute("aria-invalid", String(bad));
    if (bad && ok) { input.focus(); ok = false; }
  }
  return ok;
}

async function saveDish(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = $("form-error");
  error.hidden = true;
  if (!validate(form)) {
    error.textContent = "יש למלא שם, קטגוריה ומחיר תקין (וכמויות חיוביות)";
    error.hidden = false;
    return;
  }
  try {
    const id = state.editing?.id;
    const dish = await call(id ? `/api/admin/dishes/${id}` : "/api/admin/dishes", {
      method: id ? "PATCH" : "POST", body: JSON.stringify(dishPayload()),
    });
    state.editing = await call(`/api/admin/dishes/${dish.id}/dietary`, {
      method: "PUT", body: JSON.stringify(dietaryPayload()),
    });
    openEditor(state.editing);
    await load();
    toast("המנה נשמרה");
  } catch (err) {
    if (err.status === 401) return;
    error.textContent = explain(err);
    error.hidden = false;
  }
}

export function initAdmin() {
  $("cat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const name = $("cat-name");
    const sort = state.categories.reduce((m, c) => Math.max(m, c.sort_order), -1) + 1;
    mutate(() => call("/api/admin/categories", { method: "POST", body: JSON.stringify({ name: name.value, sort_order: Math.min(sort, 10000) }) }), "הקטגוריה נוספה")
      .then((ok) => { if (ok) name.value = ""; });
  });
  $("filter").addEventListener("change", renderDishes);
  $("new-dish").addEventListener("click", () => openEditor(null));
  $("dish-form").addEventListener("submit", saveDish);
  $("delete-dish").addEventListener("click", (e) => confirmThen(e.currentTarget, () =>
    mutate(() => call(`/api/admin/dishes/${state.editing.id}`, { method: "DELETE" }), "המנה נמחקה")
      .then((ok) => ok && openEditor(null))));
  $("add-allergen").addEventListener("click", () => {
    const input = $("new-allergen");
    if (!input.value.trim()) return;
    mutate(() => call("/api/admin/allergens", { method: "POST", body: JSON.stringify({ name: input.value }) }), "האלרגן נוסף")
      .then((ok) => { if (ok) input.value = ""; });
  });
  startAdmin({ content: "catalog", load, errors: ERRORS });
}
