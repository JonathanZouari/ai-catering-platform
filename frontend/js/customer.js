import { CATEGORIES, DISHES, DISH_BY_ID, EVENT_TYPES, TIME_SLOTS, DELIVERY_ZONES, KASHRUT, img, money, recommendedQty } from "./data.js";
import { createStore, totals, coverage, guestsOf, STATUS_LABEL } from "./order.js";
import { createTable } from "./table.js";
import { enableDrag } from "./dnd.js";
import { createAssistant } from "./assistant.js";

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const bind = (name) => $(`[data-bind="${name}"]`);

const store = createStore();
const STEPS = ["event", "menu", "summary", "send"];
let step = STEPS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "event";
if (store.get().status !== "draft") step = "send";

// --- announcements and toast ---------------------------------------------
const live = bind("announce");
const smooth = () => (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");
const announce = (text) => { live.textContent = ""; requestAnimationFrame(() => (live.textContent = text)); };
const toastEl = bind("toast");
let toastTimer;
const hideToast = () => { toastEl.classList.remove("is-on"); toastEl.inert = true; };
const armToast = () => { clearTimeout(toastTimer); toastTimer = setTimeout(hideToast, 7000); };
toastEl.inert = true;
toastEl.addEventListener("pointerenter", () => clearTimeout(toastTimer));
toastEl.addEventListener("focusin", () => clearTimeout(toastTimer));
toastEl.addEventListener("pointerleave", armToast);
toastEl.addEventListener("focusout", armToast);
function toast(text, action) {
  toastEl.inert = false;
  toastEl.innerHTML = `<span>${text}</span>${action ? `<button type="button">${action.label}</button>` : ""}`;
  if (action) toastEl.querySelector("button").onclick = () => { hideToast(); action.run(); };
  toastEl.classList.add("is-on");
  armToast();
}

// --- table ------------------------------------------------------------------
const table = createTable($("#table"), { onActivate: (id) => openDish(id) });

enableDrag({
  canDrag: () => store.get().status === "draft",
  getTarget: () => table.dropTarget,
  onDropOnTable: (id) => addDish(id),
  onDropOffTable: (id) => removeDish(id),
  announce,
});

const editable = () => store.get().status === "draft";

function addDish(id) {
  if (!editable()) return;
  const had = store.get().items[id];
  store.add(id);
  const qty = store.get().items[id];
  table.pulse(id);
  announce(`${DISH_BY_ID[id].name} על השולחן, ${qty}`);
  if (!had) return toast(`${DISH_BY_ID[id].name} נוסף, ${qty} ${unitWord(DISH_BY_ID[id], qty)} לפי מספר האורחים`);
}

function removeDish(id) {
  if (!editable()) return;
  const { items, manual } = store.get();
  store.remove(id);
  announce(`${DISH_BY_ID[id].name} הוסר מהשולחן`);
  toast(`${DISH_BY_ID[id].name} ירד מהשולחן`, { label: "ביטול", run: () => {
    store.restore(items, manual);
    ($(`[data-dish="${id}"] [data-act=inc]`) || $(`.platter[data-id="${id}"]`))?.focus();
  } });
}

const unitWord = (d, n) => (d.unit === "כוס" ? (n === 1 ? "כוס" : "כוסות") : d.unit === "חלה" ? (n === 1 ? "חלה" : "חלות") : n === 1 ? "מגש" : "מגשים");

// --- steps ------------------------------------------------------------------
function go(next, { focus = true } = {}) {
  if (store.get().status !== "draft") next = "send";
  step = next;
  history.replaceState(null, "", `#${next}`);
  $$("[data-panel]").forEach((p) => (p.hidden = p.dataset.panel !== next));
  const idx = STEPS.indexOf(next);
  $$(".steps button").forEach((b, i) => {
    b.toggleAttribute("aria-current", b.dataset.step === next);
    if (b.dataset.step === next) b.setAttribute("aria-current", "step");
    b.classList.toggle("is-done", i < idx);
  });
  if (next === "send") renderSend();
  if (focus) {
    const h = $(`[data-panel="${next}"] h2`);
    h?.setAttribute("tabindex", "-1");
    h?.focus({ preventScroll: true });
    if (window.innerWidth <= 960) $("#panel").scrollIntoView({ behavior: smooth(), block: "start" });
  }
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-go],[data-step]");
  if (!b) return;
  go(b.dataset.go || b.dataset.step);
});

