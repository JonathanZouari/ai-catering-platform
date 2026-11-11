// Radial fan. Design px live in a 390 × 580 stage; desktop scales the stage in CSS.
// The rig is drawn to the inline-start side and mirrored with scaleX(-1) when dir=rtl,
// so the wheel sits on the right edge in Hebrew.
import { $, $$ } from "../dom.js";
import { esc } from "../dom.js";
import { KASHRUT, money, moneyHTML } from "../format.js";
import {
  activeDish,
  catName,
  dishCount,
  fromPrice,
  hooks,
  keyOf,
  mod,
  pendingQty,
  session,
  variantOf,
} from "../session.js";

const STAGE_W = 390;
const PIVOT = { x: -90, y: 262 };
const SHAPE = {
  rest: { r1: 104, r2: 372, half: 15.2, outer: 22, inner: 10 },
  open: { r1: 104, r2: 436, half: 28, outer: 40, inner: 16 },
};

const rad = (deg) => (deg * Math.PI) / 180;
const pt = (r, t) => `${(r * Math.cos(t)).toFixed(2)} ${(r * Math.sin(t)).toFixed(2)}`;

function sectorPath({ r1, r2, half, outer, inner }) {
  const a = rad(half);
  const ao = outer / r2;
  const ai = inner / r1;
  return [
    `M ${pt(r1 + inner, -a)}`,
    `L ${pt(r2 - outer, -a)}`,
    `Q ${pt(r2, -a)} ${pt(r2, -a + ao)}`,
    `A ${r2} ${r2} 0 0 1 ${pt(r2, a - ao)}`,
    `Q ${pt(r2, a)} ${pt(r2 - outer, a)}`,
    `L ${pt(r1 + inner, a)}`,
    `Q ${pt(r1, a)} ${pt(r1, a - ai)}`,
    `A ${r1} ${r1} 0 0 0 ${pt(r1, -a + ai)}`,
    `Q ${pt(r1, -a)} ${pt(r1 + inner, -a)}`,
    "Z",
  ].join(" ");
}

function injectShapeCSS() {
  const s = document.createElement("style");
  s.textContent = `.arm__shape path{d:path("${sectorPath(SHAPE.rest)}")}
.arm.is-open .arm__shape path{d:path("${sectorPath(SHAPE.open)}")}`;
  document.head.append(s);
}

function pointerAngle(e, stageEl, rtl) {
  const r = stageEl.getBoundingClientRect();
  const s = r.width / STAGE_W;
  let x = (e.clientX - r.left) / s;
  if (rtl) x = STAGE_W - x;
  const y = (e.clientY - r.top) / s;
  return (Math.atan2(y - PIVOT.y, x - PIVOT.x) * 180) / Math.PI;
}

