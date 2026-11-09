import { h, icon } from "../../lib/dom.js";

/**
 * Number field with +/- buttons. Returns { el, input, set(value) }. `label` names what is counted (e.g. "מבוגרים"),
 * so each pair of buttons reads differently to a screen reader ("הוספת מבוגרים", "הוספת ילדים").
 */
export function counter({ id, value, min = 0, max = 500, onChange, describedBy, label }) {
  const input = h("input", {
    id, class: "input counter-input", type: "number", inputmode: "numeric",
    min: String(min), max: String(max), step: "1", value: String(value),
    "aria-describedby": describedBy,
  });
  const clamp = (n) => Math.min(max, Math.max(min, Number.isFinite(n) ? n : min));
  const commit = (n) => {
    const next = clamp(n);
    input.value = String(next);
    onChange(next);
  };
  input.addEventListener("change", () => commit(Math.trunc(Number(input.value))));
  const step = (delta) => commit((Number(input.value) || 0) + delta);
  const el = h("div", { class: "counter" },
    h("button", { type: "button", class: "btn btn-secondary btn-icon", "aria-label": label ? `הפחתת ${label}` : "הפחתה", onclick: () => step(-1) }, icon("minus")),
    input,
    h("button", { type: "button", class: "btn btn-secondary btn-icon", "aria-label": label ? `הוספת ${label}` : "הוספה", onclick: () => step(1) }, icon("plus")),
  );
  return { el, input, set: (v) => (input.value = String(v)) };
}