// --- step 1: event ----------------------------------------------------------
function initEvent() {
  const s = store.get().event;
  bind("event-types").innerHTML = EVENT_TYPES.map((t) => `<button class="chip" type="button" role="radio" data-type="${t}">${t}</button>`).join("");
  $("#slot").innerHTML = `<option value="">בחרו שעה</option>` + TIME_SLOTS.map((t) => `<option>${t}</option>`).join("");
  $("#zone").innerHTML = DELIVERY_ZONES.map((z) => `<option value="${z.id}">${z.label}, ${money(z.fee)}</option>`).join("");

  const min = new Date(Date.now() + 3 * 864e5);
  $("#date").min = min.toISOString().slice(0, 10);
  if (!s.date) {
    const d = new Date(Date.now() + 12 * 864e5);
    store.setEvent({ date: d.toISOString().slice(0, 10), slot: TIME_SLOTS[2] });
  }

  bind("event-types").addEventListener("click", (e) => {
    const b = e.target.closest("[data-type]");
    if (b) store.setEvent({ type: b.dataset.type });
  });
  bind("event-types").addEventListener("keydown", (e) => {
    const keys = { ArrowLeft: 1, ArrowDown: 1, ArrowRight: -1, ArrowUp: -1 };
    if (!(e.key in keys)) return;
    e.preventDefault();
    const all = $$("[data-type]");
    const i = all.indexOf(document.activeElement);
    const next = all[(i + keys[e.key] + all.length) % all.length];
    store.setEvent({ type: next.dataset.type });
    next.focus();
  });
  $$("[data-count]").forEach((b) => b.addEventListener("click", () => {
    const key = b.dataset.count;
    const max = key === "adults" ? 120 : 80;
    const v = Math.max(0, Math.min(max, store.get().event[key] + Number(b.dataset.delta)));
    store.setEvent({ [key]: v });
  }));
  // hold to repeat on the counters
  $$("[data-count]").forEach((b) => {
    let t, r;
    b.addEventListener("pointerdown", () => { t = setTimeout(() => (r = setInterval(() => b.click(), 70)), 380); });
    ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => b.addEventListener(ev, () => { clearTimeout(t); clearInterval(r); }));
  });
  $$("[data-field]").forEach((el) => {
    const evt = el.tagName === "SELECT" || el.type === "date" ? "change" : "input";
    el.addEventListener(evt, () => {
      let v = el.value;
      if (el.type === "number") v = Math.max(0, Math.min(Number(el.max), Math.round(Number(v) || 0)));
      store.setEvent({ [el.dataset.field]: v });
      if (el.type === "number" && el.value !== "" && String(v) !== el.value) el.value = v;
    });
  });
  $$("[data-fulfillment]").forEach((b) => b.addEventListener("click", () => store.setEvent({ fulfillment: b.dataset.fulfillment })));
  $(".segmented").addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    const next = $$("[data-fulfillment]").find((b) => b !== document.activeElement);
    store.setEvent({ fulfillment: next.dataset.fulfillment });
    next.focus();
  });
}

