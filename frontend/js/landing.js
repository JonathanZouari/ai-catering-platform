// Landing page: one-time intro, dish carousel, scroll reveals, and the live quote demo.
import { plateSVG } from "/js/plates.js";

const root = document.documentElement;
const intro = document.getElementById("intro");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
const EASE_IN_OUT = "cubic-bezier(0.77, 0, 0.175, 1)";
const $ = (id) => document.getElementById(id);

// ---------- Intro ----------

function finishIntro() {
  root.classList.add("is-ready");
  intro.hidden = true;
  try { sessionStorage.setItem("intro-seen", "1"); } catch {}
}

if (root.classList.contains("skip-intro") || reduceMotion) {
  finishIntro();
} else {
  // Start the page entrance while the overlay is still wiping away, so they overlap.
  const readyTimer = setTimeout(() => root.classList.add("is-ready"), 1900);
  intro.addEventListener("animationend", (e) => { if (e.target === intro) finishIntro(); });
  const skip = () => { clearTimeout(readyTimer); finishIntro(); };
  intro.addEventListener("click", skip);
  addEventListener("keydown", skip, { once: true });
}

// ---------- Dish carousel ----------
// Placeholder showcase content; real dishes come from the catalog API in Phase 2.

const dishes = [
  { kind: "hummus", seed: 11, eyebrow: "מנת הדגל", light: "חומוס", bold: "ביתי", price: 120, unit: "למגש", serves: "מגש אחד ל־10–12 אורחים",
    desc: "חומוס חלק עם גרגרים חמים, שמן זית, פפריקה ופטרוזיליה קצוצה.", tags: [["טבעוני"], ["פרווה"]],
    ingredients: ["גרגרי חומוס", "טחינה גולמית", "לימון ושום", "שמן זית", "פפריקה ופטרוזיליה"] },
  { kind: "salad", seed: 23, eyebrow: "טרי מהתנור", light: "ירקות", bold: "קלויים", price: 140, unit: "למגש", serves: "מגש אחד ל־10–12 אורחים",
    desc: "בטטה, פלפלים, קישואים וחצילים קלויים על מצע עלים, עם שומשום.", tags: [["טבעוני"], ["פרווה"]],
    ingredients: ["בטטה", "פלפל אדום וצהוב", "קישוא וחציל", "עלי בייבי", "שומשום ושמן זית"] },
  { kind: "meatballs", seed: 5, eyebrow: "מנה עיקרית", light: "קציצות", bold: "ברוטב", price: 220, unit: "למגש", serves: "מגש אחד ל־8–10 אורחים",
    desc: "קציצות בקר ברוטב עגבניות מבושל לאט, עם פטרוזיליה טרייה.", tags: [["בשרי", "meat"]],
    ingredients: ["בשר בקר טחון", "עגבניות ורסק", "בצל ושום", "פירורי לחם", "תבלינים ופטרוזיליה"] },
  { kind: "majadra", seed: 41, eyebrow: "קלאסיקה ביתית", light: "מג׳דרה", bold: "עם בצל", price: 130, unit: "למגש", serves: "מגש אחד ל־10–12 אורחים",
    desc: "אורז ועדשים בתיבול עדין, עם הר של בצל מטוגן ופריך.", tags: [["טבעוני"], ["פרווה"]],
    ingredients: ["אורז בסמטי", "עדשים חומות", "בצל מטוגן", "כמון ופלפל שחור"] },
  { kind: "salmon", seed: 17, eyebrow: "מהים", light: "סלמון", bold: "בתנור", price: 260, unit: "למגש", serves: "מגש אחד ל־6–8 אורחים",
    desc: "פילה סלמון צלוי עם לימון ושמיר, לצד תפוחי אדמה מוזהבים.", tags: [["פרווה"], ["דגים"]],
    ingredients: ["פילה סלמון", "לימון", "שמיר טרי", "תפוחי אדמה", "שמן זית ומלח ים"] },
];

const money = new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS", maximumFractionDigits: 0 });
const plate = $("plate");
const rail = $("rail");
const dots = $("dots");
const arc = $("arc");
const titleWords = [...$("dish-title").querySelectorAll(".mask > span")];
let current = 0;

rail.innerHTML = dishes.map((d, i) =>
  `<button class="rail-item" type="button" data-index="${i}" aria-label="${d.light} ${d.bold}">${plateSVG(d.kind, d.seed)}<span>${d.light} ${d.bold}</span></button>`
).join("");
dots.innerHTML = dishes.map(() => "<span></span>").join("");

function fillCard(d) {
  $("dish-eyebrow").textContent = d.eyebrow;
  $("dish-price").textContent = money.format(d.price);
  $("dish-unit").textContent = d.unit;
  $("dish-name").textContent = `${d.light} ${d.bold}`;
  $("dish-serves").textContent = d.serves;
  $("dish-desc").textContent = d.desc;
  $("dish-tags").innerHTML = d.tags.map(([t, cls = ""]) => `<span class="chip ${cls}">${t}</span>`).join("");
  $("dish-ingredients").innerHTML = d.ingredients.map((x) => `<li>${x}</li>`).join("");
  titleWords[0].textContent = d.light;
  titleWords[1].textContent = d.bold;
}

