import { h } from "../dom.js";

// Signature motion: a pill flies in an arc from `from` to `to` (DOMRects), shrinks to 45% and fades.
// Two nested elements make the arc: outer moves on X, inner on Y with a different easing.
export function flyPill({ label, from, to, duration = 750 }) {
  const inner = h("span", { class: "fly-pill__inner" }, label);
  const outer = h("div", { class: "fly-pill", "aria-hidden": "true" }, inner);
  const sx = from.left + from.width / 2;
  const sy = from.top + from.height / 2;
  outer.style.left = `${sx}px`;
  outer.style.top = `${sy}px`;
  document.body.append(outer);

  const dx = to.left + to.width / 2 - sx;
  const dy = to.top + to.height / 2 - sy;
  const opts = { duration, fill: "forwards" };
  const x = outer.animate(
    [{ transform: "translateX(0)" }, { transform: `translateX(${dx}px)` }],
    { ...opts, easing: "cubic-bezier(.3,.6,.4,1)" });
  inner.animate(
    [
      { transform: "translateY(0) scale(1)", opacity: 1 },
      { transform: `translateY(${dy}px) scale(.45)`, opacity: 0.9, offset: 0.85 },
      { transform: `translateY(${dy}px) scale(.45)`, opacity: 0 },
    ],
    { ...opts, easing: "cubic-bezier(.55,-0.4,.8,.6)" });
  return x.finished.then(() => outer.remove());
}
