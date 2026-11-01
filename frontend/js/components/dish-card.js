import { h } from "../dom.js";
import { ils } from "../format.js";
import { UNITS, KIND_LABEL } from "../mock/menu.js";
import { createStepper } from "./stepper.js";

function allergenText(dish) {
  if (dish.allergens === null) return "אין מידע על אלרגנים למנה זו. אין להניח שהיא ללא אלרגנים.";
  if (dish.allergens.length === 0) return "לא מסומנים אלרגנים מוכרים (המידע מהעסק).";
  return `אלרגנים מוכרים: ${dish.allergens.join(", ")}.`;
}

// Photo is a "no photo" placeholder until real images exist (frontend/assets).
export function createDishCard(dish, qty, onQty) {
  const unit = UNITS[dish.unit];
  const tags = [KIND_LABEL[dish.kind], dish.vegan ? "טבעוני" : dish.vegetarian ? "צמחוני" : null].filter(Boolean);
  const stepper = createStepper({
    label: dish.name,
    value: qty,
    step: dish.step ?? 1,
    max: dish.step ? 400 : 99,
    onChange: onQty,
  });
  const el = h("article", { class: "dish-card card", "data-dish": dish.id },
    h("div", { class: "dish-card__photo", role: "img", "aria-label": "אין תמונה" }, h("span", { class: "plate" })),
    h("div", { class: "dish-card__row" },
      h("h3", {}, dish.name),
      h("span", { class: "dish-card__price num" }, ils(dish.price)),
    ),
    h("p", { class: "dish-card__meta muted" }, `${unit.per} · ${tags.join(" · ")}`),
    h("details", { class: "dish-card__allergens" },
      h("summary", {}, "מידע על אלרגנים"),
      h("p", {}, allergenText(dish)),
    ),
    stepper.el,
  );
  return { el, stepperEl: stepper.el, setQty: stepper.set, pulse: stepper.pulse };
}