function renderEvent(s) {
  const e = s.event;
  const types = $$("[data-type]");
  const anyOn = types.some((b) => b.dataset.type === e.type);
  types.forEach((b, i) => { const on = b.dataset.type === e.type; b.setAttribute("aria-checked", String(on)); b.tabIndex = on || (!anyOn && i === 0) ? 0 : -1; });
  $$("[data-fulfillment]").forEach((b) => { b.tabIndex = b.dataset.fulfillment === e.fulfillment ? 0 : -1; });
  $$("[data-fulfillment]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.fulfillment === e.fulfillment)));
  $$("[data-show]").forEach((el) => (el.hidden = el.dataset.show !== e.fulfillment));
  for (const el of $$("[data-field]")) {
    if (document.activeElement === el) continue;
    const v = e[el.dataset.field];
    if (v !== undefined && el.value !== String(v)) el.value = v;
  }
}

// --- step 2: menu -----------------------------------------------------------
function initMenu() {
  bind("menu-tabs").innerHTML = CATEGORIES.map((c, i) => `<a class="chip" href="#cat-${c.id}"${i === 0 ? ' aria-current="true"' : ""}>${c.label}</a>`).join("");
  bind("menu-tabs").addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;
    e.preventDefault();
    $(a.getAttribute("href")).scrollIntoView({ behavior: smooth(), block: "start" });
    $$("a", bind("menu-tabs")).forEach((x) => x.toggleAttribute("aria-current", x === a));
  });
  bind("menu").innerHTML = CATEGORIES.map((c) => `
    <li class="menu__cat" id="cat-${c.id}">${c.label}</li>
    ${DISHES.filter((d) => d.category === c.id).map(dishCard).join("")}`).join("");

  bind("menu").addEventListener("click", (e) => {
    const t = e.target.closest("[data-act]");
    if (!t) return;
    const id = t.closest("[data-dish]").dataset.dish;
    const act = t.dataset.act;
    const q = store.get().items[id] ?? 0;
    if (act === "add" || act === "grab") addDish(id);
    else if (act === "inc") { store.setQty(id, q + 1); table.pulse(id); }
    else if (act === "dec") { if (q <= 1) removeDish(id); else { store.setQty(id, q - 1); table.pulse(id); } }
    else if (act === "info") openDish(id);
  });

  const io = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (!en.isIntersecting) continue;
      const id = en.target.id;
      $$("a", bind("menu-tabs")).forEach((a) => a.toggleAttribute("aria-current", a.getAttribute("href") === `#${id}`));
    }
  }, { rootMargin: "-30% 0px -60% 0px" });
  $$(".menu__cat").forEach((el) => io.observe(el));
}

function tags(d) {
  const k = { meat: "tag--meat", dairy: "tag--dairy", parve: "" }[d.kashrut];
  const out = [`<span class="tag ${k}">${KASHRUT[d.kashrut]}</span>`];
  if (d.diet.includes("vegan")) out.push(`<span class="tag tag--veg"><i class="ph ph-leaf" aria-hidden="true"></i>טבעוני</span>`);
  else if (d.diet.includes("vegetarian")) out.push(`<span class="tag tag--veg">צמחוני</span>`);
  if (d.kids) out.push(`<span class="tag">לילדים</span>`);
  return out.join("");
}

function dishCard(d) {
  return `
    <li class="dish" data-dish="${d.id}">
      <button class="dish__grab" type="button" data-drag-dish="${d.id}" data-act="grab" aria-label="הוספת ${d.name} לשולחן">
        <img src="${img(d.id)}" alt="" loading="lazy" draggable="false" width="88" height="88">
      </button>
      <div class="dish__body">
        <div class="dish__top">
          <h3 class="dish__name">${d.name}</h3>
          <span class="dish__price num">${money(d.price)} <small>ל${d.unit}</small></span>
        </div>
        <p class="dish__blurb">${d.blurb}</p>
        <div class="dish__tags">${tags(d)}</div>
        <div class="dish__foot">
          <button class="linklike" type="button" data-act="info">תזונה ואלרגנים</button>
          <span data-slot="ctl"></span>
        </div>
      </div>
    </li>`;
}

function renderMenu(s) {
  const g = guestsOf(s);
  for (const li of $$("[data-dish]", bind("menu"))) {
    const d = DISH_BY_ID[li.dataset.dish];
    const q = s.items[d.id] ?? 0;
    li.classList.toggle("is-on-table", q > 0);
    const slot = $("[data-slot=ctl]", li);
    const want = q > 0 ? "stepper" : "add";
    if (slot.dataset.kind !== want) {
      const hadFocus = slot.contains(document.activeElement);
      slot.dataset.kind = want;
      slot.innerHTML = want === "add"
        ? `<button class="btn btn--sm add-btn" type="button" data-act="add"><i class="ph ph-plus" aria-hidden="true"></i><span></span></button>`
        : `<span class="stepper"><button type="button" data-act="dec" aria-label="פחות ${d.name}"><i class="ph ph-minus"></i></button><output class="num"></output><button type="button" data-act="inc" aria-label="עוד ${d.name}"><i class="ph ph-plus"></i></button></span>`;
      if (hadFocus) $(want === "add" ? "[data-act=add]" : "[data-act=inc]", slot).focus();
    }
    if (want === "add") { const r = recommendedQty(d, g, s.items, s.manual); $("span", slot).textContent = `${r} ${unitWord(d, r)}`; }
    else $("output", slot).textContent = q;
  }
}

