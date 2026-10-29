// C2 dish catalogue + C3 running total. Hebrew RTL preview.
// Totals below are demo-only. The real screen must render server pricing
// (GET /api/orders/{id} and /pricing) and never price the order in the browser.
import { $ } from "./dom.js";
import { dateLong, dateShort } from "./format.js";
import { loadCatalog } from "./mock/catalog.js";
import { activeDish, byId, hooks, session, startQty } from "./session.js";
import { mountAllergenDialog } from "./components/allergen-detail.js";
import { renderDishList, syncInOrder } from "./components/dish-card.js";
import {
  mountDishWheel,
  paintWheel,
  rememberCategory,
  renderCats,
  renderDetail,
  rotateTo,
  setK,
  setOpen,
} from "./components/dish-wheel.js";
import { bumpOrderBadge, mountOrderSheet, renderOrderSummary } from "./components/order-summary.js";

const params = new URLSearchParams(location.search);
if (params.get("dir") === "ltr") document.documentElement.dir = "ltr";

const catalog = await loadCatalog();
session.dishes = catalog.dishes;
session.categories = catalog.categories;
session.units = catalog.units;
session.event = catalog.event;
session.guests = catalog.guests;

$("#event-short").textContent = `${dateShort(catalog.event.date)} · ${catalog.guests} סועדים`;
$("#event-link").setAttribute(
  "aria-label",
  `האירוע: ${dateLong(catalog.event.date)}, ${catalog.guests} סועדים. עריכת פרטי האירוע`,
);

hooks.onActiveChange = ({ categoryChanged }) => {
  if (categoryChanged) renderDishList();
  else syncInOrder();
};
hooks.onOrderChange = ({ bump }) => {
  if (bump) bumpOrderBadge();
  renderOrderSummary();
  syncInOrder();
};

const dialog = mountAllergenDialog();
const sheet = mountOrderSheet();
mountDishWheel();

paintWheel();
renderCats();
rememberCategory();
renderDishList();
renderDetail();
renderOrderSummary();

params.get("add")?.split(",").forEach((pair) => {
  const [id, vid] = pair.split(":");
  const d = byId(id);
  if (!d) return;
  const v = d.variants.find((x) => x.id === vid) ?? d.variants[0];
  session.state.order.set(`${id}:${v.id}`, startQty(v) + (v.unit === "guest" ? 0 : 1));
});
if (params.get("add")) {
  renderOrderSummary();
  syncInOrder();
}

const kParam = params.get("k") ?? (params.get("expand") && catalog.dishes.findIndex((d) => d.id === params.get("expand")));
if (kParam != null && kParam !== "" && Number(kParam) >= 0) setK(Number(kParam), { announce: false });
if (params.get("variant")) session.state.variant.set(activeDish().id, params.get("variant"));
if (params.get("expand")) setOpen(true);
if (params.get("open")) dialog.openDish(params.get("open"), null);
if (params.get("sheet")) sheet.setSheet(true);

document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-act]");
  if (!t) return;
  const { act, id } = t.dataset;
  if (act === "open") return dialog.openDish(id, t);
  if (act === "pick") {
    rotateTo(catalog.dishes.findIndex((d) => d.id === id), { collapse: false, announce: false });
    setOpen(true);
    $("#stage-wrap").scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "center",
    });
    $("input:checked", $("#detail"))?.focus({ preventScroll: true });
  }
  if (t.matches('[aria-disabled="true"]')) e.preventDefault();
});

requestAnimationFrame(() => document.body.classList.add("is-ready"));
