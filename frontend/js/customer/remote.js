// Calls to the real backend for the parts of the flow that are no longer mocked:
// availability (event step), order submission (summary step) and order status.
import { api } from "../api.js";
import { applyAvailability, qtyLabel } from "./mock-backend.js";

export const UNITS = { per_tray: "tray", per_weight: "kg", per_item: "item", per_guest: "guest" };

export async function loadAvailability() {
  try {
    applyAvailability(await api("/api/availability"));
  } catch (error) {
    // The mock placeholders stay in place; submitting will report the real error.
    console.warn("availability not loaded", error);
  }
}

// The API sends agorot; the views use shekels.
const shekels = (agorot) => agorot / 100;

/** Maps the API's frozen order snapshot to the shape the status view renders. */
export function toSnapshot(order) {
  const s = order.snapshot;
  return {
    submittedAt: order.submitted_at,
    lines: s.lines.map((l) => ({
      name: l.name,
      qty: qtyLabel({ unit: UNITS[l.pricing_unit] }, l.quantity),
      unitPrice: shekels(l.unit_price),
      lineTotal: shekels(l.line_total),
    })),
    subtotal: shekels(s.subtotal),
    deliveryFee: shekels(s.delivery_fee),
    total: shekels(s.total),
  };
}

export const submitOrderRemote = (order) =>
  api("/api/orders", {
    method: "POST",
    body: JSON.stringify({
      event: order.event,
      contact: order.contact,
      items: Object.entries(order.items).map(([dish_id, quantity]) => ({ dish_id, quantity })),
    }),
  });

export const fetchOrder = (id) => api(`/api/orders/${id}`);
