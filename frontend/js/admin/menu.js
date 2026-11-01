// A2/A3: categories and dishes, including prices, dietary data, and allergens.
import { adminApi, getConfig, patchJson, postJson, putJson, remove, upload } from "/js/admin/auth.js";
import {
  confirmDelete, field, h, numberOrNull, openDialog, select, textOrNull,
} from "/js/ui.js";

const UNITS = [
  ["per_tray", "למגש"], ["per_guest", "לסועד"], ["per_item", "ליחידה"], ["per_weight", "לפי משקל"],
];
const UNIT_LABELS = Object.fromEntries(UNITS);
const CATEGORY_TYPES = [
  ["salad", "סלטים"], ["main", "מנות עיקריות"], ["side", "תוספות"],
  ["dessert", "קינוחים"], ["drink", "משקאות"], ["other", "אחר"],
];
const KASHRUT = [["", "לא ידוע"], ["meat", "בשרי"], ["dairy", "חלבי"], ["pareve", "פרווה"]];
const TRI_STATE = [["", "לא ידוע"], ["true", "כן"], ["false", "לא"]];
const ALLERGEN = [["unknown", "לא ידוע"], ["contains", "מכיל"], ["free", "לא מכיל"]];

const toTriState = (value) => (value === null || value === undefined ? "" : String(value));
const fromTriState = (value) => (value === "" ? null : value === "true");

export async function renderMenu(view) {
  const [categories, dishes, allergens] = await Promise.all([
    adminApi("/api/admin/categories"),
    adminApi("/api/admin/dishes"),
    adminApi("/api/admin/allergens"),
  ]);
  const refresh = () => renderMenu(view);
  const context = { categories, allergens, refresh };

  view.replaceChildren(
    h("header", { className: "screen-header" },
      h("h1", {}, "תפריט"),
      h("div", { className: "actions" },
        h("button", { className: "secondary", onclick: () => openCategoryForm(null, refresh) }, "קטגוריה חדשה"),
        categories.length
          ? h("button", { onclick: () => openDishForm(null, context) }, "מנה חדשה")
          : null)),
    ...(categories.length
      ? categories.map((category) => categorySection(category, dishes, context))
      : [h("p", { className: "empty" }, "עדיין אין קטגוריות. התחילו ביצירת קטגוריה, למשל סלטים.")]),
  );
}

function categorySection(category, dishes, context) {
  const own = dishes.filter((dish) => dish.category_id === category.id);
  return h("section", { className: "card" },
    h("header", { className: "screen-header" },
      h("h2", {}, category.name, category.is_active ? null : h("span", { className: "badge" }, "מוסתר")),
      h("div", { className: "actions" },
        h("button", { className: "secondary", onclick: () => openCategoryForm(category, context.refresh) }, "עריכה"),
        h("button", {
          className: "secondary danger",
          onclick: () => confirmDelete(category.name, async () => {
            await remove(`/api/admin/categories/${category.id}`);
            await context.refresh();
          }),
        }, "מחיקה"))),
    own.length
      ? h("ul", { className: "rows" }, own.map((dish) => dishRow(dish, context)))
      : h("p", { className: "empty" }, "אין מנות בקטגוריה הזו."));
}

function dishRow(dish, context) {
  const { kashrut_class: kashrut } = dish.dietary ?? {};
  return h("li", {},
    h("div", {},
      h("strong", {}, dish.name),
      dish.is_available ? null : h("span", { className: "badge" }, "לא זמין"),
      h("div", { className: "muted" },
        h("bdi", {}, `₪${dish.unit_price}`),
        ` ${UNIT_LABELS[dish.pricing_unit]}`,
        dish.unit_label ? ` (${dish.unit_label})` : "",
        ` · כשרות: ${KASHRUT.find(([value]) => value === (kashrut ?? ""))[1]}`,
        ` · קלוריות: ${dish.calories_per_portion ?? "לא צוין"}`)),
    h("div", { className: "actions" },
      h("button", { className: "secondary", onclick: () => openDishForm(dish, context) }, "עריכה"),
      h("button", {
        className: "secondary danger",
        onclick: () => confirmDelete(dish.name, async () => {
          await remove(`/api/admin/dishes/${dish.id}`);
          await context.refresh();
        }),
      }, "מחיקה")));
}

function openCategoryForm(category, refresh) {
  const name = h("input", { required: true, maxLength: 120, value: category?.name ?? "" });
  const type = select(CATEGORY_TYPES, category?.category_type ?? "other");
  const order = h("input", { type: "number", value: category?.sort_order ?? 0 });
  const active = h("input", { type: "checkbox", checked: category?.is_active ?? true });
  openDialog(category ? "עריכת קטגוריה" : "קטגוריה חדשה", [
    field("שם", name),
    field("סוג", type, "קובע את ההמלצה על כמויות ללקוחות"),
    field("סדר הצגה", order),
    field("מוצגת ללקוחות", active),
  ], async () => {
    const data = { name: name.value.trim(), category_type: type.value, sort_order: Number(order.value) };
    if (category) {
      await patchJson(`/api/admin/categories/${category.id}`, { ...data, is_active: active.checked });
    } else {
      await postJson("/api/admin/categories", data);
    }
    await refresh();
  });
}