// --- dish sheet --------------------------------------------------------------
const sheet = bind("dish-sheet");
function openDish(id) {
  const d = DISH_BY_ID[id];
  const s = store.get();
  const q = s.items[id] ?? 0;
  const rec = recommendedQty(d, guestsOf(s), s.items, s.manual);
  const n = d.nutrition;
  sheet.innerHTML = `
    <div class="sheet__hero">
      <img src="${img(id)}" alt="${d.name}, מבט מלמעלה" width="260" height="260">
      <button class="icon-btn sheet__close" type="button" data-close aria-label="סגירה"><i class="ph ph-x"></i></button>
    </div>
    <div class="sheet__body">
      <div class="sheet__row">
        <h3 id="dish-sheet-title">${d.name}</h3>
        <span class="dish__price num">${money(d.price)} <small>ל${d.unit}</small></span>
      </div>
      <p>${d.blurb} ${d.serves > 1 ? `${d.unit === "חלה" ? "חלה" : "מגש"} מספיק לכ־${d.serves} סועדים.` : ""}</p>
      <div class="dish__tags">${tags(d)}</div>
      <dl class="facts" aria-label="ערכים תזונתיים למנה אחת">
        <div><dt>קלוריות</dt><dd class="num">${n.kcal}</dd></div>
        <div><dt>חלבון</dt><dd class="num">${n.protein}<small> ג׳</small></dd></div>
        <div><dt>פחמימות</dt><dd class="num">${n.carbs}<small> ג׳</small></dd></div>
        <div><dt>שומן</dt><dd class="num">${n.fat}<small> ג׳</small></dd></div>
      </dl>
      <p class="sheet__fine"><b>אלרגנים:</b> ${d.allergens.length ? d.allergens.join(", ") : "לא ידוע על אלרגנים עיקריים"}. הערכים למנה אחת, לידיעה בלבד.</p>
      <div class="sheet__row">
        <span class="dish__hint">ל־${s.event.adults + s.event.children} אורחים: ${rec} ${unitWord(d, rec)}</span>
        ${!editable() ? `<span class="dish__hint num">בהזמנה: ${q} ${unitWord(d, q)}</span>` : q ? `<span class="stepper"><button type="button" data-sheet="dec" aria-label="פחות"><i class="ph ph-minus"></i></button><output class="num">${q}</output><button type="button" data-sheet="inc" aria-label="עוד"><i class="ph ph-plus"></i></button></span>`
            : `<button class="btn btn--primary btn--sm" type="button" data-sheet="add"><i class="ph ph-plus" aria-hidden="true"></i>לשולחן</button>`}
      </div>
      ${q && editable() ? `<button class="btn btn--ghost btn--sm" type="button" data-sheet="remove"><i class="ph ph-trash" aria-hidden="true"></i>הורדה מהשולחן</button>` : ""}
    </div>`;
  if (!sheet.open) sheet.showModal();
  sheet.onclick = (e) => {
    if (e.target === sheet || e.target.closest("[data-close]")) return sheet.close();
    const a = e.target.closest("[data-sheet]")?.dataset.sheet;
    if (!a) return;
    const cur = store.get().items[id] ?? 0;
    if (a === "add") addDish(id);
    if (a === "inc") store.setQty(id, cur + 1);
    if (a === "dec") cur <= 1 ? removeDish(id) : store.setQty(id, cur - 1);
    if (a === "remove") { removeDish(id); return sheet.close(); }
    table.pulse(id);
    openDish(id);
    const again = $(`[data-sheet="${a}"]`, sheet) || $(a === "add" || a === "inc" ? "[data-sheet=inc]" : "[data-sheet=add]", sheet) || $("[data-close]", sheet);
    again?.focus();
  };
}

