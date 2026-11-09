// Loads the live catalog into the arrays the views already read, and keeps it current through Realtime.
import { debounce } from "../lib/dom.js";
import { dishImageUrl, sb } from "../lib/supabase.js";
import { BLOCKED_DATES, CATEGORIES, DISHES, ZONES } from "./mock-backend.js";

const UNIT = { per_tray: "tray", per_weight: "kg", per_item: "item", per_guest: "guest" };

// ponytail: quantity placeholders (perGuest, step; OPEN #3) have no table yet, so each row is merged
// over its mock dish by name. Drop this and the fixed ids once quantity_rules exists.
const mockDishes = new Map(DISHES.map((d) => [d.name, d]));
const mockCategories = new Map(CATEGORIES.map((c) => [c.name, c.id]));

const listeners = new Set();

const unwrap = ({ data, error }) => {
  if (error) throw error;
  return data;
};

/** Unknown stays unknown: allergens are only a verified list when every allergen has a verified status. */
function allergenList(rows, allergenCount) {
  const verified = rows.length === allergenCount && rows.every((r) => r.status !== "unknown");
  return verified ? rows.filter((r) => r.status === "contains").map((r) => r.allergens.name) : null;
}

export async function loadCatalog() {
  const [categories, dishes, allergens, zones, blocked] = await Promise.all([
    sb.from("dish_categories").select("id,name").eq("is_active", true).order("sort_order").then(unwrap),
    sb.from("dishes").select("id,category_id,name,description,pricing_unit,unit_price,is_available,image_path,dish_dietary(kashrut_class,is_vegetarian,is_vegan),dish_allergens(status,allergens(name))").then(unwrap),
    sb.from("allergens").select("id").then(unwrap),
    sb.from("delivery_zones").select("name,fee").eq("is_active", true).then(unwrap),
    sb.from("blocked_dates").select("date").then(unwrap),
  ]);

  const categoryKey = new Map(categories.map((c) => [c.id, mockCategories.get(c.name) ?? c.id]));
  const liveNames = new Set(dishes.map((d) => d.name));
  const live = dishes.map((row) => {
    const mock = mockDishes.get(row.name);
    return {
      ...mock,
      id: mock?.id ?? row.id,
      dbId: row.id,
      categoryId: categoryKey.get(row.category_id),
      name: row.name,
      description: row.description ?? "",
      price: Number(row.unit_price),
      unit: UNIT[row.pricing_unit],
      available: row.is_available,
      image: dishImageUrl(row.image_path),
      kashrut: row.dish_dietary?.kashrut_class ?? null,
      vegetarian: row.dish_dietary?.is_vegetarian ?? false,
      vegan: row.dish_dietary?.is_vegan ?? false,
      allergens: allergenList(row.dish_allergens, allergens.length),
    };
  });
  // A dish removed from the database may still sit in a saved draft: keep it, but not orderable.
  const removed = [...mockDishes.values()].filter((d) => !liveNames.has(d.name)).map((d) => ({ ...d, available: false }));
  const order = new Map([...mockDishes.keys()].map((name, i) => [name, i]));
  live.sort((a, b) => (order.get(a.name) ?? Infinity) - (order.get(b.name) ?? Infinity));

  DISHES.splice(0, DISHES.length, ...live, ...removed);
  CATEGORIES.splice(0, CATEGORIES.length, ...categories.map((c) => ({ id: categoryKey.get(c.id), name: c.name })));
  ZONES.splice(0, ZONES.length, ...zones.map((z) => ({ city: z.name, fee: Number(z.fee) })));
  BLOCKED_DATES.splice(0, BLOCKED_DATES.length, ...blocked.map((b) => b.date));
}

export function onCatalogChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function watchCatalog() {
  const reload = debounce(async () => {
    await loadCatalog();
    listeners.forEach((fn) => fn());
  }, 300);
  const channel = sb.channel("catalog");
  for (const table of ["dishes", "dish_categories", "dish_dietary", "dish_allergens", "delivery_zones", "blocked_dates"]) {
    channel.on("postgres_changes", { event: "*", schema: "public", table }, reload);
  }
  channel.subscribe();
}
