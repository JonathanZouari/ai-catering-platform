// The banquet table: seats follow the guest count, platters follow the order.
// Layout is computed in JS (positions as transforms) so every change animates.
import { DISH_BY_ID, CATEGORIES, CHILD_FACTOR, img, unitWord } from "./data.js";

const MAX_SEATS = 140;

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967295;
}

export function createTable(root, { onActivate, interactive = true, compactBreakpoint = 0 } = {}) {
  root.classList.add("banquet");
  root.innerHTML = `
    <div class="banquet__table" data-drop-target>
      <div class="banquet__seats" aria-hidden="true"></div>
      <div class="banquet__platters" role="group" aria-label="המנות על השולחן"></div>
      ${interactive ? `<p class="banquet__empty"><i class="ph ph-hand-grabbing" aria-hidden="true"></i><span>גררו לכאן מנות מהתפריט</span></p>` : ""}
    </div>`;
  const tableEl = root.querySelector(".banquet__table");
  const seatsEl = root.querySelector(".banquet__seats");
  const plattersEl = root.querySelector(".banquet__platters");

  let state = { adults: 0, children: 0, items: {}, proposal: null, reserve: 0 };
  let size = { w: 0, h: 0, portrait: false };
  const platterEls = new Map();

  function measure() {
    const r = tableEl.getBoundingClientRect();
    size = { w: r.width, h: r.height, portrait: root.clientWidth < compactBreakpoint };
    root.dataset.orientation = size.portrait ? "portrait" : "landscape";
  }

  function seatLayout() {
    const total = Math.min(MAX_SEATS, state.adults + state.children);
    const long = size.portrait ? size.h : size.w;
    const short = size.portrait ? size.w : size.h;
    const perSide = Math.max(1, Math.ceil(total / 2));
    const pad = Math.min(long * 0.03, 22);
    const step = (long - pad * 2) / perSide;
    const plate = Math.max(11, Math.min(short * 0.14, step * 0.86, 36));
    const inset = plate * 0.62 + short * 0.025;
    const seats = [];
    for (let i = 0; i < total; i++) {
      const side = i % 2;
      const k = Math.floor(i / 2);
      const along = pad + step * (k + 0.5);
      const across = side ? short - inset : inset;
      // children sit together at the far end of each side
      const kid = i >= total - state.children;
      seats.push(size.portrait ? { x: across, y: along, kid } : { x: along, y: across, kid });
    }
    return { seats, plate, inset };
  }

  // Portions each course provides, from the committed order only. Kids dishes
  // are kept apart: they feed the children's end of the table, not the adults.
  function portions() {
    const all = {}, kids = {};
    for (const [id, qty] of Object.entries(state.items)) {
      const d = DISH_BY_ID[id];
      if (!d || qty <= 0) continue;
      const bucket = d.kids ? kids : all;
      const p = d.serves === 1 ? qty : qty * d.serves;
      bucket[d.category] = (bucket[d.category] ?? 0) + p;
    }
    return { all, kids };
  }

  // A course reaches seats in order until its portions run out; an adult needs
  // one portion, a child CHILD_FACTOR.
  function reachOf(dishCat, kidsOnly, P) {
    const els = seatsEl.children;
    const out = new Array(els.length).fill(false);
    let cum = 0, kidCum = 0;
    for (let i = 0; i < els.length; i++) {
      const kid = els[i].classList.contains("seat--kid");
      cum += kid ? CHILD_FACTOR : 1;
      if (kid) kidCum += 1;
      const general = !kidsOnly && (P.all[dishCat] ?? 0) + 1e-6 >= cum;
      const forKids = kid && (P.kids[dishCat] ?? 0) + 1e-6 >= kidCum;
      out[i] = kidsOnly ? forKids : general || forKids;
    }
    return out;
  }

  // A seat is "short" when some course on the table does not reach it.
  function paintCoverage() {
    const els = seatsEl.children;
    const P = portions();
    const present = CATEGORIES.filter((c) => (P.all[c.id] ?? 0) > 0 || (P.kids[c.id] ?? 0) > 0);
    const short = new Array(els.length).fill(false);
    for (const c of present) reachOf(c.id, false, P).forEach((r, i) => { if (!r) short[i] = true; });
    root.classList.toggle("has-food", present.length > 0);
    for (let i = 0; i < els.length; i++) els[i].classList.toggle("seat--short", short[i]);
    return P;
  }

  // Light the seats this platter feeds, nearest first, rippling out from it.
  function highlightReach(id, { qty, cls = "is-reach" } = {}) {
    const els = [...seatsEl.children];
    root.classList.toggle(cls === "is-reach" ? "is-tracing" : "is-proposing", !!id);
    for (const el of els) el.classList.remove(cls);
    if (!id) return;
    const d = DISH_BY_ID[id];
    const pel = platterEls.get(id);
    if (!d || !pel) return;
    const s = parseFloat(getComputedStyle(root).getPropertyValue("--platter")) || 0;
    const px = parseFloat(pel.style.getPropertyValue("--x")) + s / 2;
    const py = parseFloat(pel.style.getPropertyValue("--y")) + s / 2;
    let left = (qty ?? state.items[id] ?? 0) * d.serves;
    const seats = els
      .map((el) => {
        const [x, y] = el.style.translate.split(" ").map(parseFloat);
        return { el, kid: el.classList.contains("seat--kid"), dist: Math.hypot(x - px, y - py) };
      })
      .filter((x) => !d.kids || x.kid)
      .sort((a, b) => a.dist - b.dist);
    for (const seat of seats) {
      const need = d.kids || !seat.kid ? 1 : CHILD_FACTOR;
      if (left + 1e-6 < need) break;
      left -= need;
      seat.el.style.setProperty("--d", `${Math.round(seat.dist * 1.1)}ms`);
      seat.el.classList.add(cls);
    }
  }

  function renderSeats() {
    const { seats, plate } = seatLayout();
    root.style.setProperty("--plate", `${plate}px`);
    const existing = seatsEl.children;
    while (existing.length > seats.length) {
      const last = existing[existing.length - 1];
      last.remove();
    }
    seats.forEach((s, i) => {
      let el = existing[i];
      if (!el) {
        el = document.createElement("span");
        el.className = "seat seat--enter";
        el.style.setProperty("--i", String(i % 24));
        el.style.translate = `${s.x}px ${s.y}px`;
        seatsEl.append(el);
        void el.offsetWidth;
        el.classList.remove("seat--enter");
      }
      el.classList.toggle("seat--kid", s.kid);
      el.style.translate = `${s.x}px ${s.y}px`;
    });
    paintCoverage();
  }

  function entries() {
    const list = Object.entries(state.items).map(([id, qty]) => ({ id, qty, from: qty }));
    const p = state.proposal;
    if (p) {
      for (const c of p.changes) {
        const e = list.find((x) => x.id === c.id);
        if (e) e.to = c.to;
        else list.push({ id: c.id, qty: 0, from: 0, to: c.to });
      }
    }
    return list.filter((e) => DISH_BY_ID[e.id]);
  }

  function platterLayout(n) {
    const { plate } = seatLayout();
    const band = plate * 1.25 + 8;
    const cw = (size.portrait ? size.w - band * 2 : size.w - 24);
    const ch = (size.portrait ? size.h - 24 : size.h - band * 2);
    let best = { s: 0, rows: 1, cols: n };
    const maxRows = size.portrait ? 12 : 3;
    for (let rows = 1; rows <= Math.min(maxRows, n); rows++) {
      const cols = Math.ceil(n / rows);
      const s = Math.min(ch / rows, cw / cols) * 0.94;
      if (s > best.s) best = { s, rows, cols };
    }
    const s = Math.min(best.s, size.portrait ? size.w * 0.5 : size.h * 0.56);
    const ox = (size.w - cw) / 2;
    const oy = (size.h - ch) / 2;
    const gridW = best.cols * (cw / best.cols);
    return { ...best, s, cellW: cw / best.cols, cellH: ch / best.rows, ox, oy, gridW };
  }

  function renderPlatters() {
    const list = entries();
    tableEl.classList.toggle("is-empty", list.length === 0);
    // Reserved cells keep the grid unchanged when proposals add platters, so
    // nothing already on the table moves while the user decides.
    const committed = list.filter((e) => e.from > 0).length;
    const L = platterLayout(Math.max(1, list.length, committed + (state.reserve || 0)));
    root.style.setProperty("--platter", `${L.s}px`);
    const seen = new Set();

    list.forEach((e, i) => {
      seen.add(e.id);
      const dish = DISH_BY_ID[e.id];
      let el = platterEls.get(e.id);
      const isNew = !el;
      if (isNew) {
        el = document.createElement(interactive ? "button" : "div");
        if (interactive) el.type = "button";
        el.className = "platter platter--enter";
        el.dataset.id = e.id;
        if (interactive) el.dataset.dragPlatter = e.id;
        const rot = Math.round(hash(e.id) * 70 - 35);
        el.innerHTML = `
          <span class="platter__stack" aria-hidden="true"></span>
          <span class="platter__dish"><img src="${img(e.id)}" alt="" draggable="false" style="rotate:${rot}deg"></span>
          <span class="platter__qty num"></span>
          <span class="platter__name">${dish.name}</span>`;
        plattersEl.append(el);
        platterEls.set(e.id, el);
        el.addEventListener("click", () => onActivate?.(e.id));
        el.addEventListener("pointerenter", () => highlightReach(e.id));
        el.addEventListener("pointerleave", () => highlightReach(null));
        el.addEventListener("focus", () => highlightReach(e.id));
        el.addEventListener("blur", () => highlightReach(null));
      }
      const col = i % L.cols;
      const row = Math.floor(i / L.cols);
      const slots = Math.max(list.length, committed + (state.reserve || 0));
      const rowCount = row === L.rows - 1 ? slots - row * L.cols : L.cols;
      const rowOffset = ((L.cols - rowCount) * L.cellW) / 2;
      const jx = (hash(e.id + "x") - 0.5) * L.cellW * 0.08;
      const jy = (hash(e.id + "y") - 0.5) * L.cellH * 0.1;
      // RTL: first dish sits on the right
      const cx = size.w - (L.ox + rowOffset + L.cellW * (col + 0.5)) + jx;
      const cy = L.oy + L.cellH * (row + 0.5) + jy;
      // the stacked plates reach about 7% beyond the platter, so clamp that box
      const m = L.s * 0.08 + 6;
      const band = seatLayout().inset + seatLayout().plate * 0.6;
      const x = Math.min(size.w - L.s - m, Math.max(m, cx - L.s / 2));
      const y = Math.min(size.h - band - L.s * 1.06, Math.max(band, cy - L.s / 2));
      el.style.setProperty("--x", `${x}px`);
      el.style.setProperty("--y", `${y}px`);

      const ghost = e.from === 0 && e.to !== undefined;
      const removing = e.to !== undefined && e.to <= 0;
      const changing = e.to !== undefined && e.from > 0 && e.to > 0 && e.to !== e.from;
      el.classList.toggle("platter--ghost", ghost);
      el.classList.toggle("platter--top", row === 0 && L.rows > 1);
      el.classList.toggle("platter--removing", removing);
      el.classList.toggle("platter--changing", changing);
      const shown = e.to !== undefined ? e.to : e.qty;
      el.style.setProperty("--stack", String(Math.min(2, Math.max(0, (removing ? e.from : shown) - 1))));
      const qtyEl = el.querySelector(".platter__qty");
      qtyEl.innerHTML = changing ? `${e.from}<i class="ph ph-arrow-left" aria-hidden="true"></i>${e.to}` : ghost ? `<bdi dir="ltr">+${e.to}</bdi>` : removing ? "הסרה" : `<bdi dir="ltr">×${e.qty}</bdi>`;
      el.setAttribute("aria-label", changing ? `${dish.name}, מ־${e.from} ל־${e.to}, הצעה שממתינה לאישור` : removing ? `${dish.name}, הצעה להוריד` : `${dish.name}, ${shown} ${unitWord(dish, shown)}${ghost ? ", הצעה שממתינה לאישור" : ""}`);
      if (isNew) { void el.offsetWidth; el.classList.remove("platter--enter"); }
    });

    for (const [id, el] of platterEls) {
      if (seen.has(id)) continue;
      platterEls.delete(id);
      el.classList.add("platter--leave");
      el.addEventListener("transitionend", () => el.remove(), { once: true });
      setTimeout(() => el.remove(), 600);
    }
  }

  function render() {
    measure();
    if (!size.w) return;
    renderSeats();
    renderPlatters();
    const ghost = state.proposal?.changes.find((c) => !state.items[c.id] && c.to > 0);
    highlightReach(ghost?.id ?? null, { qty: ghost?.to, cls: "is-proposed" });
  }

  const ro = new ResizeObserver(() => render());
  ro.observe(root);

  return {
    el: root,
    dropTarget: tableEl,
    update(next) {
      state = { ...state, ...next };
      render();
    },
    pulse(id) {
      const el = platterEls.get(id);
      if (!el) return;
      el.classList.remove("platter--pulse");
      void el.offsetWidth;
      el.classList.add("platter--pulse");
    },
    destroy() { ro.disconnect(); },
  };
}
