// Owner order screen (A1). Mock orders until /api/admin/orders exists; the order
// sent from the customer screen in this browser shows up live from shared storage.
import { DISH_BY_ID, DISHES, DELIVERY_ZONES, money, img, unitWord, recommendedQty } from "./data.js";
import { totals, STATUS_LABEL, normalize } from "./order.js";
import { createTable } from "./table.js";

const KEY = "yumi.order.v1";
const $ = (s, el = document) => el.querySelector(s);
const bind = (n) => $(`[data-bind="${n}"]`);

const day = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
const MOCK = [
  { id: "Y-1042", name: "הדס ונתנאל כהן", phone: "054-6120937", status: "pending", submittedAt: day(-1),
    event: { type: "ברית", date: day(6), slot: "11:00 עד 12:00", adults: 52, children: 8, fulfillment: "delivery", zone: "sharon", address: "הנרקיסים 14, רעננה", notes: "סבתא צליאקית, נשמח לחלה בלי גלוטן אם אפשר" },
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
    const raw = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!raw || raw.status === "draft" || !raw.status) return null;
    const s = normalize(raw);
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

const OWNER_LABEL = { ...STATUS_LABEL, pending: "מחכה לתשובה שלך", countered: "מחכה לתשובת הלקוח" };
const inFilter = (o, f) => f === "all" || o.status === f || (f === "pending" && o.status === "countered");

// Everything the kitchen has to make in the next 7 days, from requests that are
// approved or still open.
function renderPrep(all) {
  const now = Date.now();
  const week = all.filter((o) => ["approved", "pending", "countered"].includes(o.status) && (new Date(o.event.date) - now) / 864e5 <= 7 && new Date(o.event.date) >= now - 864e5);
  const firm = {}, open = {};
  for (const o of week) for (const [id, q] of Object.entries(o.items)) {
    const bucket = o.status === "approved" ? firm : open;
    bucket[id] = (bucket[id] ?? 0) + q;
  }
  const top = [...new Set([...Object.keys(firm), ...Object.keys(open)])]
    .map((id) => [id, firm[id] ?? 0, open[id] ?? 0])
    .sort((a, b) => b[1] + b[2] - (a[1] + a[2]));
  const guests = week.reduce((g, o) => g + o.event.adults + o.event.children, 0);
  const sure = week.filter((o) => o.status === "approved").length;
  bind("prep").innerHTML = week.length ? `
    <div class="prep__head"><h2>מה מכינים השבוע</h2><span class="num">${week.length} אירועים, ${guests} אורחים${sure < week.length ? `, ${week.length - sure === 1 ? "אחד מהם" : `${week.length - sure} מהם`} עוד פתוח` : ""}</span></div>
    <ul class="prep__list">${top.map(([id, f, o]) => `<li><img src="${img(id)}" alt="" width="44" height="44"><span class="num">${f ? `<b>${f}</b>` : ""}${f && o ? " " : ""}${o ? `<span class="open">${f ? "ועוד " : ""}${o} פתוחות</span>` : ""}</span><span class="prep__name">${DISH_BY_ID[id].name}, ${unitWord(DISH_BY_ID[id], f + o)}</span></li>`).join("")}</ul>` : "";
}

function render() {
  const all = orders();
  renderPrep(all);
  const pending = all.filter((o) => o.status === "pending");
  bind("orders-summary").textContent = pending.length ? `${pending.length} בקשות מחכות לתשובה שלך` : "אין בקשות שמחכות לתשובה";
  bind("filters").innerHTML = FILTERS.map(([id, label]) => {
    const n = all.filter((o) => inFilter(o, id)).length;
    return `<button class="chip" type="button" data-filter="${id}" aria-pressed="${filter === id}">${label}<span class="count num">${n}</span></button>`;
  }).join("");

  const list = all.filter((o) => inFilter(o, filter)).sort((a, b) => a.event.date.localeCompare(b.event.date));
  if (!selected || !list.find((o) => o.id === selected)) selected = (list.find((o) => o.live && o.status === "pending") ?? list[0])?.id ?? null;
  bind("list").innerHTML = list.length ? list.map((o) => {
    const d = fmtDay(o.event.date);
    const t = totals(o);
    return `<li><button class="order-row" type="button" data-id="${o.id}" aria-current="${o.id === selected}">
      <span class="order-date"><b class="num">${d.getDate()}</b><span>${d.toLocaleDateString("he-IL", { month: "short" })}</span></span>
      <span><span class="order-row__who">${esc(o.name)}</span><br><span class="order-row__meta">${esc(o.event.type)}, ${o.event.adults + o.event.children} אורחים${o.live ? ` <span class="live"><i class="ph ph-broadcast" aria-hidden="true"></i>חדש</span>` : ""}</span></span>
      <span class="order-row__end"><span class="order-row__total num">${money(t.total)}</span><span class="badge badge--${o.status}">${OWNER_LABEL[o.status]}</span></span>
    </button></li>`;
  }).join("") : `<li class="receipt__empty">אין הזמנות בסינון הזה.</li>`;
  renderDetail(all.find((o) => o.id === selected));
}

let snapshot = null;
const drafts = {};
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
        <span class="badge badge--${o.status}">${OWNER_LABEL[o.status]}</span>
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
        <p class="snapshot-note" data-snapnote><i class="ph ph-lock-simple" aria-hidden="true"></i>ההזמנה כפי שהלקוח שלח: ${e.adults} מבוגרים ו־${e.children} ילדים</p>
      </div>
      <div data-lines></div>
    </div>
    ${e.notes ? `<div class="detail__notes"><b>הערות הלקוח</b>${esc(e.notes)}</div>` : ""}
    ${o.offerDeclined && o.status === "pending" ? `<div class="detail__notes"><b>תשובת הלקוח</b>להשאיר את ההזמנה כמו שנשלחה.</div>` : ""}
    ${o.status === "countered" && o.offer ? `<div class="owner-note"><button class="btn btn--sm withdraw" type="button" data-withdraw>ביטול ההצעה</button><b>ההצעה שלך מחכה לתשובת הלקוח</b>${o.offer.changes.map((c) => `${DISH_BY_ID[c.id].name}: ${c.from === 0 ? `הוספה, ${c.to}` : c.to <= 0 ? "הסרה" : `מ־${c.from} ל־${c.to}`}`).join(". ")}${o.offer.note ? `. ${esc(o.offer.note)}` : ""}</div>` : ""}
    ${o.status === "pending" ? `
      <form class="decide" data-decide>
        <div class="field">
          <label for="owner-note">הערה ללקוח</label>
          <textarea class="input" id="owner-note" rows="2" placeholder="למשל: מאושר, המשלוח יגיע חצי שעה לפני">${esc(drafts[o.id]?.note ?? "")}</textarea>
          <span class="field__error" hidden>כשלא מאשרים, כדאי לכתוב ללקוח למה</span>
        </div>
        <div class="decide__actions" data-actions></div>
      </form>` : o.ownerNote ? `<div class="owner-note"><b>ההערה שנשלחה ללקוח</b>${esc(o.ownerNote)}</div>` : ""}`;

  snapshot = createTable($("[data-snapshot]", el), { interactive: false });
  const editable = o.status === "pending";
  const draft = (drafts[o.id] ??= { edits: {}, note: "" });
  let edits = draft.edits;
  const changes = () => Object.entries(edits).filter(([id, q]) => q !== (o.items[id] ?? 0)).map(([id, q]) => ({ id, from: o.items[id] ?? 0, to: q }));

  function renderEdits() {
    const ch = changes();
    const after = { ...o.items, ...edits };
    for (const k of Object.keys(after)) if (after[k] <= 0) delete after[k];
    const now = totals(o);
    const next = totals(o, after);
    const ids = [...new Set([...Object.keys(o.items), ...Object.keys(edits)])].filter((id) => DISH_BY_ID[id]);
    const focusId = document.activeElement?.closest?.("[data-line]")?.dataset.line;
    const focusAct = document.activeElement?.dataset?.step;
    $("[data-lines]", el).innerHTML = `
      <ul class="detail__lines">
        ${ids.map((id) => {
          const d = DISH_BY_ID[id];
          const q = after[id] ?? 0;
          const orig = o.items[id] ?? 0;
          const changed = q !== orig;
          return `<li data-line="${id}" class="${changed ? "is-changed" : ""}"><span>${d.name}${changed ? ` <small class="was num">${orig ? `במקור ${orig}` : "חדש"}</small>` : ""}</span>
            ${editable ? `<span class="line-edit"><span class="stepper stepper--sm"><button type="button" data-step="-1" aria-label="פחות ${d.name}"><i class="ph ph-minus"></i></button><output class="num">${q}</output><button type="button" data-step="1" aria-label="עוד ${d.name}"><i class="ph ph-plus"></i></button></span><span class="num">${money(q * d.price)}</span></span>`
                       : `<span class="num">${q} × ${money(d.price)} = ${money(q * d.price)}</span>`}</li>`;
        }).join("")}
        ${now.delivery ? `<li><span>משלוח, ${zoneOf(o)?.label}</span><span class="num">${money(now.delivery)}</span></li>` : ""}
        <li><span>סה״כ</span><span class="num">${ch.length ? `<s>${money(now.total)}</s> ` : ""}${money(next.total)}</span></li>
      </ul>
      ${editable ? `<div class="add-line"><label class="sr-only" for="add-dish">מנה להוספה</label><select class="input" id="add-dish" data-add><option value="">מנה להוספה להצעה</option>${DISHES.filter((d) => !ids.includes(d.id)).map((d) => `<option value="${d.id}">${d.name}</option>`).join("")}</select><button class="btn btn--sm" type="button" data-add-btn>הוספה</button></div>` : ""}`;
    if (focusId) $(`[data-line="${focusId}"] [data-step="${focusAct}"]`, el)?.focus();
    snapshot.update({ adults: e.adults, children: e.children, items: o.items, proposal: ch.length ? { changes: ch } : o.status === "countered" && o.offer ? { changes: o.offer.changes } : null, reserve: ["pending", "countered"].includes(o.status) ? 2 : 0 });
    const actions = $("[data-actions]", el);
    if (actions) {
      actions.innerHTML = ch.length
        ? `<button class="btn btn--accent" type="submit" value="countered"><i class="ph ph-paper-plane-tilt" aria-hidden="true"></i>שליחת ההצעה ללקוח</button><button class="btn btn--ghost" type="button" data-reset>ביטול השינויים</button>`
        : `<button class="btn btn--primary" type="submit" value="approved"><i class="ph ph-check" aria-hidden="true"></i>אישור ההזמנה</button><button class="btn btn--danger" type="submit" value="rejected">לא לאשר</button>`;
      $("[data-reset]", actions)?.addEventListener("click", () => { edits = draft.edits = {}; renderEdits(); });
      const empty = !Object.values(after).some((q) => q > 0);
      const send = $("button[value=countered]", actions);
      if (send && empty) { send.disabled = true; send.insertAdjacentHTML("afterend", `<span class="field__error">אי אפשר להציע הזמנה בלי מנות. כדי לסרב, ביטול השינויים ואז "לא לאשר".</span>`); }
      $("#owner-note", el)?.setAttribute("placeholder", ch.length ? "למשל: כדאי עוד מגש פרגיות, הילדים בדרך כלל לוקחים פעמיים" : "למשל: מאושר, המשלוח יגיע חצי שעה לפני");
    }
    const sn = $("[data-snapnote]", el);
    if (sn) sn.lastChild.textContent = ch.length ? "בקו מקווקו ובאדום: השינויים שלך, לפני שהם נשלחים ללקוח" : `ההזמנה כפי שהלקוח שלח: ${e.adults} מבוגרים ו־${e.children} ילדים`;
  }
  renderEdits();

  $("[data-lines]", el).addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-step]");
    if (!b) return;
    const id = b.closest("[data-line]").dataset.line;
    const cur = edits[id] ?? o.items[id] ?? 0;
    edits[id] = Math.max(0, cur + Number(b.dataset.step));
    renderEdits();
  });
  $("[data-lines]", el).addEventListener("click", (ev) => {
    if (!ev.target.closest("[data-add-btn]")) return;
    const id = $("[data-add]", el).value;
    if (!id) { $("[data-add]", el).focus(); return; }
    const after = { ...o.items, ...edits };
    edits[id] = recommendedQty(DISH_BY_ID[id], { adults: e.adults, children: e.children }, after);
    renderEdits();
    $(`[data-line="${id}"] [data-step="1"]`, el)?.focus();
  });
  $("#owner-note", el)?.addEventListener("input", (ev) => { draft.note = ev.target.value; });

  $("[data-withdraw]", el)?.addEventListener("click", () => decide(o, "pending", "", null));
  $("[data-decide]", el)?.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const status = ev.submitter?.value;
    const note = $("#owner-note").value.trim();
    const err = $(".field__error", el);
    if (status === "rejected" && !note) { err.hidden = false; $("#owner-note").focus(); return; }
    if (status === "countered" && ev.submitter.disabled) return;
    delete drafts[o.id];
    decide(o, status, note, status === "countered" ? { changes: changes(), note } : null);
  });
}

function decide(o, status, note, offer = null) {
  const patch = { status, ownerNote: note, offer, offerDeclined: false };
  if (o.live) {
    try {
      const s = JSON.parse(localStorage.getItem(KEY));
      localStorage.setItem(KEY, JSON.stringify({ ...s, ...patch }));
    } catch { /* ignore */ }
  } else {
    Object.assign(MOCK.find((m) => m.id === o.id), patch);
  }
  if (o.live) lastLive = status;
  toast({ approved: `ההזמנה של ${esc(o.name)} אושרה`, rejected: `ההזמנה של ${esc(o.name)} לא אושרה, הלקוח יקבל את ההערה`, countered: `ההצעה נשלחה ל${esc(o.name)}`, pending: "ההצעה בוטלה, ההזמנה חזרה אליך" }[status]);
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
let lastLive = liveOrder()?.status;
window.addEventListener("storage", (e) => {
  if (e.key !== KEY) return;
  const live = liveOrder();
  if (live && lastLive === "countered" && live.status !== "countered") {
    toast(live.status === "approved" ? `${esc(live.name)}: ההצעה שלך אושרה וההזמנה סגורה` : `${esc(live.name)}: ההזמנה נשארת כמו שנשלחה`);
    selected = live.id;
    filter = live.status === "approved" ? "approved" : "pending";
  }
  lastLive = live?.status;
  render();
});
render();
