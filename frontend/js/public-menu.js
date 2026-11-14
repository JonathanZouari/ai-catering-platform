// The public menu (/menu/): every available dish, read-only, with no login and no order.
// Same cards as the order screen (js/menu.js) without the quantity controls. Text via textContent only.
import { api } from "/js/api.js";
import { hydrateIllustrations } from "/js/illustrations.js";
import { allergens, artFor, badges, el, icon, money, PER, safePhoto } from "/js/menu.js";

const $ = (id) => document.getElementById(id);
const state = { dishes: [], categories: [], category: "", diet: null, q: "" };

function visible(d) {
  // a search looks through the whole menu, not only the open category
  if (state.q ? !`${d.name} ${d.description ?? ""}`.includes(state.q) : state.category && d.category_id !== state.category) return false;
  if (d.dietary.kashrut_class === null) return true; // not food: diet filters don't apply
  if (state.diet === "vegan") return d.dietary.is_vegan === true;
  if (state.diet === "vegetarian") return d.dietary.is_vegetarian === true || d.dietary.is_vegan === true;
  return true;
}

function card(d, categoryName) {
  const media = safePhoto(d)
    ? el("div", { className: "dish-media" }, el("img", { src: d.image_url, alt: "", loading: "lazy", width: 400, height: 300 }),
      d.image_is_placeholder ? el("span", { className: "photo-note", textContent: "תמונה להמחשה" }) : "")
    : el("div", { className: "dish-media no-photo in" }, icon(artFor(categoryName)));
  return el("article", { className: "dish static" }, media, el("div", { className: "dish-body" },
    el("h4", { textContent: d.name }),
    badges(d),
    d.description ? el("p", { className: "dish-desc", textContent: d.description }) : "",
    el("p", { className: "price num" }, money(d.unit_price), " ", el("span", { textContent: d.unit_label || PER[d.pricing_unit] })),
    allergens(d)));
}

function renderDishes() {
  const shown = state.dishes.filter(visible);
  $("no-dishes").hidden = shown.length > 0;
  const groups = state.categories.map((c) => [c, shown.filter((d) => d.category_id === c.id)]).filter(([, ds]) => ds.length);
  $("dishes").replaceChildren(...groups.map(([c, ds]) => el("section", { className: "dish-group" },
    el("h3", { className: "group-h" }, icon(artFor(c.name)), c.name, el("small", { textContent: ds.length === 1 ? "מנה אחת" : `${ds.length} מנות` })),
    el("div", { className: "dish-grid" }, ...ds.map((d) => card(d, c.name))))));
  hydrateIllustrations($("dishes"));
}

function renderCategories() {
  const tab = (id, name) => {
    const b = el("button", { type: "button", className: "chip-btn cat-tab" }, icon(id ? artFor(name) : "plate"), name);
    b.setAttribute("aria-pressed", String(state.category === id));
    b.addEventListener("click", () => { state.category = id; renderCategories(); renderDishes(); $("categories").querySelector('[aria-pressed="true"]').focus(); });
    return b;
  };
  $("categories").replaceChildren(...state.categories.map((c) => tab(c.id, c.name)), tab("", "כל התפריט"));
  hydrateIllustrations($("categories"));
}

export async function initPublicMenu() {
  try {
    const [dishes, categories, business] = await Promise.all([
      api("/api/catalog/dishes"), api("/api/catalog/categories"), api("/api/catalog/business"),
    ]);
    const cert = business.kashrut_certificate;
    $("kashrut-line").textContent = `המטבח כשר${cert ? ` (${cert})` : ""}: מנות בשריות ופרווה בלבד, בלי חלבי.`;
    state.dishes = dishes;
    state.categories = categories;
    state.category = categories[0]?.id ?? "";
  } catch {
    $("page-notice").textContent = "לא הצלחנו לטעון את התפריט. נסו לרענן את הדף.";
    $("page-notice").hidden = false;
    return;
  }
  for (const b of $("diet-filters").querySelectorAll("button")) {
    b.addEventListener("click", () => {
      state.diet = state.diet === b.dataset.diet ? null : b.dataset.diet;
      for (const o of $("diet-filters").querySelectorAll("button")) o.setAttribute("aria-pressed", String(o.dataset.diet === state.diet));
      renderDishes();
    });
  }
  $("dish-search").addEventListener("input", (e) => { state.q = e.target.value.trim(); renderDishes(); });
  renderCategories();
  renderDishes();
  $("menu").hidden = false;
}
