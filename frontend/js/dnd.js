// Pointer-based drag and drop (mouse, touch and pen). A press that does not move
// stays a normal click, so every draggable is also a plain button for keyboard users.
import { img } from "./data.js";

const THRESHOLD = 6;

export function enableDrag({ scope = document, canDrag, getTarget, onDropOnTable, onDropOffTable, announce }) {
  let drag = null;

  scope.addEventListener("pointerdown", (ev) => {
    if (ev.button !== 0 || canDrag?.() === false) return;
    const src = ev.target.closest("[data-drag-dish],[data-drag-platter]");
    if (!src) return;
    const fromTable = src.hasAttribute("data-drag-platter");
    drag = {
      id: src.dataset.dragDish || src.dataset.dragPlatter,
      fromTable, src, startX: ev.clientX, startY: ev.clientY,
      lastX: ev.clientX, active: false, pointerId: ev.pointerId,
    };
  });

  function start(ev) {
    const table = getTarget();
    const size = fromTableSize(drag, table);
    const ghost = document.createElement("div");
    ghost.className = "drag-ghost";
    ghost.style.setProperty("--s", `${size}px`);
    ghost.innerHTML = `<img src="${img(drag.id)}" alt="">`;
    document.body.append(ghost);
    drag.ghost = ghost;
    drag.active = true;
    drag.size = size;
    drag.src.classList.add("is-dragging");
    document.documentElement.classList.add("is-dragging-dish");
    if (drag.fromTable) table.closest(".banquet")?.classList.add("is-lifting");
    try { drag.src.setPointerCapture(drag.pointerId); } catch { /* ignore */ }
    move(ev);
  }

  function fromTableSize(d, table) {
    const v = getComputedStyle(table.closest(".banquet") ?? table).getPropertyValue("--platter");
    const n = parseFloat(v);
    return Math.max(84, Math.min(150, Number.isFinite(n) && n > 0 ? n : 120));
  }

  function overTable(x, y) {
    const r = getTarget().getBoundingClientRect();
    return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
  }

  function move(ev) {
    const vx = ev.clientX - drag.lastX;
    drag.lastX = ev.clientX;
    drag.tilt = Math.max(-14, Math.min(14, (drag.tilt ?? 0) * 0.7 + vx * 0.9));
    const over = overTable(ev.clientX, ev.clientY);
    drag.over = over;
    drag.ghost.style.transform = `translate(${ev.clientX - drag.size / 2}px, ${ev.clientY - drag.size / 2}px) rotate(${drag.tilt}deg) scale(${over || drag.fromTable ? 1.04 : 0.9})`;
    drag.ghost.classList.toggle("is-removing", drag.fromTable && !over);
    getTarget().classList.toggle("is-over", over && !drag.fromTable);
  }

  window.addEventListener("pointermove", (ev) => {
    if (!drag || ev.pointerId !== drag.pointerId) return;
    if (!drag.active) {
      if (Math.hypot(ev.clientX - drag.startX, ev.clientY - drag.startY) < THRESHOLD) return;
      start(ev);
    }
    ev.preventDefault();
    move(ev);
  }, { passive: false });

  function end(ev, cancelled = false) {
    if (!drag || ev.pointerId !== drag.pointerId) return;
    const d = drag;
    drag = null;
    if (!d.active) return;
    // swallow the click that follows a real drag (pointerup only; cancel fires none)
    if (!cancelled) {
      const kill = (e) => { e.stopPropagation(); e.preventDefault(); };
      d.src.addEventListener("click", kill, { capture: true, once: true });
      setTimeout(() => d.src.removeEventListener("click", kill, true), 0);
    }
    setTimeout(() => d.src.classList.remove("is-dragging"), 0);
    document.documentElement.classList.remove("is-dragging-dish");
    getTarget().classList.remove("is-over");
    getTarget().closest(".banquet")?.classList.remove("is-lifting");
    const ghost = d.ghost;
    if (!cancelled && !d.fromTable && d.over) {
      ghost.classList.add("is-landing");
      onDropOnTable?.(d.id);
    } else if (!cancelled && d.fromTable && !d.over) {
      ghost.classList.add("is-gone");
      onDropOffTable?.(d.id);
    } else {
      ghost.classList.add("is-returning");
      if (!d.fromTable) announce?.("המנה לא נוספה. שחררו אותה מעל השולחן.");
    }
    setTimeout(() => ghost.remove(), 320);
  }

  window.addEventListener("pointerup", (ev) => end(ev));
  window.addEventListener("pointercancel", (ev) => end(ev, true));
  window.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && drag?.active) end({ pointerId: drag.pointerId }, true);
  });
}
