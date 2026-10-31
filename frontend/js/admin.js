// Owner order screen (A1). Mock orders until /api/admin/orders exists; the order
// sent from the customer screen in this browser shows up live from shared storage.
import { DISH_BY_ID, DELIVERY_ZONES, money } from "./data.js";
import { totals, STATUS_LABEL } from "./order.js";
import { createTable } from "./table.js";

const KEY = "yumi.order.v1";
const $ = (s, el = document) => el.querySelector(s);
const bind = (n) => $(`[data-bind="${n}"]`);

const day = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
const MOCK = [
  { id: "Y-1042", name: "הדס ונתנאל כהן", phone: "054-6120937", status: "pending", submittedAt: day(-1),
    event: { type: "ברית", date: day(9), slot: "11:00 עד 12:00", adults: 52, children: 8, fulfillment: "delivery", zone: "sharon", address: "הנרקיסים 14, רעננה", notes: "סבתא צליאקית, נשמח לחלה בלי גלוטן אם אפשר" },
    items: { challah: 5, hummus: 4, eggplant: 5, tabbouleh: 4, salmon: 6, mujadara: 4, fruit: 3 } },
  { id: "Y-1039", name: "משפחת אברג'ל", phone: "052-8841206", status: "pending", submittedAt: day(-2),
    event: { type: "בר / בת מצווה", date: day(16), slot: "18:00 עד 19:00", adults: 74, children: 22, fulfillment: "delivery", zone: "center", address: "ויצמן 31, גבעתיים", notes: "" },
    items: { challah: 8, bourekas: 6, hummus: 6, eggplant: 7, chicken: 9, schnitzel: 3, potatoes: 7, fruit: 5 } },
  { id: "Y-1031", name: "צוות המעבדה, אורן תעשיות", phone: "03-7712490", status: "approved", submittedAt: day(-6), ownerNote: "מאושר. המשלוח יגיע 20 דקות לפני.",
    event: { type: "אירוע חברה", date: day(4), slot: "12:00 עד 13:00", adults: 38, children: 0, fulfillment: "pickup", zone: "center", address: "", notes: "4 טבעונים" },
    items: { hummus: 3, quinoa: 3, eggplant: 3, chicken: 4, potatoes: 3 } },
  { id: "Y-1027", name: "שירן לוי", phone: "050-3398217", status: "rejected", submittedAt: day(-8), ownerNote: "התאריך מלא אצלנו. אשמח להציע את יום ראשון שאחרי.",
    event: { type: "יום הולדת", date: day(2), slot: "17:00 עד 18:00", adults: 30, children: 12, fulfillment: "delivery", zone: "jlm", address: "עמק רפאים 40, ירושלים", notes: "" },
    items: { hummus: 3, schnitzel: 2, potatoes: 3, fruit: 2, malabi: 42 } },
];

function liveOrder() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!s || s.status === "draft" || !s.items || !Object.keys(s.items).length) return null;
    return { id: "Y-1043", live: true, name: s.event.contactName || "לקוח חדש", phone: s.event.contactPhone || "", ...s };
  } catch { return null; }
}

let filter = "pending";
let selected = null;
const FILTERS = [["pending", "ממתינות"], ["approved", "אושרו"], ["rejected", "לא אושרו"], ["all", "הכל"]];

function orders() {
  const live = liveOrder();
  return live ? [live, ...MOCK] : MOCK;
}

const fmtDay = (d) => new Date(d);
const fmtPhone = (p = "") => { const d = p.replace(/\D/g, ""); return d.length === 10 ? `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}` : p; };
const zoneOf = (o) => DELIVERY_ZONES.find((z) => z.id === o.event.zone);

function render() {
  const all = orders();
  const pending = all.filter((o) => o.status === "pending");
  bind("orders-summary").textContent = pending.length ? `${pending.length} בקשות מחכות לתשובה שלך` : "אין בקשות שמחכות לתשובה";
  bind("filters").innerHTML = FILTERS.map(([id, label]) => {
    const n = id === "all" ? all.length : all.filter((o) => o.status === id).length;
    return `<button class="chip" type="button" data-filter="${id}" aria-pressed="${filter === id}">${label}<span class="count num">${n}</span></button>`;
  }).join("");

  const list = all.filter((o) => filter === "all" || o.status === filter).sort((a, b) => a.event.date.localeCompare(b.event.date));
  if (!selected || !list.find((o) => o.id === selected)) selected = (list.find((o) => o.live && o.status === "pending") ?? list[0])?.id ?? null;
  bind("list").innerHTML = list.length ? list.map((o) => {
    const d = fmtDay(o.event.date);
    const t = totals(o);
    return `<li><button class="order-row" type="button" data-id="${o.id}" aria-current="${o.id === selected}">
      <span class="order-date"><b class="num">${d.getDate()}</b><span>${d.toLocaleDateString("he-IL", { month: "short" })}</span></span>
      <span><span class="order-row__who">${esc(o.name)}</span><br><span class="order-row__meta">${esc(o.event.type)}, ${o.event.adults + o.event.children} אורחים${o.live ? ` <span class="live"><i class="ph ph-broadcast" aria-hidden="true"></i>חדש</span>` : ""}</span></span>
      <span class="order-row__end"><span class="order-row__total num">${money(t.total)}</span><span class="badge badge--${o.status}">${STATUS_LABEL[o.status]}</span></span>
    </button></li>`;
  }).join("") : `<li class="receipt__empty">אין הזמנות בסינון הזה.</li>`;
  renderDetail(all.find((o) => o.id === selected));
}

