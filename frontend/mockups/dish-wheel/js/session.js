// Screen state for this preview. Prices in `order` are sample figures from loadCatalog().
export const session = {
  dishes: [],
  categories: [],
  units: null,
  event: null,
  guests: 0,
  state: {
    k: 0,
    open: false,
    variant: new Map(),
    pending: new Map(),
    order: new Map(),
  },
};

export const hooks = {
  onActiveChange() {},
  onOrderChange() {},
};

const mod = (n, m) => ((n % m) + m) % m;

export const dishCount = () => session.dishes.length;
export const byId = (id) => session.dishes.find((d) => d.id === id);
export const activeDish = () => session.dishes[mod(session.state.k, session.dishes.length)];
export const catName = (id) => session.categories.find((c) => c.id === id).name;
export const variantOf = (d) => d.variants.find((v) => v.id === session.state.variant.get(d.id)) ?? d.variants[0];
export const keyOf = (d, v = variantOf(d)) => `${d.id}:${v.id}`;
export const startQty = (v) => v.preset ?? v.min ?? 1;
export const pendingQty = (d, v = variantOf(d)) =>
  session.state.pending.get(keyOf(d, v)) ?? session.state.order.get(keyOf(d, v)) ?? startQty(v);
export const fromPrice = (d) => Math.min(...d.variants.map((v) => v.price));
export { mod };
