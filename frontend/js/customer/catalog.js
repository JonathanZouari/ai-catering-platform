// Loads the real catalog (GET /api/catalog/categories + /dishes) and maps it to the shape the
// views already use, so dish cards, filters and the order sidebar need no changes.
import { api } from "../api.js";
import { supabase } from "../supabase.js";
import { setCatalog } from "./mock-backend.js";
import { remapItems } from "./store.js";

// Presentation keys for the illustrations (CATEGORY_ART) and the "missing category" hint.
// A category the owner adds later has no key and simply uses its database id.
const CATEGORY_KEYS = {
  "סלטים ומטבלים": "salads",
  "עיקריות": "mains",
  "דגים": "fish",
  "תוספות ולחמים": "sides",
  "קינוחים": "desserts",
  "שתייה": "drinks",
};

const UNITS = { per_tray: "tray", per_weight: "kg", per_item: "item", per_guest: "guest" };

/**
 * UI contract: an array is a verified list (empty = verified none); null = unknown.
 * If any allergen is unknown the whole dish is shown as unknown: a partial list would read as
 * "everything else is safe", and unknown is never shown as safe (Decision 9).
 */
function toAllergens(list) {
  if (!list.length || list.some((a) => a.status === "unknown")) return null;
  return list.filter((a) => a.status === "contains").map((a) => a.name);
}

function toDish(d, categoryIds) {
  return {
    id: d.id,
    categoryId: categoryIds.get(d.category_id) ?? d.category_id,
    name: d.name,
    description: d.description ?? "",
    image: d.image_url ?? undefined,
    price: Number(d.unit_price),
    unit: UNITS[d.pricing_unit],
    perGuest: d.per_guest ?? undefined,
    step: d.qty_step ?? undefined,
    kashrut: d.dietary.kashrut,
    vegetarian: d.dietary.is_vegetarian,
    vegan: d.dietary.is_vegan,
    allergens: toAllergens(d.allergens),
  };
}

let loading = null;

/** Fetches once per page load (or again after refreshCatalog); a failure can be retried. */
export function loadCatalog() {
  loading ??= Promise.all([api("/api/catalog/categories"), api("/api/catalog/dishes")])
    .then(([rawCategories, rawDishes]) => {
      const categoryIds = new Map(rawCategories.map((c) => [c.id, CATEGORY_KEYS[c.name] ?? c.id]));
      const categories = rawCategories.map((c) => ({ id: categoryIds.get(c.id), name: c.name }));
      const dishes = rawDishes.filter((d) => UNITS[d.pricing_unit]).map((d) => toDish(d, categoryIds));
      remapItems(setCatalog(categories, dishes));
    })
    .catch((error) => {
      loading = null;
      throw error;
    });
  return loading;
}

export function refreshCatalog() {
  loading = null;
  return loadCatalog();
}

/* ---------------- live updates ---------------- */
// The owner's edits (price, availability, a new photo) reach open menus through Supabase
// Realtime. Every catalog write bumps the single row of catalog_changes (a trigger in the
// database); the event only says "something changed" and prices still come from the backend API.
// Subscribing to the catalog tables themselves would miss hidden dishes: Realtime checks RLS on
// the new row, and a hidden dish is no longer readable by customers.
const listeners = new Set();
let channel = null;
let timer = null;

function changed() {
  clearTimeout(timer);
  timer = setTimeout(() => {
    refreshCatalog().then(() => listeners.forEach((fn) => fn())).catch(() => {
      /* keep showing the last good catalog; the next change retries */
    });
  }, 300);
}

/** Calls fn after the catalog was reloaded because of a change. Returns an unsubscribe. */
export function watchCatalog(fn) {
  listeners.add(fn);
  if (!channel) {
    channel = "pending";
    supabase().then((client) => {
      if (!client) return;
      channel = client.channel("catalog")
        .on("postgres_changes", { event: "UPDATE", schema: "public", table: "catalog_changes" }, changed)
        .subscribe();
    }).catch(() => {
      channel = null; /* live updates are an extra; the menu works without them */
    });
  }
  return () => listeners.delete(fn);
}
