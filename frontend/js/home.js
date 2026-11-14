// Landing page depth layer: the hero table (round plates that drift with scroll and pointer), word-by-word
// headline, painted accents that drift on scroll, scroll-driven 3D menu ring.
import { initMotion, reduceMotion as reduce } from "/js/motion.js";

initMotion();

const $ = (s) => document.querySelector(s);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

const hero = $("#hero");
const plates = [...document.querySelectorAll(".plate")], paints = [...document.querySelectorAll(".paint")];
plates.forEach((p, i) => p.style.setProperty("--i", i));
paints.forEach((p, i) => { p.style.setProperty("--i", i); p.pageTop = p.getBoundingClientRect().top + scrollY; });
const ring = $("#ring"), cards = [...ring.children], ringSec = $("#ring-sec"), ringNow = $("#ring-now");
const N = cards.length, STEP = 360 / N;

const h1 = $(".hero h1");
h1.innerHTML = h1.textContent.trim().split(/\s+/).map((w, i) => `<span class="w" style="--i:${i}">${w}</span>`).join(" ");
setTimeout(() => hero.classList.add("in"), 300);

let manual = 0, cur = 0, front = -1, px = 0, py = 0, cpx = 0, cpy = 0, queued = false;
const kick = () => { if (!queued) { queued = true; requestAnimationFrame(frame); } };

function frame() {
  queued = false;
  const y = scrollY, H = innerHeight;
  if (!reduce) {
    cpx += (px - cpx) * 0.08;
    cpy += (py - cpy) * 0.08;
    plates.forEach((p, i) => {
      const d = Number(p.dataset.depth);
      p.style.setProperty("--sy", `${-y * d * 0.1}px`);
      p.style.setProperty("--px", `${cpx * d * -22}px`);
      p.style.setProperty("--py", `${cpy * d * -18}px`);
      p.style.setProperty("--rot", `${y * 0.05 * (i % 2 ? -1 : 1)}deg`);
    });
    paints.forEach((p) => p.style.setProperty("--sy", `${clamp((p.pageTop - y - H / 2) * -0.08, -60, 60)}px`));
    if (Math.abs(px - cpx) + Math.abs(py - cpy) > 0.002) kick();
  }

  // The ring turns once while its 300vh section scrolls past; the arrow buttons add a manual offset.
  const rr = ringSec.getBoundingClientRect();
  const rp = reduce ? 0 : clamp(-rr.top / Math.max(1, rr.height - H), 0, 1);
  const target = -rp * (360 - STEP) + manual;
  cur = reduce ? target : cur + (target - cur) * 0.12;
  if (Math.abs(target - cur) > 0.05) kick();
  const r = (cards[0].offsetWidth / 2) / Math.tan(Math.PI / N) * 1.18;
  ring.style.transform = `translateZ(${-r}px) rotateY(${cur}deg)`;
  let best = 0, bestCos = -2;
  cards.forEach((c, i) => {
    const facing = Math.cos(((i * STEP + cur) * Math.PI) / 180);
    c.style.transform = `rotateY(${i * STEP}deg) translateZ(${r}px)`;
    c.style.opacity = String(0.22 + 0.78 * Math.max(0, facing));
    c.querySelector("a").tabIndex = facing > 0.5 ? 0 : -1;
    if (facing > bestCos) { bestCos = facing; best = i; }
  });
  if (best !== front) {
    cards.forEach((c, i) => c.classList.toggle("front", i === best));
    ringNow.textContent = cards[best].textContent.trim();
    front = best;
  }
}

$("#ring-next").addEventListener("click", () => { manual -= STEP; kick(); });
$("#ring-prev").addEventListener("click", () => { manual += STEP; kick(); });
hero.addEventListener("pointermove", (e) => { px = e.clientX / innerWidth - 0.5; py = e.clientY / innerHeight - 0.5; kick(); });
hero.addEventListener("pointerleave", () => { px = py = 0; kick(); });
addEventListener("scroll", kick, { passive: true });
addEventListener("resize", kick);
kick();

// Kashrut certificate from the owner's settings (OPEN_DECISIONS #9); the footer stays as is if missing.
fetch("/api/catalog/business")
  .then((r) => (r.ok ? r.json() : null))
  .then((b) => {
    const line = document.getElementById("kashrut-line");
    if (!b?.kashrut_certificate || !line) return;
    line.textContent = `כשר · ${b.kashrut_certificate}`;
    line.hidden = false;
  })
  .catch(() => {});