// --- step 3: summary ----------------------------------------------------------
function renderSummary(s) {
  const t = totals(s);
  const notices = [];
  const kinds = new Set(t.lines.map((l) => l.dish.kashrut));
  if (kinds.has("meat") && kinds.has("dairy")) {
    const dairy = t.lines.filter((l) => l.dish.kashrut === "dairy").map((l) => l.dish.name).join(", ");
    notices.push(`<div class="notice"><i class="ph ph-warning-circle" aria-hidden="true"></i><span>בהזמנה יש מנות בשריות ומנות חלביות (${dairy}). אם האירוע כשר, כדאי להחליף את החלביות.</span></div>`);
  }
  if (!s.event.notes.trim() && t.lines.some((l) => l.dish.allergens.length)) {
    notices.push(`<div class="notice notice--info"><i class="ph ph-info" aria-hidden="true"></i><span>יש בתפריט מנות עם אלרגנים. אם למישהו מהאורחים יש אלרגיה, כתבו זאת בהערות באירוע.</span></div>`);
  }
  bind("notices").innerHTML = notices.join("");

  if (!t.lines.length) {
    bind("receipt").innerHTML = `<div class="receipt__empty"><p>עוד לא הוספתם מנות לשולחן.</p><button class="btn btn--sm" type="button" data-go="menu">לתפריט</button></div>`;
    return;
  }
  bind("receipt").innerHTML = t.lines.map((l) => `
    <div class="receipt__row">
      <img src="${img(l.dish.id)}" alt="" width="44" height="44" loading="lazy">
      <div><div class="receipt__name">${l.dish.name}</div><div class="receipt__math num">${l.qty} × ${money(l.dish.price)}</div></div>
      <div class="receipt__line num">${money(l.line)}</div>
    </div>`).join("") + `
    <div class="receipt__sum">
      <div><span>מנות</span><span class="num">${money(t.subtotal)}</span></div>
      <div><span>${s.event.fulfillment === "delivery" ? "משלוח" : "איסוף עצמי"}</span><span class="num">${t.delivery ? money(t.delivery) : "ללא עלות"}</span></div>
      <div class="is-total"><span>הערכה כוללת</span><span class="num">${money(t.total)}</span></div>
    </div>`;
}

