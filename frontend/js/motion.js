// Shared motion layer: scroll reveals, illustration draw-in, mouse tilt. Everything stays static under reduced motion.
import { hydrateIllustrations } from "/js/illustrations.js";

export const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

export function initMotion() {
  hydrateIllustrations();
  if (reduceMotion) return;
  document.documentElement.classList.add("motion");

  // Reveal .reveal blocks (children stagger) and draw their illustrations when they enter the screen.
  document.querySelectorAll(".reveal").forEach((r) => [...r.children].forEach((c, i) => c.style.setProperty("--i", i)));
  const seen = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (!e.isIntersecting) return;
    e.target.classList.add("in");
    seen.unobserve(e.target);
  }), { threshold: 0.15 });
  document.querySelectorAll(".reveal, [data-reveal]").forEach((el) => seen.observe(el));

  // Tilt .tilt tiles and dish photos toward a mouse pointer.
  let tilted = null;
  const untilt = () => {
    if (!tilted) return;
    tilted.classList.remove("tilting");
    tilted.style.removeProperty("--rx");
    tilted.style.removeProperty("--ry");
    tilted = null;
  };
  document.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse") return;
    const t = e.target.closest(".tilt, .dish-media");
    if (t !== tilted) untilt();
    if (!t) return;
    const b = t.getBoundingClientRect();
    t.classList.add("tilting");
    t.style.setProperty("--ry", `${((e.clientX - b.left) / b.width - 0.5) * 12}deg`);
    t.style.setProperty("--rx", `${((e.clientY - b.top) / b.height - 0.5) * -10}deg`);
    tilted = t;
  });
}

// Parallax for the photo band on app screens.
export function initRouteBand() {
  const img = document.querySelector(".route-band img");
  const note = document.querySelector(".band-note");
  if (note) requestAnimationFrame(() => requestAnimationFrame(() => note.classList.add("in")));
  if (!img || reduceMotion) return;
  let queued = false;
  addEventListener("scroll", () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; img.style.transform = `translate3d(0, ${scrollY * 0.3}px, 0)`; });
  }, { passive: true });
}
