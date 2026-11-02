// Shared catering logic for the three design concepts: sample data, transparent demo pricing,
// and the interactive builder (packages, dishes, guests, live summary, quote request).
// Markup hooks: [data-packages] [data-dishes] [data-guests] [data-summary] [data-quote-form]
// [data-total] (any live total) [data-count] (selected dish count).

const STORE = "catering-demo-v1";

export const SERVICE_FEE = 400; // fixed delivery / setup, demo value
export const DISCOUNTS = [
  { from: 100, rate: 0.08 },
  { from: 50, rate: 0.05 },
];

export const PACKAGES = [
  { id: "brunch", name: "בוקר חגיגי", base: 38, img: "brunch", dishes: ["b1", "b2", "b3", "d2"],
    desc: "שולחן בוקר ארוך ושופע — לימי הולדת, פגישות בוקר וחגיגות משפחתיות." },
  { id: "cocktail", name: "קוקטייל קליל", base: 30, img: "pizza", dishes: ["s2", "s3", "m1", "m4", "d3"],
    desc: "ביסים עדינים לעמידה, לשיחה ולצלצול כוסות — בלי להרגיש כבדים." },
  { id: "dinner", name: "ערב מלא", base: 58, img: "pasta", dishes: ["s1", "m2", "m3", "d1"],
    desc: "ארוחה מוגשת מראשונה ועד קינוח, עם צוות הגשה לאורך הערב." },
];

export const CATS = [
  { id: "brunch", name: "בוקר ושולחן פתוח" },
  { id: "starters", name: "ראשונות וסלטים" },
  { id: "mains", name: "עיקריות" },
  { id: "sweets", name: "קינוחים" },
];

export const DISHES = [
  { id: "b1", cat: "brunch", name: "קערות שיבולת שועל ופירות", price: 18, img: "brunch", desc: "שיבולת שועל חמה, פירות יער, תפוז ופרחי מאכל." },
  { id: "b2", cat: "brunch", name: "וופל ביתי עם חלת דבש", price: 22, img: "brunch", desc: "וופל פריך, דבש גולמי ופירות יער." },
  { id: "b3", cat: "brunch", name: "יוגורט, גרנולה ופירות עונה", price: 16, desc: "יוגורט עבה, זרעים קלויים ופירות העונה." },
  { id: "s1", cat: "starters", name: "סלט עלים, שרי ופסטו", price: 14, desc: "עלים רכים, עגבניות שרי ורוטב פסטו עדין." },
  { id: "s2", cat: "starters", name: "דיפים ולחם טרי", price: 16, desc: "שלושה ממרחים עונתיים עם לחם שנאפה באותו בוקר." },
  { id: "s3", cat: "starters", name: "מיני קישים ירוקים", price: 15, desc: "בצק פריך, תרד, עשבי תיבול וגבינה." },
  { id: "m1", cat: "mains", name: "פיצה מרגריטה על בצק מחמצת", price: 26, img: "pizza", desc: "עגבניות שרי, מוצרלה ועלי מרווה, מוגשת פרוסה." },
  { id: "m2", cat: "mains", name: "פרפלה בפסטו ועגבניות שרי", price: 28, img: "pasta", desc: "פסטה בצורת פפיון, פסטו טרי, שרי חצויות ועלים." },
  { id: "m3", cat: "mains", name: "מגש ירקות קלויים וגבינות", price: 24, desc: "ירקות עונה קלויים, גבינות רכות ושמן זית." },
  { id: "m4", cat: "mains", name: "פוקאצ'ה עשבי תיבול", price: 12, desc: "שמן זית, מלח גס ורוזמרין." },
  { id: "d1", cat: "sweets", name: "קרפ קצפת ופירות יער", price: 20, img: "crepes", desc: "קרפ דק, קצפת וניל, תות ופטל." },
  { id: "d2", cat: "sweets", name: "פנקייק ריקוטה, פטל ונענע", price: 22, img: "pancakes", desc: "פנקייק אוורירי, אבקת סוכר, פטל ונענע טרייה." },
  { id: "d3", cat: "sweets", name: "מיני טארט לימון", price: 14, desc: "בצק חמאה פריך וקרם לימון חמצמץ." },
];

