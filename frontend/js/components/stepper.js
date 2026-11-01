import { h } from "../dom.js";

// Pill stepper (− n +). Becomes accent-tinted when value > 0.
export function createStepper({ label, value = 0, min = 0, max = 999, step = 1, onChange }) {
  const out = h("output", { "aria-label": label });
  const dec = h("button", { type: "button", "aria-label": `הפחתה: ${label}` }, "−");
  const inc = h("button", { type: "button", "aria-label": `הוספה: ${label}` }, "+");
  const el = h("div", { class: "stepper", role: "group", "aria-label": label }, inc, out, dec);
  let current = value;

  const paint = () => {
    out.textContent = current;
    el.classList.toggle("is-active", current > 0);
    dec.disabled = current <= min;
    inc.disabled = current >= max;
  };
  const change = (delta) => {
    const next = Math.min(max, Math.max(min, current + delta));
    if (next !== current) onChange?.(next);
  };
  dec.addEventListener("click", () => change(-step));
  inc.addEventListener("click", () => change(step));
  paint();

  return {
    el,
    set(next) { current = next; paint(); },
    pulse() { el.classList.remove("is-pulsing"); void el.offsetWidth; el.classList.add("is-pulsing"); },
  };
}
