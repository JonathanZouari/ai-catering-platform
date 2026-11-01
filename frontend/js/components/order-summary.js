import { h } from "../dom.js";
import { ils, reducedMotion } from "../format.js";
import { UNITS, dishById, orderTotal } from "../mock/menu.js";

// Running order: lines (qty × unit = line) and a rolling total. The visible total is aria-hidden while
// it rolls; a separate polite live region announces only the final value.
export function createOrderSummary() {
  const lines = h("ul", { class: "summary__lines" });
  const totalEl = h("strong", { class: "summary__total num", "aria-hidden": "true" }, ils(0));
  const live = h("span", { class: "visually-hidden", "aria-live": "polite" });
  const foot = h("div", { class: "summary__foot" },
    h("p", { class: "summary__delivery muted" }, h("span", {}, "משלוח"), h("span", {}, "לפי אזור, יחושב באישור")),
    h("p", { class: "summary__sum" }, h("span", {}, "סה״כ (ללא משלוח)"), totalEl, live),
  );
  const el = h("section", { class: "summary", "aria-label": "סיכום ההזמנה" },
    h("h3", {}, "ההזמנה שלכם"),
    lines,
    foot,
  );
  const mirrors = []; // other elements that show the same total (mobile bar)
  let shown = null;
  let frame = 0;

  const paintTotal = (value) => { for (const t of [totalEl, ...mirrors]) t.textContent = ils(value); };

  function roll(to, ms = 700) {
    cancelAnimationFrame(frame);
    const from = shown ?? to;
    shown = to;
    if (reducedMotion() || from === to) { paintTotal(to); return; }
    const t0 = performance.now();
    totalEl.classList.add("is-rolling");
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / ms);
      paintTotal(from + (to - from) * (1 - (1 - p) ** 3));
      if (p < 1) frame = requestAnimationFrame(tick);
      else totalEl.classList.remove("is-rolling");
    };
    frame = requestAnimationFrame(tick);
  }

  function update(order, { highlight = [] } = {}) {
    lines.replaceChildren(...Object.entries(order).filter(([, q]) => q > 0).map(([id, qty]) => {
      const dish = dishById(id);
      const unit = UNITS[dish.unit];
      return h("li", { class: highlight.includes(id) ? "is-new" : "" },
        h("span", { class: "summary__name" }, dish.name),
        h("span", { class: "summary__calc num muted" }, `${qty} ${qty === 1 ? unit.one : unit.many} × ${ils(dish.price)}`),
        h("span", { class: "summary__line num" }, ils(dish.price * qty)),
      );
    }));
    // Scroll only the summary box (not the page) so the new line is in view.
    const fresh = lines.querySelector(".is-new");
    const box = el.closest(".agent__summary");
    if (fresh && box) {
      box.scrollTop += fresh.getBoundingClientRect().top - box.getBoundingClientRect().top - box.clientHeight / 3;
    }
    const total = orderTotal(order);
    roll(total);
    live.textContent = `סה״כ ${ils(total)}`;
  }

  return { el, foot, totalEl, update, mirror: (node) => mirrors.push(node) };
}