// --- step 4: send and status ----------------------------------------------------
function renderSend() {
  const s = store.get();
  const t = totals(s);
  const e = s.event;
  const when = e.date ? new Date(e.date).toLocaleDateString("he-IL", { weekday: "long", day: "numeric", month: "long" }) : "לא נבחר";
  if (s.status === "draft") {
    bind("send").innerHTML = `
      <div class="step" style="animation:none">
        <header class="step__head">
          <h2 tabindex="-1">שליחת בקשה להצעת מחיר</h2>
          <p>הבקשה עוברת לבעל העסק. ההזמנה סגורה רק אחרי שהוא מאשר אותה.</p>
        </header>
        <dl class="review-list">
          <dt>אירוע</dt><dd>${escapeHtml(e.type)}</dd>
          <dt>מתי</dt><dd>${when}${e.slot ? `, ${escapeHtml(e.slot)}` : ""}</dd>
          <dt>אורחים</dt><dd class="num">${e.adults} מבוגרים ו־${e.children} ילדים</dd>
          <dt>${e.fulfillment === "delivery" ? "משלוח" : "איסוף"}</dt><dd>${e.fulfillment === "delivery" ? escapeHtml(e.address || DELIVERY_ZONES.find((z) => z.id === e.zone)?.label || "") : "מהמטבח, רחוב הנגרים 8"}</dd>
          <dt>מנות</dt><dd class="num">${t.lines.length} מנות, ${money(t.total)}</dd>
        </dl>
        <form class="group" data-bind="send-form" novalidate>
          <div class="grid-2">
            <div class="field"><label for="c-name">שם מלא</label><input class="input" id="c-name" autocomplete="name" required aria-describedby="c-name-err"><span class="field__error" id="c-name-err" hidden>צריך שם כדי שנדע למי לחזור</span></div>
            <div class="field"><label for="c-phone">טלפון</label><input class="input num" id="c-phone" type="tel" inputmode="tel" autocomplete="tel" dir="ltr" placeholder="050-0000000" required aria-describedby="c-phone-err"><span class="field__error" id="c-phone-err" hidden>מספר נייד בן 10 ספרות</span></div>
          </div>
          ${t.lines.length ? "" : `<div class="notice"><i class="ph ph-warning-circle" aria-hidden="true"></i><span>השולחן ריק. הוסיפו מנות לפני השליחה.</span></div>`}
          <div class="step__foot">
            <button class="btn btn--ghost" type="button" data-go="summary"><i class="ph ph-arrow-right" aria-hidden="true"></i>חזרה</button>
            <button class="btn btn--accent" type="submit" ${t.lines.length ? "" : "aria-disabled=\"true\""}>שליחה לאישור</button>
          </div>
        </form>
      </div>`;
    const form = bind("send-form");
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      if (!t.lines.length) { go("menu"); return; }
      if (!e.date || e.date < $("#date").min) { go("event"); $("#date").focus(); announce("בחרו תאריך שלפחות 3 ימים מהיום"); return; }
      const name = $("#c-name"), phone = $("#c-phone");
      const okName = name.value.trim().length > 1;
      const okPhone = /^0\d{8,9}$/.test(phone.value.replace(/\D/g, ""));
      name.nextElementSibling.hidden = okName;
      phone.nextElementSibling.hidden = okPhone;
      name.setAttribute("aria-invalid", String(!okName));
      phone.setAttribute("aria-invalid", String(!okPhone));
      if (!okName) return name.focus();
      if (!okPhone) return phone.focus();
      store.setEvent({ contactName: name.value.trim(), contactPhone: phone.value.trim() });
      store.submit();
    });
    return;
  }

  const order = ["draft", "pending", s.status === "rejected" ? "rejected" : "approved"];
  const sent = s.submittedAt ? new Date(s.submittedAt).toLocaleString("he-IL", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  bind("send").innerHTML = `
    <div class="status-card">
      <div class="step__head">
        <span class="badge badge--${s.status}">${STATUS_LABEL[s.status]}</span>
        <h2 tabindex="-1" style="margin-top:14px">${s.status === "pending" ? "הבקשה אצל בעל העסק" : s.status === "approved" ? "האירוע שלכם מאושר" : "הבקשה לא אושרה"}</h2>
        <p>${s.status === "pending" ? "זו עדיין לא הזמנה סגורה. נעדכן כאן ובטלפון ברגע שתהיה תשובה." : s.status === "approved" ? `נתראה ב${when}.` : "אפשר לעדכן את השולחן ולשלוח שוב."}</p>
      </div>
      <ol class="timeline">
        <li class="is-done"><span class="timeline__dot"><i class="ph ph-check"></i></span><div><strong>הבקשה נשלחה</strong><span class="num">${sent}</span></div></li>
        <li class="${s.status === "pending" ? "is-now" : "is-done"}"><span class="timeline__dot"><i class="ph ${s.status === "pending" ? "ph-hourglass-medium" : "ph-check"}"></i></span><div><strong>בדיקה של בעל העסק</strong><span>מחירים, כמויות ותאריך</span></div></li>
        <li class="${s.status === "approved" ? "is-done" : s.status === "rejected" ? "is-rejected" : ""}"><span class="timeline__dot"><i class="ph ${s.status === "rejected" ? "ph-x" : "ph-confetti"}"></i></span><div><strong>${order[2] === "rejected" ? "לא אושרה" : "אישור סופי"}</strong><span>${s.status === "pending" ? "ממתין" : ""}</span></div></li>
      </ol>
      <dl class="review-list">
        <dt>אירוע</dt><dd>${escapeHtml(e.type)}, ${when}</dd>
        <dt>אורחים</dt><dd class="num">${e.adults + e.children}</dd>
        <dt>הערכה</dt><dd class="num">${money(t.total)}</dd>
      </dl>
      <div class="step__foot">
        <button class="btn btn--ghost btn--sm" type="button" data-new>הזמנה חדשה</button>
        ${s.status === "rejected" ? `<button class="btn btn--primary btn--sm" type="button" data-edit>לעדכן ולשלוח שוב</button>` : ""}
      </div>
    </div>`;
  bind("send").querySelector("[data-new]")?.addEventListener("click", () => { store.reset(); go("event"); });
  bind("send").querySelector("[data-edit]")?.addEventListener("click", () => { store.setStatus("draft"); go("menu"); });
}