export const EVENT_TYPES = ["יום הולדת", "אירוע חברה", "אירוסין / חתונה", "ברית / בר-בת מצווה", "אירוע פרטי אחר"];

const fmt = new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS", maximumFractionDigits: 0 });
export const money = (n) => fmt.format(n);
export const imgUrl = (name, w = 800) => `/assets/img/${name}-${w}.webp`;
const byId = (list, id) => list.find((x) => x.id === id);

/** Transparent demo pricing: guests × (package + dishes) + fixed fee, minus a volume discount. */
export function quote({ pkgId, guests, dishIds }) {
  const pkg = byId(PACKAGES, pkgId);
  const dishes = dishIds.map((id) => byId(DISHES, id)).filter(Boolean);
  const perDishes = dishes.reduce((s, d) => s + d.price, 0);
  const subtotal = guests * (pkg.base + perDishes);
  const rate = (DISCOUNTS.find((t) => guests >= t.from) ?? { rate: 0 }).rate;
  const discount = Math.round(subtotal * rate);
  const total = subtotal - discount + SERVICE_FEE;
  return { pkg, dishes, perDishes, subtotal, rate, discount, fee: SERVICE_FEE, total, perGuest: Math.round(total / guests) };
}

function load() {
  const fallback = { pkgId: PACKAGES[0].id, guests: 30, dishIds: [...PACKAGES[0].dishes] };
  try {
    const s = JSON.parse(localStorage.getItem(STORE));
    if (s && byId(PACKAGES, s.pkgId) && Number.isInteger(s.guests) && Array.isArray(s.dishIds)) {
      return { ...s, guests: clampGuests(s.guests), dishIds: s.dishIds.filter((id) => byId(DISHES, id)) };
    }
  } catch { /* storage unavailable or corrupt: use defaults */ }
  return fallback;
}
const save = (s) => { try { localStorage.setItem(STORE, JSON.stringify(s)); } catch { /* ignore */ } };
const clampGuests = (n) => Math.min(300, Math.max(10, Math.round(n) || 10));
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

