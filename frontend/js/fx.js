// Shared motion layer. All effects are opacity/transform only and are skipped under reduced motion.
//   [data-reveal]        fade/rise in once on scroll
//   [data-crossfade=ms]  stack of .fx-slide images that cross-fade slowly (visible only)
//   [data-parallax=k]    gentle vertical drift tied to scroll
//   [data-stage]         crossfade stack driven by [data-stage-trigger=key] sections and cb:dish events
//   [data-spot]          soft light that follows the pointer (--mx / --my)
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

export function setSlide(stack, key) {
  const slides = [...stack.querySelectorAll(".fx-slide")];
  const next = slides.find((s) => s.dataset.key === key);
  if (!next || next.classList.contains("is-active")) return;
  slides.forEach((s) => s.classList.toggle("is-active", s === next));
  const cap = document.querySelector(`[data-stage-caption="${stack.id}"]`);
  if (cap) cap.textContent = next.dataset.caption || "";
}

function reveal() {
  const els = document.querySelectorAll("[data-reveal]");
  if (reduced || !("IntersectionObserver" in window)) return els.forEach((e) => e.classList.add("is-in"));
  const io = new IntersectionObserver((entries) => entries.forEach((en) => {
    if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); }
  }), { rootMargin: "0px 0px -10% 0px", threshold: 0.12 });
  els.forEach((e) => io.observe(e));
}

function crossfades() {
  document.querySelectorAll("[data-crossfade]").forEach((stack) => {
    const slides = [...stack.querySelectorAll(".fx-slide")];
    if (slides.length < 2 || reduced) return;
    const every = Number(stack.dataset.crossfade) || 7000;
    let i = 0, timer = null, visible = false;
    const tick = () => { i = (i + 1) % slides.length; setSlide(stack, slides[i].dataset.key); };
    const start = () => { timer ??= setInterval(tick, every); };
    const stop = () => { clearInterval(timer); timer = null; };
    new IntersectionObserver(([en]) => { visible = en.isIntersecting; visible ? start() : stop(); }).observe(stack);
    document.addEventListener("visibilitychange", () => (document.hidden ? stop() : visible && start()));
  });
}

function parallax() {
  const els = [...document.querySelectorAll("[data-parallax]")];
  if (reduced || !els.length) return;
  let queued = false;
  const update = () => {
    queued = false;
    const vh = innerHeight;
    for (const el of els) {
      const r = el.getBoundingClientRect();
      if (r.bottom < -100 || r.top > vh + 100) continue;
      el.style.translate = `0 ${((r.top + r.height / 2 - vh / 2) * -Number(el.dataset.parallax)).toFixed(1)}px`;
    }
  };
  addEventListener("scroll", () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, { passive: true });
  update();
}

function stages() {
  const stage = document.querySelector("[data-stage]");
  if (!stage) return;
  if (!reduced && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => entries.forEach((en) => {
      if (en.isIntersecting) setSlide(stage, en.target.dataset.stageTrigger);
    }), { rootMargin: "-45% 0px -45% 0px" });
    document.querySelectorAll("[data-stage-trigger]").forEach((t) => io.observe(t));
  }
  document.addEventListener("cb:dish", (e) => setSlide(stage, e.detail.img));
}

function spots() {
  if (reduced || !matchMedia("(hover: hover)").matches) return;
  document.querySelectorAll("[data-spot]").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
      el.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
    });
  });
}

export function initFx() {
  document.documentElement.classList.add("fx");
  reveal(); crossfades(); parallax(); stages(); spots();
}
