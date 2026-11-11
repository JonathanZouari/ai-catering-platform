import { $ } from "../dom.js";
import { esc } from "../dom.js";
import { dateLong, money, moneyHTML } from "../format.js";
import { byId, session } from "../session.js";

const m$ = moneyHTML;
const items = (n) => (n === 1 ? "פריט אחד" : `${n} פריטים`);

function orderLines() {
  // DEMO ONLY. The real build must render server pricing from
  // GET /api/orders/{id} and GET /api/orders/{id}/pricing, and send `version`
  // on every change. The browser never computes authoritative prices (ADR 0003).
  return [...session.state.order].map(([key, q]) => {
    const [id, vid] = key.split(":");
    const d = byId(id);
    const v = d.variants.find((x) => x.id === vid);
    return { d, v, q, total: q * v.price };
  });
}

export function renderOrderSummary() {
  const lines = orderLines();
  const subtotal = lines.reduce((s, l) => s + l.total, 0);
  const count = lines.length;
  const { event, guests, units } = session;
  const body = $("#summary-body");
  const meta = `<p class="summary__meta">${guests} סועדים · ${dateLong(event.date)} · ${event.fulfillment}</p>`;
  if (!count) {
    body.innerHTML = meta + `<div class="summary__empty"><strong>עוד לא הוספתם מנות</strong><span>פתחו מנה בגלגל, בחרו גודל והוסיפו להזמנה. הסכום המצטבר יופיע כאן.</span></div>
      <a href="#" class="btn btn--primary btn--block summary__cta" aria-disabled="true" role="link">להצעת המחיר</a>`;
  } else {
    body.innerHTML = meta + `<ul class="lines">${lines.map(({ d, v, q, total }) => `
      <li class="line"><span class="line__name">${esc(d.name)} <span class="line__var">· ${esc(v.label)}</span></span>
      <span class="line__calc"><bdi>${esc(units[v.unit].count(q))}</bdi> × ${m$(v.price)}</span>
      <span class="line__total">${m$(total)}</span></li>`).join("")}</ul>
      <dl class="totals">
        <div><dt>סכום ביניים</dt><dd>${m$(subtotal)}</dd></div>
        <div><dt>דמי משלוח</dt><dd class="is-pending">יחושבו בשלב הבא</dd></div>
        <div class="grand"><dt>סה״כ משוער</dt><dd>${m$(subtotal)}</dd></div>
      </dl>
      <a href="#" class="btn btn--primary btn--block summary__cta">להצעת המחיר</a>`;
  }
  body.innerHTML += `<p class="summary__note"><svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 11v6M12 7.5v.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><span>המחירים יאושרו על ידי העסק לאחר שליחת הבקשה.</span></p>`;
  const badge = $("#bar-count");
  badge.textContent = count;
  badge.hidden = !count;
  $("#bar-count-sr").textContent = `הזמנה: ${items(count)}, סה״כ משוער `;
  $("#bar-total").textContent = money(subtotal);
  $("#total-live").textContent = `סה״כ משוער ${money(subtotal)}, ${items(count)}`;
}

export function bumpOrderBadge() {
  const b = $("#bar-count");
  b.classList.remove("is-bump");
  void b.offsetWidth;
  b.classList.add("is-bump");
}

export function mountOrderSheet() {
  const summary = $("#summary");
  const scrim = $("#scrim");
  const barToggle = $("#bar-toggle");

  function setSheet(open) {
    summary.classList.toggle("is-open", open);
    scrim.hidden = !open;
    barToggle.setAttribute("aria-expanded", String(open));
    if (open) $("#summary-close").focus();
    else barToggle.focus();
  }

  barToggle.addEventListener("click", () => setSheet(!summary.classList.contains("is-open")));
  $("#summary-close").addEventListener("click", () => setSheet(false));
  scrim.addEventListener("click", () => setSheet(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && summary.classList.contains("is-open")) setSheet(false);
  });

  return { setSheet };
}