async function openDishForm(dish, { categories, allergens, refresh }) {
  const { storage_public_url: storageUrl } = await getConfig();
  const name = h("input", { required: true, maxLength: 120, value: dish?.name ?? "" });
  const category = select(categories.map((c) => [c.id, c.name]), dish?.category_id);
  const description = h("textarea", { rows: 2, value: dish?.description ?? "" });
  const unit = select(UNITS, dish?.pricing_unit);
  const price = h("input", {
    type: "number", min: "0", step: "0.01", required: true, inputMode: "decimal",
    value: dish?.unit_price ?? "",
  });
  const unitLabel = h("input", { value: dish?.unit_label ?? "" });
  const servings = h("input", {
    type: "number", min: "0.01", step: "0.01", value: dish?.servings_per_unit ?? "",
  });
  const calories = h("input", { type: "number", min: "0", value: dish?.calories_per_portion ?? "" });
  const portion = h("input", { value: dish?.portion_description ?? "" });
  const minimum = h("input", {
    type: "number", min: "0.01", step: "0.01", value: dish?.min_quantity ?? "",
  });
  const available = h("input", { type: "checkbox", checked: dish?.is_available ?? true });
  const kashrut = select(KASHRUT, dish?.dietary?.kashrut_class ?? "");
  const vegetarian = select(TRI_STATE, toTriState(dish?.dietary?.is_vegetarian));
  const vegan = select(TRI_STATE, toTriState(dish?.dietary?.is_vegan));
  const image = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp" });

  const current = Object.fromEntries((dish?.allergens ?? []).map((a) => [a.allergen_id, a.status]));
  const allergenControls = allergens.map((allergen) => ({
    allergen, control: select(ALLERGEN, current[allergen.id] ?? "unknown"),
  }));

  openDialog(dish ? "עריכת מנה" : "מנה חדשה", [
    dish?.image_path && storageUrl
      ? h("img", { className: "preview", src: `${storageUrl}/${dish.image_path}`, alt: dish.name })
      : null,
    field("שם המנה", name),
    field("קטגוריה", category),
    field("תיאור", description),
    h("div", { className: "grid" },
      field("תמחור", unit),
      field("מחיר בש״ח", price),
      field("תיאור יחידה", unitLabel, "למשל מגש גדול, או ק״ג במחיר לפי משקל"),
      field("מנות ביחידה", servings, "לכמה סועדים מספיקה יחידה אחת. ריק = בלי המלצת כמות")),
    h("div", { className: "grid" },
      field("קלוריות למנה", calories, "ריק = לא ידוע"),
      field("מה נחשב מנה", portion, "למשל 100 גרם"),
      field("כמות מינימלית", minimum)),
    field("זמינה להזמנה", available),
    field("תמונה", image, "PNG, JPG או WEBP, עד 5MB"),
    h("h3", {}, "כשרות ותזונה"),
    h("div", { className: "grid" },
      field("כשרות", kashrut),
      field("צמחוני", vegetarian),
      field("טבעוני", vegan)),
    h("h3", {}, "אלרגנים"),
    h("p", { className: "muted" }, "\"לא ידוע\" מוצג ללקוחות כמידע שלא אומת, ולעולם לא כ\"לא מכיל\"."),
    h("div", { className: "grid" }, allergenControls.map(({ allergen, control }) => field(allergen.name, control))),
  ], async () => {
    const data = {
      name: name.value.trim(),
      category_id: category.value,
      description: textOrNull(description.value),
      pricing_unit: unit.value,
      unit_price: price.value,
      unit_label: textOrNull(unitLabel.value),
      servings_per_unit: servings.value || null,
      calories_per_portion: numberOrNull(calories.value),
      portion_description: textOrNull(portion.value),
      min_quantity: minimum.value || null,
      is_available: available.checked,
    };
    const saved = dish
      ? await patchJson(`/api/admin/dishes/${dish.id}`, data)
      : await postJson("/api/admin/dishes", data);
    // The dish is saved from here on, so reopen it on a retry rather than duplicating it.
    dish = saved;
    await putJson(`/api/admin/dishes/${saved.id}/dietary`, {
      kashrut_class: kashrut.value || null,
      is_vegetarian: fromTriState(vegetarian.value),
      is_vegan: fromTriState(vegan.value),
      allergens: allergenControls.map(({ allergen, control }) => ({
        allergen_id: allergen.id, status: control.value,
      })),
    });
    if (image.files[0]) await upload(`/api/admin/dishes/${saved.id}/image`, image.files[0]);
    await refresh();
  });
}

