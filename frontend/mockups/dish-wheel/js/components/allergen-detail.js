import { $ } from "../dom.js";
import { esc } from "../dom.js";
import { KASHRUT, moneyHTML } from "../format.js";
import { byId, session, variantOf } from "../session.js";

const m$ = moneyHTML;

export function badgesHTML(d) {
  const out = [];
  if (d.kashrut) out.push(`<span class="badge badge--${d.kashrut}"><span class="badge__dot" aria-hidden="true"></span>${KASHRUT[d.kashrut]}</span>`);
  else out.push(`<span class="badge badge--unknown">כשרות: לא אומתה</span>`);
  if (d.is_vegan === true) out.push(`<span class="badge badge--diet">טבעוני</span>`);
  else if (d.is_vegetarian === true) out.push(`<span class="badge badge--diet">צמחוני</span>`);
  if (d.is_vegan === null) out.push(`<span class="badge badge--unknown">טבעוני: לא אומת</span>`);
  return `<div class="badges">${out.join("")}</div>`;
}

const STATUS = {
  contains: { cls: "allergen--contains", icon: "!", text: (a) => `מכיל ${a}` },
  free: { cls: "allergen--free", icon: "✓", text: (a) => `ללא ${a}` },
  // Unknown is never rendered as safe.
  unknown: { cls: "allergen--unknown", icon: "?", text: (a) => `${a}: לא אומת – כדאי לברר עם העסק` },
};

const allergenHTML = (name, status) => {
  const s = STATUS[status];
  return `<span class="allergen ${s.cls}"><span class="allergen__icon" aria-hidden="true">${s.icon}</span>${esc(s.text(name))}</span>`;
};

function dialogHTML(d) {
  const v = variantOf(d);
  const unit = session.units[v.unit];
  return `<span class="dlg-handle" aria-hidden="true"></span>
  <button type="button" class="icon-btn dlg-close" data-act="close" aria-label="סגירת הפרטים">
    <svg aria-hidden="true" viewBox="0 0 24 24" width="22" height="22"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
  <div class="dlg-media"><img src="${d.image}" alt="${esc(d.alt)}"></div>
  <div class="dlg-scroll">
    <div class="dlg-body">
      ${badgesHTML(d)}
      <h2 class="dlg-title" id="dlg-title">${esc(d.name)}</h2>
      <p class="dlg-desc">${esc(d.description)}</p>
      <h3 class="dlg-h3">מה במנה</h3>
      <div class="legend" aria-label="מקרא אלרגנים"><span class="allergen allergen--contains"><span class="allergen__icon" aria-hidden="true">!</span>מכיל</span><span class="allergen allergen--free"><span class="allergen__icon" aria-hidden="true">✓</span>ללא</span><span class="allergen allergen--unknown"><span class="allergen__icon" aria-hidden="true">?</span>לא אומת</span></div>
      <ul class="components">${d.components.map((c) => `
        <li class="component"><span class="component__name">${esc(c.name)}</span>
          <div class="component__allergens">${c.allergens.length
            ? c.allergens.map(([a, st]) => allergenHTML(a, st)).join("")
            : `<span class="allergen allergen--unknown"><span class="allergen__icon" aria-hidden="true">?</span>אין מידע על אלרגנים – לא אומת, כדאי לברר עם העסק</span>`}</div>
        </li>`).join("")}</ul>
      <p class="disclaimer"><strong>יש אלרגיה?</strong> ״לא אומת״ פירושו שהעסק עוד לא אישר את המידע, וזה לא אומר שהמנה נקייה מהאלרגן. אם למישהו מהאורחים יש אלרגיה, כדאי לברר עם העסק לפני ההזמנה.</p>
    </div>
    <div class="dlg-foot">
      <p class="price"><span class="price__amount">${m$(v.price)}</span><span class="price__unit">${esc(v.label)} · ${unit.per}</span></p>
      <button type="button" class="btn btn--primary" data-act="close">חזרה לאפשרויות</button>
    </div>
  </div>`;
}

export function mountAllergenDialog() {
  const dlg = $("#dish-dialog");
  let lastTrigger = null;

  function openDish(id, trigger) {
    lastTrigger = trigger;
    $("#dlg-content").innerHTML = dialogHTML(byId(id));
    dlg.showModal();
    $(".dlg-close", dlg).focus();
  }

  dlg.addEventListener("close", () => lastTrigger?.focus());
  dlg.addEventListener("click", (e) => {
    if (e.target === dlg) dlg.close();
    if (e.target.closest("[data-act='close']")) dlg.close();
  });

  return { openDish, close: () => dlg.close() };
}
