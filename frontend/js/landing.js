import { DISHES, DISH_BY_ID, img, money, balance } from "./data.js";
import { createTable } from "./table.js";

const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (s) => document.querySelector(s);

// --- hero: a table that sets itself, sized by the slider ---------------------
const HERO_MENU = ["hummus", "eggplant", "tabbouleh", "chicken", "salmon", "potatoes", "challah", "fruit"];
const hero = createTable($("#hero-table"), { interactive: false });
const slider = $("#hero-guests");
const out = $("#hero-guests-out");
let shown = reduce ? HERO_MENU.length : 0;

function heroGuests() {
  const n = Number(slider.value);
  const children = Math.round(n * 0.25);
  return { adults: n - children, children };
}

function renderHero() {
  const g = heroGuests();
  const items = balance(Object.fromEntries(HERO_MENU.slice(0, shown).map((id) => [id, 1])), g);
  hero.update({ ...g, items });
  out.textContent = slider.value;
  slider.style.setProperty("--fill", `${((slider.value - slider.min) / (slider.max - slider.min)) * 100}%`);
  const trays = Object.values(items).reduce((a, b) => a + b, 0);
  const total = Object.entries(items).reduce((s, [id, q]) => s + q * DISH_BY_ID[id].price, 0);
  $("[data-hero=trays]").textContent = trays;
  $("[data-hero=total]").textContent = money(total);
}

slider.addEventListener("input", renderHero);
renderHero();
if (!reduce) {
  const tick = () => {
    if (shown >= HERO_MENU.length) return;
    shown++;
    renderHero();
    setTimeout(tick, 420);
  };
  setTimeout(tick, 700);
}

// the CTA carries the guest count into the order screen
$("[data-cta]").addEventListener("click", () => {
  try {
    const key = "yumi.order.v1";
    const s = JSON.parse(localStorage.getItem(key) || "null");
    const g = heroGuests();
    if (!s || (s.status === "draft" && !Object.keys(s.items || {}).length)) {
      localStorage.setItem(key, JSON.stringify({ ...(s || {}), event: { ...(s?.event || { type: "יום הולדת", notes: "", fulfillment: "delivery", zone: "center", address: "", date: "", slot: "" }), ...g }, items: s?.items || {}, status: "draft", version: 1 }));
    }
  } catch { /* storage unavailable */ }
});

// --- story: one table, four states ---------------------------------------------
const story = $("#how");
const storyTable = createTable($("#story-table"), { interactive: false });
const STORY_GUESTS = { adults: 40, children: 14 };
const STORY_ITEMS = { hummus: 3, eggplant: 4, chicken: 5, potatoes: 4, challah: 4 };
const STATES = [
  { items: {}, proposal: null },
  { items: STORY_ITEMS, proposal: null },
  { items: STORY_ITEMS, proposal: { changes: [{ id: "schnitzel", from: 0, to: 2 }, { id: "chicken", from: 5, to: 4 }] } },
  { items: { ...STORY_ITEMS, chicken: 4, schnitzel: 2 }, proposal: null },
];
let current = -1;
let countTimer;
function setStage(i) {
  if (i === current) return;
  const from = current;
  current = i;
  story.dataset.stage = String(i);
  document.querySelectorAll("[data-story]").forEach((li) => li.classList.toggle("is-active", Number(li.dataset.story) === i));
  clearInterval(countTimer);
  // step 1 seats the guests one by one; later steps start with everyone seated
  if (i === 0 && from <= 0 && !reduce) {
    const total = STORY_GUESTS.adults + STORY_GUESTS.children;
    let n = 0;
    countTimer = setInterval(() => {
      n = Math.min(total, n + 2);
      const kids = Math.max(0, n - STORY_GUESTS.adults);
      storyTable.update({ adults: n - kids, children: kids, ...STATES[0] });
      if (n >= total) clearInterval(countTimer);
    }, 28);
    return;
  }
  storyTable.update({ ...STORY_GUESTS, ...STATES[i] });
}
setStage(0);
const steps = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) setStage(Number(e.target.dataset.story));
}, { rootMargin: "-45% 0px -45% 0px" });
document.querySelectorAll("[data-story]").forEach((li) => steps.observe(li));

// --- bento: a quiet table, half the seats children, showing the half-portion rule
const bento = createTable(document.querySelector("#bento-table"), { interactive: false });
bento.update({ adults: 24, children: 16, items: balance({ hummus: 1, tabbouleh: 1, schnitzel: 1, chicken: 1, potatoes: 1, fruit: 1 }, { adults: 24, children: 16 }), proposal: null });

// --- kitchen rail ----------------------------------------------------------------------
const rail = $("[data-bind=rail]");
rail.innerHTML = DISHES.map((d) => `
  <li>
    <img src="${img(d.id)}" alt="${d.name}, מבט מלמעלה" loading="lazy" width="300" height="300">
    <h3>${d.name}</h3>
    <p>${d.blurb}</p>
    <span class="price num">${money(d.price)} ל${d.unit}</span>
  </li>`).join("");
document.querySelectorAll("[data-rail]").forEach((b) => b.addEventListener("click", () => {
  rail.scrollBy({ left: Number(b.dataset.rail) * rail.clientWidth * 0.8, behavior: reduce ? "auto" : "smooth" });
}));

// --- reveal on scroll ---------------------------------------------------------------------
const io = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); }
}, { threshold: 0.15 });
document.querySelectorAll(".kitchen__head, .rail, .bento__cell, .closing > *, .story__title").forEach((el) => { el.classList.add("reveal"); io.observe(el); });
