// Customer catalog prototype: fictional demo dishes, client-side selection only.
// Nothing here is sent to the backend; totals are illustrative, not quotations.

import { CATEGORIES, DEMO_DISHES } from "./demo-dishes.js";
import { SCENES } from "./kitchen-scenes.js";
import { initKitchenPreview } from "./kitchen-preview.js";
import { initHoverPreview } from "./hover-preview.js";
import { isSoundOn, setSoundOn, onSoundChange } from "./sound-pref.js";

const money = new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS", maximumFractionDigits: 0 });
const byId = new Map(DEMO_DISHES.map((d) => [d.id, d]));
const selection = new Map(); // dishId -> qty
let activeCategory = "all";

const chipsEl = document.getElementById("category-chips");
const gridEl = document.getElementById("dish-grid");
const linesEl = document.getElementById("selection-lines");
const totalEl = document.getElementById("selection-total");
const barCountEl = document.getElementById("bar-count");
const barTotalEl = document.getElementById("bar-total");
const navCountEl = document.getElementById("nav-count");
const dialogEl = document.getElementById("kitchen-preview");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const getQty = (id) => selection.get(id) ?? 0;

function setQty(id, qty) {
  if (qty > 0) selection.set(id, qty);
  else selection.delete(id);
  renderActions(id);
  renderSummary();
}

const preview = initKitchenPreview({ onAdd: (id) => setQty(id, getQty(id) + 1), getQty });
const hover = initHoverPreview({
  grid: gridEl,
  getDish: (id) => byId.get(id),
  onOpen: (dish, trigger) => openPreview(dish, trigger),
  isBlocked: () => dialogEl.open, // never two players at once
});

function openPreview(dish, trigger) {
  hover.stop(); // never two players at once
  preview.open(dish, trigger);
  syncHero();
}

// ---- "Enable kitchen sounds": explicit consent by click, for this page view; click again to mute ----
const soundSwitch = document.getElementById("kitchen-sound");
function renderSoundSwitch(on) {
  soundSwitch.setAttribute("aria-pressed", String(on));
  soundSwitch.querySelector(".sound-switch__label").textContent = on ? "השתקת צלילי מטבח" : "הפעל צלילי מטבח";
}
soundSwitch.addEventListener("click", () => setSoundOn(!isSoundOn()));
onSoundChange(renderSoundSwitch);
renderSoundSwitch(isSoundOn());

// Short, truthful status (screen readers + a quiet visible note under the nav).
const soundStatus = document.getElementById("sound-status");
let statusTimer = 0;
function announce(text) {
  clearTimeout(statusTimer);
  soundStatus.textContent = text;
  statusTimer = setTimeout(() => (soundStatus.textContent = ""), 7000);
}
onSoundChange((on, reason) => {
  if (reason === "blocked") announce("הדפדפן לא אפשר השמעת קול, ולכן הסרטון ממשיך ללא קול. אפשר לנסות שוב בלחיצה על „הפעל צלילי מטבח”.");
  else announce(on ? "צלילי המטבח פעילים. אפשר להשתיק בכל רגע." : "צלילי המטבח כבויים.");
});

// ---- Hero entry: explicit choice between "with kitchen sounds" and "without" ----
// Only these clicks (and the sound buttons) change the preference — never hover,
// scroll or unrelated clicks. The click is the user gesture browsers require;
// whether a later clip is actually audible is still up to the browser, and a
// refusal falls back to muted truthfully (see "blocked" above).
const menuTitle = document.getElementById("menu-title");
function goToMenu() {
  // Focus first (without scrolling), then scroll: focusing after a smooth scroll
  // starts would cancel it. Keyboard and screen-reader users land on the menu.
  menuTitle.focus({ preventScroll: true });
  document.getElementById("menu").scrollIntoView({ behavior: reducedMotion.matches ? "auto" : "smooth" });
}
document.getElementById("enter-with-sound").addEventListener("click", () => {
  setSoundOn(true);
  goToMenu();
});
document.getElementById("enter-silent").addEventListener("click", (e) => {
  e.preventDefault();
  setSoundOn(false);
  goToMenu();
});

// ---- Hero: muted ambient loop (never audible) ----
// Plays only while on screen, the tab is visible, no dialog is open and the
// visitor has not paused it. Reduced motion: a still plated frame, no loop.
const heroVideo = document.querySelector(".hero__video");
const heroToggle = document.getElementById("hero-toggle");
let heroOnScreen = false;
let heroUserPaused = false;

function syncHero() {
  if (!heroVideo.isConnected || reducedMotion.matches) return;
  const shouldPlay = heroOnScreen && !document.hidden && !dialogEl.open && !heroUserPaused;
  if (shouldPlay && heroVideo.paused) heroVideo.play().catch(() => {});
  else if (!shouldPlay && !heroVideo.paused) heroVideo.pause();
  heroToggle.textContent = heroUserPaused ? "הפעלת הווידאו" : "השהיית הווידאו";
}
heroVideo.addEventListener("loadeddata", () => heroVideo.classList.add("is-ready"), { once: true });
heroVideo.addEventListener("error", () => heroVideo.remove(), { once: true });
if (reducedMotion.matches) {
  heroVideo.removeAttribute("loop");
  heroVideo.addEventListener("loadedmetadata", () => (heroVideo.currentTime = Math.max(0, heroVideo.duration - 0.5)), { once: true });
} else {
  heroToggle.hidden = false;
  heroToggle.addEventListener("click", () => {
    heroUserPaused = !heroUserPaused;
    syncHero();
  });
  new IntersectionObserver(([entry]) => {
    heroOnScreen = entry.isIntersecting;
    syncHero();
  }).observe(heroVideo);
  document.addEventListener("visibilitychange", syncHero);
  dialogEl.addEventListener("close", syncHero);
}