let snapshot = null;
function renderDetail(o) {
  const el = bind("detail");
  snapshot?.destroy();
  if (!o) { el.innerHTML = `<p class="receipt__empty">בחרו הזמנה מהרשימה.</p>`; snapshot = null; return; }
  const t = totals(o);
  const e = o.event;
  const when = fmtDay(e.date).toLocaleDateString("he-IL", { weekday: "long", day: "numeric", month: "long" });
  el.innerHTML = `
    <div class="detail__head">
      <div>
        <span class="badge badge--${o.status}">${STATUS_LABEL[o.status]}</span>
        <h2 style="margin-top:10px">${esc(o.name)}</h2>
        <p>${esc(e.type)}, ${when}, ${esc(e.slot)}</p>
      </div>
      <dl class="review-list">
        <dt>הזמנה</dt><dd class="num">${o.id}</dd>
        <dt>טלפון</dt><dd class="num" dir="ltr">${esc(fmtPhone(o.phone) || "לא נמסר")}</dd>
        <dt>${e.fulfillment === "delivery" ? "משלוח" : "איסוף"}</dt><dd>${e.fulfillment === "delivery" ? `${esc(e.address || "")}${e.address ? ", " : ""}${zoneOf(o)?.label ?? ""}` : "מהמטבח"}</dd>
      </dl>
    </div>
    <div class="detail__grid">
      <div class="detail__table">
        <div data-snapshot></div>
        <p class="snapshot-note"><i class="ph ph-lock-simple" aria-hidden="true"></i>תמונת מצב קפואה של ההזמנה כפי שנשלחה: ${e.adults} מבוגרים ו־${e.children} ילדים</p>
      </div>
      <ul class="detail__lines">
        ${t.lines.map((l) => `<li><span>${l.dish.name}</span><span class="num">${l.qty} × ${money(l.dish.price)} = ${money(l.line)}</span></li>`).join("")}
        ${t.delivery ? `<li><span>משלוח, ${zoneOf(o)?.label}</span><span class="num">${money(t.delivery)}</span></li>` : ""}
        <li><span>סה״כ</span><span class="num">${money(t.total)}</span></li>
      </ul>
    </div>
    ${e.notes ? `<div class="detail__notes"><b>הערות הלקוח</b>${esc(e.notes)}</div>` : ""}
    ${o.status === "pending" ? `
      <form class="decide" data-decide>
        <div class="field">
          <label for="owner-note">הערה ללקוח</label>
          <textarea class="input" id="owner-note" rows="2" placeholder="למשל: מאושר, המשלוח יגיע חצי שעה לפני"></textarea>
          <span class="field__error" hidden>כשלא מאשרים, כדאי לכתוב ללקוח למה</span>
        </div>
        <div class="decide__actions">
          <button class="btn btn--primary" type="submit" value="approved"><i class="ph ph-check" aria-hidden="true"></i>אישור ההזמנה</button>
          <button class="btn btn--danger" type="submit" value="rejected">לא לאשר</button>
        </div>
      </form>` : o.ownerNote ? `<div class="owner-note"><b>ההערה שנשלחה ללקוח</b>${esc(o.ownerNote)}</div>` : ""}`;

  snapshot = createTable($("[data-snapshot]", el), { interactive: false });
  snapshot.update({ adults: e.adults, children: e.children, items: o.items, proposal: null });

  $("[data-decide]", el)?.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const status = ev.submitter?.value;
    const note = $("#owner-note").value.trim();
    const err = $(".field__error", el);
    if (status === "rejected" && !note) { err.hidden = false; $("#owner-note").focus(); return; }
    decide(o, status, note);
  });
}

function decide(o, status, note) {
  if (o.live) {
    try {
      const s = JSON.parse(localStorage.getItem(KEY));
      localStorage.setItem(KEY, JSON.stringify({ ...s, status, ownerNote: note }));
    } catch { /* ignore */ }
  } else {
    Object.assign(MOCK.find((m) => m.id === o.id), { status, ownerNote: note });
  }
  toast(status === "approved" ? `ההזמנה של ${esc(o.name)} אושרה` : `ההזמנה של ${esc(o.name)} לא אושרה, הלקוח יקבל את ההערה`);
  render();
}

const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const toastEl = bind("toast");
let tt;
function toast(text) {
  clearTimeout(tt);
  toastEl.innerHTML = `<span>${text}</span>`;
  toastEl.classList.add("is-on");
  tt = setTimeout(() => toastEl.classList.remove("is-on"), 3600);
}

bind("filters").addEventListener("click", (e) => {
  const b = e.target.closest("[data-filter]");
  if (b) { filter = b.dataset.filter; selected = null; render(); }
});
bind("list").addEventListener("click", (e) => {
  const b = e.target.closest("[data-id]");
  if (b) { selected = b.dataset.id; render(); if (innerWidth <= 960) bind("detail").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }
});
window.addEventListener("storage", (e) => { if (e.key === KEY) render(); });
render();