function tween(el, to) {
  const from = Number(el.dataset.v ?? to);
  el.dataset.v = to;
  if (reduced || from === to) { el.textContent = money(to); return; }
  const t0 = performance.now();
  const step = (t) => {
    const k = Math.min(1, (t - t0) / 350);
    el.textContent = money(Math.round(from + (to - from) * (1 - (1 - k) ** 3)));
    if (k < 1 && Number(el.dataset.v) === to) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export function initBuilder(root = document) {
  const state = load();
  const $ = (sel) => root.querySelector(sel);
  const mounts = {
    pkgs: $("[data-packages]"), dishes: $("[data-dishes]"), guests: $("[data-guests]"),
    summary: $("[data-summary]"), form: $("[data-quote-form]"),
  };
  const announce = root.querySelector("[data-announce]");
  const say = (msg) => { if (announce) announce.textContent = msg; };

  // ---- packages (native radios: arrow-key navigation for free)
  mounts.pkgs.innerHTML = `<fieldset class="cb-packages"><legend class="sr-only">בחירת חבילה</legend>${PACKAGES.map((p) => `
    <label class="cb-pkg" data-id="${p.id}">
      <input class="sr-only" type="radio" name="pkg" value="${p.id}">
      <span class="cb-pkg__img"><img src="${imgUrl(p.img)}" alt="" loading="lazy" decoding="async"></span>
      <span class="cb-pkg__body">
        <span class="cb-pkg__name">${p.name}</span>
        <span class="cb-pkg__desc">${p.desc}</span>
        <span class="cb-pkg__price">החל מ-${money(p.base)} <small>לסועד</small></span>
        <span class="cb-pkg__state" aria-hidden="true">נבחרה ✓</span>
      </span>
    </label>`).join("")}</fieldset>`;

  // ---- dishes
  mounts.dishes.innerHTML = CATS.map((c) => `
    <section class="cb-cat" aria-labelledby="cat-${c.id}">
      <h3 class="cb-cat__title" id="cat-${c.id}">${c.name}</h3>
      <ul class="cb-dishes">${DISHES.filter((d) => d.cat === c.id).map((d) => `
        <li><button type="button" class="cb-dish${d.img ? " has-img" : ""}" data-id="${d.id}" aria-pressed="false">
          ${d.img ? `<span class="cb-dish__img"><img src="${imgUrl(d.img)}" alt="" loading="lazy" decoding="async"></span>` : ""}
          <span class="cb-dish__text"><span class="cb-dish__name">${d.name}</span><span class="cb-dish__desc">${d.desc}</span></span>
          <span class="cb-dish__price">${money(d.price)}<small>לסועד</small></span>
          <span class="cb-dish__mark" aria-hidden="true"></span>
        </button></li>`).join("")}</ul>
    </section>`).join("");

  // ---- guests
  mounts.guests.innerHTML = `
    <div class="cb-guests">
      <label class="cb-guests__label" for="cb-guests-num">מספר אורחים</label>
      <div class="cb-guests__stepper">
        <button type="button" data-step="-5" aria-label="הפחת 5 אורחים">−</button>
        <input id="cb-guests-num" type="number" inputmode="numeric" min="10" max="300" step="1">
        <button type="button" data-step="5" aria-label="הוסף 5 אורחים">+</button>
      </div>
      <input class="cb-guests__range" type="range" min="10" max="300" step="5" aria-label="מספר אורחים — סרגל">
      <p class="cb-guests__hint">מ-50 אורחים — הנחת כמות של 5%, מ-100 — 8%.</p>
    </div>`;
  const num = $("#cb-guests-num"), range = $(".cb-guests__range");

  // ---- summary
  mounts.summary.innerHTML = `
    <div class="cb-sum">
      <h3 class="cb-sum__title">הסיכום שלך</h3>
      <p class="cb-sum__pkg"></p>
      <ul class="cb-sum__lines"></ul>
      <p class="cb-sum__empty">עוד לא נבחרו מנות — הוסיפו מהתפריט.</p>
      <dl class="cb-sum__break"></dl>
      <p class="cb-sum__total"><span>הערכת מחיר</span><strong data-total aria-live="polite"></strong></p>
      <p class="cb-sum__per"></p>
      <p class="cb-sum__note">הערכה בלבד, על בסיס תמחור דוגמה — המחיר הסופי יאושר בהצעה.</p>
      <details class="cb-sum__how"><summary>איך המחיר מחושב?</summary>
        <p>(מחיר חבילה + סכום המנות שנבחרו) × מספר אורחים, פחות הנחת כמות, ועוד ${money(SERVICE_FEE)} משלוח והקמה.</p></details>
      <a class="btn cb-sum__cta" href="#quote">לבקשת הצעת מחיר</a>
      <button type="button" class="cb-sum__clear">נקה בחירת מנות</button>
    </div>`;

  function render() {
    const q = quote(state);
    mounts.pkgs.querySelectorAll(".cb-pkg").forEach((el) => {
      const on = el.dataset.id === state.pkgId;
      el.classList.toggle("is-on", on);
      el.querySelector("input").checked = on;
    });
    mounts.dishes.querySelectorAll(".cb-dish").forEach((el) => {
      const on = state.dishIds.includes(el.dataset.id);
      el.setAttribute("aria-pressed", on);
      el.classList.toggle("is-on", on);
    });
    if (document.activeElement !== num) num.value = state.guests;
    range.value = state.guests;
    const s = mounts.summary;
    s.querySelector(".cb-sum__pkg").textContent = `חבילת ${q.pkg.name} · ${state.guests} אורחים`;
    s.querySelector(".cb-sum__lines").innerHTML = q.dishes.map((d) => `
      <li><span>${d.name}</span><span class="cb-sum__amt">${money(d.price * state.guests)}</span>
      <button type="button" data-remove="${d.id}" aria-label="הסר ${d.name}">×</button></li>`).join("");
    s.querySelector(".cb-sum__empty").hidden = q.dishes.length > 0;
    const rows = [
      [`חבילה (${money(q.pkg.base)} × ${state.guests})`, money(q.pkg.base * state.guests)],
      [`מנות (${money(q.perDishes)} × ${state.guests})`, money(q.perDishes * state.guests)],
      q.discount ? [`הנחת כמות ${Math.round(q.rate * 100)}%`, "−" + money(q.discount)] : null,
      ["משלוח והקמה", money(q.fee)],
    ].filter(Boolean);
    s.querySelector(".cb-sum__break").innerHTML = rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
    s.querySelector(".cb-sum__per").textContent = `כ-${money(q.perGuest)} לסועד, כולל הכל`;
    root.querySelectorAll("[data-total]").forEach((el) => tween(el, q.total));
    root.querySelectorAll("[data-count]").forEach((el) => (el.textContent = q.dishes.length));
    save(state);
  }

  // ---- events
  mounts.pkgs.addEventListener("change", (e) => {
    const p = byId(PACKAGES, e.target.value);
    if (!p) return;
    state.pkgId = p.id;
    state.dishIds = [...p.dishes];
    say(`נבחרה חבילת ${p.name}. התפריט עודכן.`);
    render();
  });
  mounts.dishes.addEventListener("click", (e) => {
    const b = e.target.closest(".cb-dish");
    if (!b) return;
    const i = state.dishIds.indexOf(b.dataset.id);
    i < 0 ? state.dishIds.push(b.dataset.id) : state.dishIds.splice(i, 1);
    render();
  });
  const showDish = (e) => {
    const b = e.target.closest(".cb-dish");
    const d = b && byId(DISHES, b.dataset.id);
    if (d?.img) root.dispatchEvent(new CustomEvent("cb:dish", { detail: d, bubbles: true }));
  };
  mounts.dishes.addEventListener("pointerover", showDish);
  mounts.dishes.addEventListener("focusin", showDish);
  const setGuests = (n) => { state.guests = clampGuests(n); render(); };
  mounts.guests.addEventListener("click", (e) => {
    const b = e.target.closest("[data-step]");
    if (b) setGuests(state.guests + Number(b.dataset.step));
  });
  range.addEventListener("input", () => setGuests(range.value));
  num.addEventListener("input", () => { if (num.value !== "") setGuests(num.value); });
  num.addEventListener("blur", () => { num.value = state.guests; });
  mounts.summary.addEventListener("click", (e) => {
    const r = e.target.closest("[data-remove]");
    if (r) { state.dishIds = state.dishIds.filter((id) => id !== r.dataset.remove); render(); }
    if (e.target.closest(".cb-sum__clear")) { state.dishIds = []; render(); }
  });

  initQuoteForm(mounts.form, state);
  render();
  return state;
}

function initQuoteForm(mount, state) {
  const today = new Date().toISOString().slice(0, 10);
  mount.innerHTML = `
    <form class="cb-form" novalidate>
      <div class="cb-field"><label for="q-name">שם מלא</label><input id="q-name" name="name" autocomplete="name" required><p class="cb-err" id="q-name-e"></p></div>
      <div class="cb-field"><label for="q-phone">טלפון</label><input id="q-phone" name="phone" type="tel" autocomplete="tel" dir="ltr" inputmode="tel" required><p class="cb-err" id="q-phone-e"></p></div>
      <div class="cb-field"><label for="q-email">אימייל <small>(לא חובה)</small></label><input id="q-email" name="email" type="email" autocomplete="email" dir="ltr"><p class="cb-err" id="q-email-e"></p></div>
      <div class="cb-field"><label for="q-date">תאריך האירוע</label><input id="q-date" name="date" type="date" min="${today}" required><p class="cb-err" id="q-date-e"></p></div>
      <div class="cb-field"><label for="q-type">סוג האירוע</label><select id="q-type" name="type" required><option value="">בחרו…</option>${EVENT_TYPES.map((t) => `<option>${t}</option>`).join("")}</select><p class="cb-err" id="q-type-e"></p></div>
      <div class="cb-field cb-field--wide"><label for="q-notes">הערות <small>(העדפות, מגבלות תזונתיות, מיקום)</small></label><textarea id="q-notes" name="notes" rows="3"></textarea></div>
      <p class="cb-err cb-err--menu" id="q-menu-e" role="alert"></p>
      <button class="btn" type="submit">שליחת בקשת הצעה</button>
      <p class="cb-form__demo">זהו אתר דמו: הבקשה נשמרת בדפדפן שלכם בלבד ולא נשלחת לאף גורם.</p>
    </form>`;
  const form = mount.querySelector("form");
  const rules = {
    name: (v) => (v.trim().length >= 2 ? "" : "נא להזין שם"),
    phone: (v) => (/^[0-9+\-\s()]{7,15}$/.test(v.trim()) ? "" : "נא להזין מספר טלפון תקין"),
    email: (v) => (!v || /^\S+@\S+\.\S+$/.test(v) ? "" : "כתובת האימייל אינה תקינה"),
    date: (v) => (v && v >= today ? "" : "נא לבחור תאריך עתידי"),
    type: (v) => (v ? "" : "נא לבחור סוג אירוע"),
  };
  const check = (name) => {
    const el = form.elements[name], msg = rules[name](el.value);
    form.querySelector(`#q-${name}-e`).textContent = msg;
    el.setAttribute("aria-invalid", !!msg);
    el.setAttribute("aria-describedby", `q-${name}-e`);
    return !msg;
  };
  Object.keys(rules).forEach((n) => form.elements[n].addEventListener("blur", () => check(n)));
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const results = Object.keys(rules).map(check);
    const menuErr = form.querySelector("#q-menu-e");
    menuErr.textContent = state.dishIds.length ? "" : "בחרו לפחות מנה אחת בתפריט לפני שליחת הבקשה.";
    const bad = Object.keys(rules).find((n, i) => !results[i]);
    if (bad) return form.elements[bad].focus();
    if (!state.dishIds.length) return;
    const q = quote(state), data = Object.fromEntries(new FormData(form));
    const ref = "Q-" + Date.now().toString(36).toUpperCase().slice(-6);
    try {
      const all = JSON.parse(localStorage.getItem("catering-demo-requests") || "[]");
      all.push({ ref, ...data, pkgId: state.pkgId, guests: state.guests, dishIds: state.dishIds, estimate: q.total });
      localStorage.setItem("catering-demo-requests", JSON.stringify(all));
    } catch { /* ignore */ }
    const done = document.createElement("div");
    done.className = "cb-done";
    done.tabIndex = -1;
    done.innerHTML = `<h3></h3><p></p><p class="cb-done__sum"></p><p class="cb-form__demo">דמו בלבד — לא נשלח דבר. מספר הפנייה לדוגמה: <bdi></bdi></p>
      <button type="button" class="btn cb-done__again">עריכת הבקשה</button>`;
    done.querySelector("h3").textContent = `תודה, ${data.name.trim()}!`;
    done.querySelector("p").textContent = `בקשת ההצעה ל${data.type} בתאריך ${new Date(data.date).toLocaleDateString("he-IL")} התקבלה (בדמו).`;
    done.querySelector(".cb-done__sum").textContent = `חבילת ${q.pkg.name} · ${state.guests} אורחים · ${q.dishes.length} מנות · הערכה: ${money(q.total)}`;
    done.querySelector("bdi").textContent = ref;
    form.hidden = true;
    mount.append(done);
    done.focus();
    done.querySelector(".cb-done__again").addEventListener("click", () => { done.remove(); form.hidden = false; });
  });
}
