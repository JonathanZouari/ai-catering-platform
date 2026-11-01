import { h } from "../dom.js";
import { ils, reducedMotion } from "../format.js";
import { UNITS, dishById, orderTotal } from "../mock/menu.js";

// Running order: collapsible lines (qty × unit = line) and a rolling total. The visible total is aria-hidden
// while it rolls; a separate polite live region announces only the final value.
export function createOrderSummary() {
  // Scrollbar hidden (one visible scrollbar in the panel); focusable so the list scrolls with the keyboard.
  const lines = h("ul", { class: "summary__lines", tabindex: "0", "aria-label": "מנות בהזמנה" });
  const count = h("span", { class: "summary__count num" });
  const details = h("details", { class: "summary__details" },
    h("summary", {}, h("span", {}, "ההזמנה שלכם"), count),
    lines);
  const totalEl = h("strong", { class: "summary__total num", "aria-hidden": "true" }, ils(0));
  const live = h("span", { class: "visually-hidden", "aria-live": "polite" });
  const foot = h("div", { class: "summary__foot" },
    h("p", { class: "summary__delivery muted" }, h("span", {}, "משלוח"), h("span", {}, "לפי אזור, יחושב באישור")),
    h("p", { class: "summary__sum" }, h("span", {}, "סה״כ (ללא משלוח)"), totalEl, live),
  );
  const el = h("section", { class: "summary", "aria-label": "סיכום ההזמנה" }, details, foot);
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
    const entries = Object.entries(order).filter(([, q]) => q > 0);
    count.textContent = `${entries.length} מנות`;
    lines.replaceChildren(...entries.map(([id, qty]) => {
      const dish = dishById(id);
      const unit = UNITS[dish.unit];
      return h("li", { class: highlight.includes(id) ? "is-new" : "" },
        h("span", { class: "summary__name" }, dish.name),
        h("span", { class: "summary__calc num muted" }, `${qty} ${qty === 1 ? unit.one : unit.many} × ${ils(dish.price)}`),
        h("span", { class: "summary__line num" }, ils(dish.price * qty)),
      );
    }));
    // Scroll only the lines list (not the page) so the new line is in view.
    const fresh = lines.querySelector(".is-new");
    if (fresh && details.open) {
      lines.scrollTop += fresh.getBoundingClientRect().top - lines.getBoundingClientRect().top - lines.clientHeight / 3;
    }
    const total = orderTotal(order);
    roll(total);
    live.textContent = `סה״כ ${ils(total)}`;
  }

  // open({ autoClose }) shows the lines; with autoClose (ms) it closes again unless it was already open or
  // the user toggled it meanwhile.
  let closeTimer = 0;
  let programmatic = false;
  details.addEventListener("toggle", () => {
    if (programmatic) programmatic = false;
    else clearTimeout(closeTimer); // the user took over
  });
  function open({ autoClose = 0 } = {}) {
    const wasOpen = details.open;
    clearTimeout(closeTimer);
    if (!wasOpen) { programmatic = true; details.open = true; }
    if (autoClose && !wasOpen) {
      closeTimer = setTimeout(() => { if (details.open) { programmatic = true; details.open = false; } }, autoClose);
    }
  }

  return { el, foot, totalEl, update, open, mirror: (node) => mirrors.push(node) };
}
