import { h } from "../dom.js";
import { ils, reducedMotion } from "../format.js";
import { UNITS, dishById, orderTotal } from "../mock/menu.js";

// Running order: a collapsible list of lines (qty × unit = line), then a foot that is always visible
// (delivery / pickup note, rolling total, CTA). Only the lines scroll. The visible total is aria-hidden while it
// rolls; a separate polite live region announces only the final value.
export function createOrderSummary({ isDelivery = true } = {}) {
  // Scrollbar hidden (one visible scrollbar in the panel); focusable so the list scrolls with the keyboard.
  const lines = h("ul", { class: "summary__lines", id: "order-lines", tabindex: "0", "aria-label": "מנות בהזמנה", hidden: true });
  const count = h("span", { class: "summary__count num" });
  const toggle = h("button", { type: "button", class: "summary__toggle", "aria-expanded": "false", "aria-controls": "order-lines", onClick: () => { clearTimeout(closeTimer); setOpen(lines.hidden); } },
    h("span", {}, "ההזמנה שלכם"), count);
  const totalEl = h("strong", { class: "summary__total num", "aria-hidden": "true" }, ils(0));
  const live = h("span", { class: "visually-hidden", "aria-live": "polite" });
  const foot = h("div", { class: "summary__foot" },
    isDelivery
      ? h("p", { class: "summary__delivery muted" }, h("span", {}, "משלוח"), h("span", {}, "לפי אזור, יחושב באישור"))
      : h("p", { class: "summary__delivery muted" }, h("span", {}, "קבלה"), h("span", {}, "איסוף עצמי")),
    h("p", { class: "summary__sum" }, h("span", {}, isDelivery ? "סה״כ (ללא משלוח)" : "סה״כ"), totalEl, live),
  );
  const el = h("section", { class: "summary", "aria-label": "סיכום ההזמנה" }, toggle, lines, foot);
  const mirrors = []; // other elements that show the same total (mobile bar)
  let shown = null;
  let frame = 0;
  let closeTimer = 0;

  const setOpen = (open) => { lines.hidden = !open; toggle.setAttribute("aria-expanded", String(open)); };
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
    if (fresh && !lines.hidden) {
      lines.scrollTop += fresh.getBoundingClientRect().top - lines.getBoundingClientRect().top - lines.clientHeight / 3;
    }
    const total = orderTotal(order);
    roll(total);
    live.textContent = `סה״כ ${ils(total)}`;
  }

  // open({ autoClose }) shows the lines; with autoClose (ms) it closes again unless it was already open or
  // the user toggled it meanwhile.
  function open({ autoClose = 0 } = {}) {
    const wasOpen = !lines.hidden;
    clearTimeout(closeTimer);
    if (!wasOpen) setOpen(true);
    if (autoClose && !wasOpen) closeTimer = setTimeout(() => setOpen(false), autoClose);
  }

  return { el, foot, totalEl, update, open, mirror: (node) => mirrors.push(node) };
}