const escapeHtml = (t) => t.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// --- stage ----------------------------------------------------------------------
let lastTotal = 0;
function renderStage(s) {
  const e = s.event;
  bind("guests-total").textContent = e.adults + e.children;
  bind("guests-split").textContent = `${e.adults} מבוגרים, ${e.children} ילדים, ${e.type}`;
  const total = totals(s).total;
  tween(bind("total"), lastTotal, total);
  lastTotal = total;

  const cov = coverage(s);
  const need = Math.ceil(cov.need);
  bind("coverage").innerHTML = CATEGORIES.map((c) => {
    const have = Math.floor(cov.byCat[c.id] ?? 0);
    const cls = have === 0 ? "is-missing" : have >= need ? "is-ok" : "is-short";
    const icon = have === 0 ? "ph-circle-dashed" : have >= need ? "ph-check-circle" : "ph-warning-circle";
    const text = have === 0 ? "עדיין ריק" : have >= need ? "מספיק לכולם" : `חסר ל־${need - have} מנות`;
    return `<li class="${cls}"><i class="ph ${icon}" aria-hidden="true"></i><strong>${c.label}</strong> ${text}</li>`;
  }).join("");

  table.update({ adults: e.adults, children: e.children, items: s.items, proposal: s.proposal });

  const stage = $(".stage");
  stage.classList.toggle("is-locked", s.status !== "draft");
  const wasSet = stage.classList.contains("is-set");
  stage.classList.toggle("is-set", s.status === "approved");
  const card = bind("place-card");
  card.hidden = !(s.status !== "draft" && s.ownerNote);
  if (!card.hidden) card.innerHTML = `<b>מבעל העסק</b>${escapeHtml(s.ownerNote)}`;
  if (s.status === "approved" && !wasSet) stage.classList.add("is-setting");
  setTimeout(() => stage.classList.remove("is-setting"), 1600);
}

function tween(el, from, to) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || from === to) { el.textContent = money(to); return; }
  const t0 = performance.now();
  const dur = 520;
  cancelAnimationFrame(el._raf);
  const frame = (t) => {
    const k = Math.min(1, (t - t0) / dur);
    const ease = 1 - Math.pow(1 - k, 3);
    el.textContent = money(from + (to - from) * ease);
    if (k < 1) el._raf = requestAnimationFrame(frame);
  };
  el._raf = requestAnimationFrame(frame);
}

// --- assistant ---------------------------------------------------------------------
const toggle = $(".assistant-toggle");
const assistant = createAssistant({
  root: $("#assistant"),
  store,
  onOpenChange: (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    $(".workspace").classList.toggle("has-assistant", open);
  },
});
toggle.addEventListener("click", () => ($("#assistant").hidden ? assistant.open() : assistant.close()));
$("[data-close-assistant]").addEventListener("click", () => { assistant.close(); toggle.focus(); });

// --- wire up -------------------------------------------------------------------------
function render(s, change = {}) {
  renderStage(s);
  renderEvent(s);
  renderMenu(s);
  renderSummary(s);
  if (change.type === "status" || change.type === "reset") { hideToast(); go(s.status === "draft" ? step : "send", { focus: false }); }
  if (change.type === "proposal-applied") {
    change.changes.forEach((c) => table.pulse(c.id));
    announce("השינוי הוחל על השולחן");
  }
}

initEvent();
initMenu();
store.subscribe(render);
render(store.get());
go(step, { focus: false });

// the owner screen writes to the same storage; reflect its decision live
window.addEventListener("storage", (e) => {
  if (e.key !== "yumi.order.v1" || !e.newValue) return;
  try {
    const next = JSON.parse(e.newValue);
    if (next.status !== store.get().status) store.setStatus(next.status, next.ownerNote);
  } catch { /* ignore */ }
});

// keep the sticky menu tabs under the sticky stage on small screens
const ro = new ResizeObserver(() => document.documentElement.style.setProperty("--stage-h", `${$(".stage").offsetHeight}px`));
ro.observe($(".stage"));