const m$ = moneyHTML;
const isRTL = () => document.documentElement.dir === "rtl";
const trashSVG = `<svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18"><path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

let STEP = 0;
let lastCat = null;
let wheel;
let stage;
let detail;

export function mountDishWheel() {
  const dishes = session.dishes;
  const N = dishes.length;
  STEP = 360 / N;
  injectShapeCSS();
  wheel = $("#wheel");
  stage = $("#stage");
  detail = $("#detail");

  wheel.innerHTML = dishes.map((d, i) => `
    <div class="arm" id="opt-${d.id}" role="option" aria-selected="false" data-i="${i}" style="transform: rotate(${(i * STEP).toFixed(3)}deg)"
      aria-label="${esc(d.name)}, ${catName(d.category)}, החל מ־${money(fromPrice(d))}${d.is_available ? "" : ", לא זמין"}">
      <svg class="arm__shape" aria-hidden="true" width="1" height="1"><path/></svg>
      <div class="arm__img" aria-hidden="true"><img src="${d.image}" alt="" width="640" height="640" decoding="async"></div>
      <div class="arm__title" aria-hidden="true"><span>${esc(d.short)}</span></div>
      ${d.is_available ? "" : `<span class="arm__tag" aria-hidden="true"><span>לא זמין</span></span>`}
    </div>`).join("");

  wheel.addEventListener("keydown", (e) => {
    const fwd = isRTL() ? "ArrowLeft" : "ArrowRight";
    const back = isRTL() ? "ArrowRight" : "ArrowLeft";
    if (e.key === "ArrowDown" || e.key === fwd) { e.preventDefault(); step(1); }
    else if (e.key === "ArrowUp" || e.key === back) { e.preventDefault(); step(-1); }
    else if (e.key === "Home") { e.preventDefault(); rotateTo(0); }
    else if (e.key === "End") { e.preventDefault(); rotateTo(N - 1); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(!session.state.open); }
    else if (e.key === "Escape" && session.state.open) { e.preventDefault(); setOpen(false); }
  });
  detail.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { setOpen(false); wheel.focus(); }
  });

  let drag = null;
  stage.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".detail") || e.button !== 0) return;
    drag = { id: e.pointerId, a0: pointerAngle(e, stage, isRTL()), x: e.clientX, y: e.clientY, moved: false, k0: session.state.k };
  });
  stage.addEventListener("pointermove", (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    if (!drag.moved && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 8) return;
    if (!drag.moved) {
      drag.moved = true;
      stage.setPointerCapture(e.pointerId);
      wheel.classList.add("is-dragging");
      if (session.state.open) { session.state.open = false; paintWheel(); renderDetail(); }
    }
    let delta = pointerAngle(e, stage, isRTL()) - drag.a0;
    if (delta > 180) delta -= 360;
    if (delta < -180) delta += 360;
    drag.delta = delta;
    paintWheel(-drag.k0 * STEP + delta);
  });
  function endDrag(e) {
    if (!drag || e.pointerId !== drag.id) return;
    const d = drag;
    drag = null;
    wheel.classList.remove("is-dragging");
    if (d.moved) {
      setK(Math.round(d.k0 - (d.delta ?? 0) / STEP));
      return;
    }
    const arm = e.target.closest?.(".arm");
    if (!arm) return;
    const i = Number(arm.dataset.i);
    if (i === mod(session.state.k, N)) setOpen(!session.state.open);
    else { rotateTo(i, { collapse: false, announce: false }); setOpen(true); }
    wheel.focus({ preventScroll: true });
  }
  stage.addEventListener("pointerup", endDrag);
  stage.addEventListener("pointercancel", (e) => { if (drag) { drag.moved = true; endDrag(e); } });

  let wheelAcc = 0;
  let wheelLock = 0;
  stage.addEventListener("wheel", (e) => {
    if (e.target.closest(".detail")) return;
    e.preventDefault();
    wheelAcc += e.deltaY;
    const now = performance.now();
    if (Math.abs(wheelAcc) > 40 && now > wheelLock) {
      step(Math.sign(wheelAcc));
      wheelAcc = 0;
      wheelLock = now + 220;
    }
  }, { passive: false });

  detail.addEventListener("change", (e) => {
    if (!e.target.matches(".opts input")) return;
    const d = activeDish();
    session.state.variant.set(d.id, e.target.value);
    renderDetail();
    $(`.opts input[value="${CSS.escape(e.target.value)}"]`, detail).focus();
  });
  detail.addEventListener("click", (e) => {
    const t = e.target.closest("[data-act]");
    if (!t || t.dataset.act === "open") return;
    const d = activeDish();
    const v = variantOf(d);
    const key = keyOf(d, v);
    const q = pendingQty(d, v);
    if (t.dataset.act === "inc") session.state.pending.set(key, q + 1);
    if (t.dataset.act === "dec") session.state.pending.set(key, Math.max(v.min ?? 1, q - 1));
    if (t.dataset.act === "add") {
      if (t.getAttribute("aria-disabled") === "true") return;
      session.state.order.set(key, q);
      session.state.pending.delete(key);
    }
    if (t.dataset.act === "remove") {
      session.state.order.delete(key);
      session.state.pending.delete(key);
    }
    const act = t.dataset.act === "remove" ? "add" : t.dataset.act;
    const bump = t.dataset.act === "add";
    renderDetail();
    hooks.onOrderChange({ bump });
    ($(`[data-act="${act}"]:not([disabled])`, detail) || $("[data-act='add']", detail))?.focus();
  });

  $("#cats").addEventListener("change", (e) => {
    const first = session.dishes.findIndex((d) => d.category === e.target.value);
    rotateTo(first, { collapse: true });
  });
}

export function paintWheel(angleOverride) {
  const deg = angleOverride ?? -session.state.k * STEP;
  wheel.style.transform = `rotate(${deg}deg)`;
  const a = activeDish();
  $$(".arm", wheel).forEach((el) => {
    const on = el.id === `opt-${a.id}`;
    el.classList.toggle("is-active", on);
    el.classList.toggle("is-open", on && session.state.open);
    el.setAttribute("aria-selected", String(on));
  });
  wheel.classList.toggle("is-open", session.state.open);
  stage.classList.toggle("is-open", session.state.open);
  wheel.setAttribute("aria-activedescendant", `opt-${a.id}`);
}

export function renderCats() {
  const cur = activeDish().category;
  $("#cats").innerHTML = session.categories.map((c) => `
    <label class="r-cat"><input type="radio" name="cat" value="${c.id}" ${c.id === cur ? "checked" : ""}><span>${c.name}</span></label>`).join("");
}

export function rememberCategory() {
  lastCat = activeDish().category;
}

let sayTimer;
function say(msg) {
  clearTimeout(sayTimer);
  sayTimer = setTimeout(() => { $("#fan-live").textContent = msg; }, 120);
}

export function setK(newK, { collapse = true, announce = true } = {}) {
  const moved = newK !== session.state.k;
  if (moved && collapse) session.state.open = false;
  session.state.k = newK;
  paintWheel();
  renderDetail();
  const a = activeDish();
  let categoryChanged = false;
  if (a.category !== lastCat) {
    lastCat = a.category;
    renderCats();
    categoryChanged = true;
  }
  hooks.onActiveChange({ categoryChanged, moved });
  const N = dishCount();
  if (announce && moved) say(`${a.name}, ${mod(session.state.k, N) + 1} מתוך ${N}, ${catName(a.category)}${a.is_available ? "" : ", לא זמין"}.`);
}

export function rotateTo(index, opts) {
  const N = dishCount();
  let diff = mod(index - mod(session.state.k, N), N);
  if (diff > N / 2) diff -= N;
  setK(session.state.k + diff, opts);
}

export const step = (n) => setK(session.state.k + n);

export function setOpen(open, { focusDetail = false } = {}) {
  session.state.open = open;
  paintWheel();
  renderDetail();
  const a = activeDish();
  const { units } = session;
  say(open
    ? `נפתחו האפשרויות של ${a.name}: ${a.variants.map((v) => `${v.label}, ${money(v.price)} ${units[v.unit].per}`).join("; ")}. אפשר לעבור ביניהן עם Tab.`
    : `האפשרויות של ${a.name} נסגרו.`);
  if (focusDetail) $("input:checked", detail)?.focus();
}

export function renderDetail() {
  const d = activeDish();
  detail.toggleAttribute("inert", !session.state.open);
  detail.classList.toggle("is-open", session.state.open);
  const v = variantOf(d);
  const key = keyOf(d, v);
  const q = pendingQty(d, v);
  const inOrder = session.state.order.get(key);
  const min = v.min ?? 1;
  const atMin = q <= min;
  const unit = session.units[v.unit];
  const addLabel = !inOrder ? "הוספה להזמנה" : inOrder === q ? "בהזמנה ✓" : "עדכון ההזמנה";
  const meta = [v.note, d.kashrut ? KASHRUT[d.kashrut] : "כשרות לא אומתה"].filter(Boolean).join(" · ");
  detail.innerHTML = `
    <h2 class="visually-hidden" id="detail-title">${esc(d.name)}</h2>
    <p class="detail__meta">${esc(meta)}</p>
    <fieldset class="opts">
      <legend class="visually-hidden">${d.variants[0].unit === "guest" ? "מספר סועדים" : "גודל"}: ${esc(d.name)}</legend>
      ${d.variants.map((x) => `<label class="opt"><input type="radio" name="opt-${d.id}" value="${x.id}" ${x.id === v.id ? "checked" : ""}><span>${esc(x.label)}</span></label>`).join("")}
    </fieldset>
    <p class="detail__price"><span class="detail__amount">${m$(v.price)}</span><span class="detail__unit">${unit.per}</span></p>
    <div class="tray">
      ${d.is_available ? `
      <div class="tray__row">
        <!-- RTL: "+" comes first so it sits on the reading-start (right) side -->
        <div class="stepper" role="group" aria-label="כמות: ${esc(d.name)}, ${esc(v.label)}">
          <button type="button" data-act="inc" aria-label="הוספת ${esc(unit.count(1))}">+</button>
          <span class="stepper__value" aria-live="polite">${esc(unit.count(q))}</span>
          <button type="button" data-act="dec" aria-label="הורדת ${esc(unit.count(1))}" ${atMin ? "disabled" : ""}>−</button>
        </div>
        <button type="button" class="btn btn--primary tray__add" data-act="add" ${inOrder === q ? 'aria-disabled="true"' : ""}>
          <span>${esc(addLabel)}</span><span class="tray__sum">${m$(q * v.price)}</span></button>
      </div>` : `<p class="tray__unavailable"><svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8 8l8 8" stroke="currentColor" stroke-width="2"/></svg>${esc(d.unavailable_reason)}</p>`}
      <div class="tray__links">
        <button type="button" class="tray__link" data-act="open" data-id="${d.id}">מה במנה ואלרגנים</button>
        ${inOrder ? `<button type="button" class="tray__link tray__remove" data-act="remove">${trashSVG}הסרה מההזמנה</button>` : ""}
      </div>
    </div>`;
}

export function focusWheel() {
  wheel.focus({ preventScroll: true });
}