function markActive(i) {
  rail.querySelectorAll(".rail-item").forEach((b, j) => b.setAttribute("aria-current", String(i === j)));
  dots.querySelectorAll("span").forEach((s, j) => s.classList.toggle("is-active", i === j));
  // Center the active thumb inside the rail only — never scroll the page.
  const item = rail.children[i].getBoundingClientRect();
  const box = rail.getBoundingClientRect();
  rail.scrollBy({ left: item.left + item.width / 2 - (box.left + box.width / 2), behavior: reduceMotion ? "auto" : "smooth" });
}

function show(i, direction = 1) {
  if (i === current) return;
  const d = dishes[i];
  current = i;
  markActive(i);
  arc.style.transform = `rotate(${i * 38}deg)`;

  const old = plate.lastElementChild;
  plate.insertAdjacentHTML("beforeend", plateSVG(d.kind, d.seed));
  const next = plate.lastElementChild;

  if (reduceMotion) {
    old.remove();
    fillCard(d);
    return;
  }

  // Old plate spins away, new one spins in from the other side.
  old.animate(
    [{ transform: "none", opacity: 1 }, { transform: `rotate(${-50 * direction}deg) scale(0.92)`, opacity: 0 }],
    { duration: 450, easing: EASE_IN_OUT, fill: "forwards" },
  ).finished.then(() => old.remove());
  next.animate(
    [{ transform: `rotate(${80 * direction}deg) scale(0.92)`, opacity: 0 }, { transform: "none", opacity: 1 }],
    { duration: 900, delay: 150, easing: EASE_OUT, fill: "backwards" },
  );

  fillCard(d);
  titleWords.forEach((w, k) => w.animate(
    [{ transform: "translateY(105%)" }, { transform: "translateY(0)" }],
    { duration: 700, delay: 120 + k * 80, easing: EASE_OUT, fill: "backwards" },
  ));
  const body = $("card-body");
  body.classList.remove("is-swapping");
  void body.offsetWidth; // restart the CSS animation
  body.classList.add("is-swapping");
}

plate.innerHTML = plateSVG(dishes[0].kind, dishes[0].seed);
fillCard(dishes[0]);
markActive(0);

// Autoplay until the visitor takes control; pause while they're looking at the hero.
let paused = false;
let autoplay = reduceMotion ? null : setInterval(() => { if (!paused) show((current + 1) % dishes.length); }, 6000);
const hero = $("hero");
hero.addEventListener("pointerenter", () => (paused = true));
hero.addEventListener("pointerleave", () => (paused = false));
hero.addEventListener("focusin", () => (paused = true));
hero.addEventListener("focusout", () => (paused = false));
const stopAutoplay = () => { clearInterval(autoplay); autoplay = null; };

rail.addEventListener("click", (e) => {
  const item = e.target.closest(".rail-item");
  if (!item) return;
  stopAutoplay();
  const i = Number(item.dataset.index);
  show(i, i > current ? 1 : -1);
});
document.querySelectorAll(".rail-arrow").forEach((btn) => btn.addEventListener("click", () => {
  stopAutoplay();
  const step = Number(btn.dataset.step);
  show((current + step + dishes.length) % dishes.length, step);
}));

// Card tabs
const tabs = [...document.querySelectorAll(".card-tabs [role=tab]")];
function selectTab(tab) {
  tabs.forEach((t) => {
    const on = t === tab;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    $(t.getAttribute("aria-controls")).hidden = !on;
  });
}
tabs.forEach((t, i) => {
  t.addEventListener("click", () => selectTab(t));
  t.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    const next = tabs[(i + 1) % tabs.length];
    selectTab(next);
    next.focus();
  });
});

// ---------- Scroll reveals ----------

const observer = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    entry.target.classList.add("is-visible");
    observer.unobserve(entry.target);
  }
}, { threshold: 0.25 });
document.querySelectorAll("[data-reveal]").forEach((el) => observer.observe(el));

// ---------- Quote demo ----------
// Demo only: the real flow sends the approval to the backend, which recalculates the price.

const totalEl = $("total");
const proposal = $("proposal");
const result = $("proposal-result");
totalEl.textContent = money.format(1900);

function countTo(from, to, duration = 700) {
  if (reduceMotion) { totalEl.textContent = money.format(to); return; }
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 4);
    totalEl.textContent = money.format(Math.round(from + (to - from) * eased));
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

proposal.addEventListener("click", (e) => {
  const action = e.target.closest("[data-action]")?.dataset.action;
  if (!action) return;
  proposal.classList.add("is-done");

  if (action === "approve") {
    const line = document.createElement("li");
    line.className = "line is-new";
    line.innerHTML = '<span class="line-name">מג׳דרה<span class="tag">טבעוני</span></span><span class="line-qty">2 מגשים × ₪130</span><span class="line-price">₪260</span>';
    $("lines").append(line);
    countTo(1900, 2160);
    result.textContent = "השינוי אושר והמחיר עודכן.";
  } else {
    result.textContent = "ההצעה נדחתה. ההזמנה לא השתנתה.";
  }
});