// ---- Category filters ----
function renderChips() {
  chipsEl.innerHTML = CATEGORIES.map(
    (c) => `<button type="button" class="filter" data-cat="${c.id}" aria-pressed="${c.id === activeCategory}">${c.label}</button>`,
  ).join("");
}
chipsEl.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-cat]");
  if (!btn) return;
  activeCategory = btn.dataset.cat;
  renderChips();
  renderGrid();
});

// ---- Dish rows (no media tiles: the clip appears only on name hover/tap) ----
function cardHtml(d) {
  const method = d.prep ? SCENES[d.prep.type]?.label : "";
  const name = d.video
    ? `<button type="button" class="dish-name-trigger" data-preview="${d.id}" aria-describedby="cue-${d.id}">${d.name}</button>`
    : d.name;
  const cue = d.video
    ? `<span class="cue-dot" aria-hidden="true"></span>וידאו הכנה · נוצר ב־AI להמחשה`
    : `ללא סרטון הכנה כרגע`;
  return `<article class="dish-card${d.video ? " has-video" : ""}" data-dish="${d.id}" aria-labelledby="t-${d.id}">
    <div class="dish-card__main">
      <h4 id="t-${d.id}" class="dish-card__title">${name}</h4>
      <p class="dish-card__cue" id="cue-${d.id}">${method ? `${method} · ` : ""}${cue}</p>
      <p class="dish-card__desc">${d.description}</p>
      <p class="dish-card__facts">כשרות ואלרגנים: טרם נמסר מידע</p>
    </div>
    <div class="dish-card__aside">
      <p class="dish-price"><span class="dish-price__amount">${money.format(d.price)}</span><span class="dish-price__unit">${d.unit} · מחיר לדוגמה</span></p>
      <div class="dish-card__actions" data-actions="${d.id}"></div>
    </div>
  </article>`;
}

function actionsHtml(d) {
  const qty = getQty(d.id);
  if (!qty) {
    return `<button type="button" class="btn btn--select" data-add="${d.id}">הוספה לבחירה<span class="visually-hidden">: ${d.name}</span></button>`;
  }
  return `<div class="stepper" role="group" aria-label="כמות ${d.name}">
    <button type="button" class="stepper__btn" data-dec="${d.id}" aria-label="הפחתה">−</button>
    <output class="stepper__qty">${qty}</output>
    <button type="button" class="stepper__btn" data-inc="${d.id}" aria-label="הוספה">+</button>
  </div>`;
}

// Re-renders a row's add/stepper controls, keeping keyboard focus in place.
function renderActions(id) {
  const el = gridEl.querySelector(`[data-actions="${id}"]`);
  if (!el) return;
  const had = el.contains(document.activeElement) ? document.activeElement.dataset : null;
  el.innerHTML = actionsHtml(byId.get(id));
  if (!had) return;
  const same = "inc" in had ? "[data-inc]" : "dec" in had ? "[data-dec]" : "[data-inc]";
  (el.querySelector(same) ?? el.querySelector("button"))?.focus();
}

// Grouped by category, each with its own heading, for a calmer menu rhythm.
function renderGrid() {
  hover.stop();
  const groups = CATEGORIES.filter((c) => c.id !== "all" && (activeCategory === "all" || c.id === activeCategory))
    .map((c) => ({ ...c, dishes: DEMO_DISHES.filter((d) => d.category === c.id) }))
    .filter((g) => g.dishes.length);
  gridEl.innerHTML = groups
    .map(
      (g) => `<section class="menu-group" aria-labelledby="g-${g.id}">
        <h3 class="menu-group__title" id="g-${g.id}">${g.label} <span class="menu-group__count">${g.dishes.length}</span></h3>
        ${g.dishes.map(cardHtml).join("")}
      </section>`,
    )
    .join("");
  groups.forEach((g) => g.dishes.forEach((d) => renderActions(d.id)));
}

gridEl.addEventListener("click", (e) => {
  const t = e.target.closest("button");
  if (!t) return;
  const { preview: pid, add, inc, dec } = t.dataset;
  if (pid) openPreview(byId.get(pid), t);
  else if (add) setQty(add, 1);
  else if (inc) setQty(inc, getQty(inc) + 1);
  else if (dec) setQty(dec, getQty(dec) - 1);
});

// ---- Selection summary (illustrative only) ----
function renderSummary() {
  let total = 0;
  let count = 0;
  const lines = [];
  for (const [id, qty] of selection) {
    const d = byId.get(id);
    const line = d.price * qty;
    total += line;
    count += qty;
    lines.push(`<li><span>${d.name} × ${qty}</span><span>${money.format(line)}</span></li>`);
  }
  linesEl.innerHTML = lines.length ? lines.join("") : `<li class="summary__empty">בחרו מנות מהתפריט, והן יופיעו כאן.</li>`;
  totalEl.textContent = money.format(total);
  barCountEl.textContent = count ? `${count} פריטים` : "לא נבחרו פריטים";
  barTotalEl.textContent = money.format(total);
  navCountEl.textContent = String(count);
  document.body.classList.toggle("has-selection", count > 0); // desktop sticky summary
}

renderChips();
renderGrid();
renderSummary();
