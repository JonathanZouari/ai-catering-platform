import { $, $$ } from "../dom.js";
import { esc } from "../dom.js";
import { moneyHTML } from "../format.js";
import { session } from "../session.js";
import { badgesHTML } from "./allergen-detail.js";

const m$ = moneyHTML;

export function renderDishList() {
  const cat = session.categories.find((c) => c.id === activeCategory());
  const list = session.dishes.filter((d) => d.category === cat.id);
  $("#list-title").textContent = cat.all;
  $("#list-count").textContent = list.length === 1 ? "מנה אחת" : `${list.length} מנות`;
  $("#dish-list").innerHTML = list.map((d) => `
    <li><article class="r-card ${d.is_available ? "" : "is-unavailable"}" id="card-${d.id}" aria-labelledby="name-${d.id}">
      <img class="r-card__img" src="${d.image}" alt="" loading="lazy" width="640" height="640">
      <div class="r-card__body">
        <h3 class="r-card__name" id="name-${d.id}">${esc(d.name)}</h3>
        <p class="r-card__desc">${esc(d.description)}</p>
        ${badgesHTML(d)}
        <p class="r-card__price">${d.is_available ? `החל מ־<strong>${m$(fromPrice(d))}</strong>` : `<span class="r-card__na">${esc(d.unavailable_reason)}</span>`}
          <span class="r-card__in" data-in="${d.id}"></span></p>
        <div class="r-card__actions">
          <button type="button" class="btn btn--secondary r-card__pick" data-act="pick" data-id="${d.id}">בחירת אפשרויות<span class="visually-hidden">: ${esc(d.name)}</span></button>
          <button type="button" class="tray__link" data-act="open" data-id="${d.id}">מה במנה ואלרגנים<span class="visually-hidden">: ${esc(d.name)}</span></button>
        </div>
      </div>
    </article></li>`).join("");
  syncInOrder();
}

function activeCategory() {
  const { dishes, state } = session;
  const n = dishes.length;
  const i = ((state.k % n) + n) % n;
  return dishes[i].category;
}

function fromPrice(d) {
  return Math.min(...d.variants.map((v) => v.price));
}

export function syncInOrder() {
  $$("[data-in]").forEach((el) => {
    const n = [...session.state.order.keys()].filter((k) => k.startsWith(el.dataset.in + ":")).length;
    el.textContent = n ? "בהזמנה ✓" : "";
  });
}
