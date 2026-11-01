// Client-side order draft. The backend stays authoritative for prices and status
// (ADR 0003); this store only mirrors the draft so the UI can react instantly.
import { DISH_BY_ID, DELIVERY_ZONES, EVENT_TYPES, balance } from "./data.js";

const KEY = "yumi.order.v1";

const blank = () => ({
  event: {
    type: "יום הולדת",
    date: "",
    slot: "",
    adults: 48,
    children: 16,
    notes: "",
    fulfillment: "delivery",
    zone: "center",
    address: "",
  },
  items: {},
  manual: {},
  proposal: null,
  status: "draft",
  ownerNote: "",
  version: 1,
  submittedAt: null,
});

// Stored drafts may be partial or from an older shape; never trust them.
// A pending proposal is not restored: its chat card does not survive a reload.
export function normalize(p) {
  const b = blank();
  if (!p || typeof p !== "object") return b;
  const items = {};
  if (p.items && typeof p.items === "object") {
    for (const [id, q] of Object.entries(p.items)) { const n = Math.round(Number(q)); if (DISH_BY_ID[id] && n > 0) items[id] = n; }
  }
  const ev = { ...b.event, ...(p.event && typeof p.event === "object" ? p.event : {}) };
  for (const k of ["adults", "children"]) ev[k] = Math.max(0, Math.min(k === "adults" ? 120 : 80, Math.round(Number(ev[k]) || 0)));
  for (const k of ["type", "date", "slot", "notes", "fulfillment", "zone", "address"]) ev[k] = String(ev[k] ?? "");
  if (!EVENT_TYPES.includes(ev.type)) ev.type = b.event.type;
  if (!["delivery", "pickup"].includes(ev.fulfillment)) ev.fulfillment = "delivery";
  let status = ["draft", "pending", "approved", "rejected", "countered"].includes(p.status) ? p.status : "draft";
  let offer = null;
  if (status === "countered") {
    const ch = Array.isArray(p.offer?.changes) ? p.offer.changes.filter((c) => DISH_BY_ID[c?.id] && Number.isFinite(Number(c.to))).map((c) => ({ id: c.id, from: items[c.id] ?? 0, to: Math.max(0, Math.round(Number(c.to))) })).filter((c) => c.from !== c.to) : [];
    if (ch.length) offer = { changes: ch, note: String(p.offer.note ?? "") };
    else status = "pending";
  }
  const manual = {};
  if (p.manual && typeof p.manual === "object") for (const id of Object.keys(p.manual)) if (items[id]) manual[id] = true;
  const balanced = status === "draft" ? balance(items, { adults: ev.adults, children: ev.children }, manual) : items;
  return { ...b, event: ev, items: balanced, manual, proposal: null, status, offer, offerDeclined: !!p.offerDeclined, ownerNote: String(p.ownerNote ?? ""), version: Number(p.version) || 1, submittedAt: p.submittedAt ?? null };
}

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return normalize(JSON.parse(raw));
  } catch { /* storage unavailable: start fresh */ }
  return blank();
}

export function createStore(initial = load(), { persist = true } = {}) {
  let state = initial;
  const listeners = new Set();

  const emit = (change) => {
    if (persist) {
      try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* ignore */ }
    }
    listeners.forEach((fn) => fn(state, change));
  };

  const draft = () => state.status === "draft";
  const setItems = (items, change, manual = state.manual) => {
    if (!draft()) return;
    for (const id of Object.keys(manual)) if (!items[id]) { manual = { ...manual }; delete manual[id]; }
    state = { ...state, items: balance(items, guestsOf(state), manual), manual, version: state.version + 1 };
    emit(change);
  };

  return {
    get: () => state,
    // Take state written by another tab; notify without writing it back.
    replace(next) {
      state = next;
      listeners.forEach((fn) => fn(state, { type: "status" }));
    },
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },

    setEvent(patch) {
      if (!draft() && !("contactName" in patch)) return;
      // proposals are sized by guest count, so a guest change invalidates them
      const bump = ["adults", "children"].some((k) => k in patch && patch[k] !== state.event[k]) ? 1 : 0;
      state = { ...state, event: { ...state.event, ...patch }, version: state.version + bump };
      if (bump) state = { ...state, items: balance(state.items, guestsOf(state), state.manual) };
      emit({ type: "event", patch });
    },

    // First drop of a dish lands at the quantity the guest count calls for.
    add(id) {
      if (!draft()) return;
      const current = state.items[id] ?? 0;
      if (current) return this.setQty(id, current + 1);
      setItems({ ...state.items, [id]: 1 }, { type: "add", id });
    },
    setQty(id, qty) {
      const items = { ...state.items };
      if (qty <= 0) delete items[id];
      else items[id] = qty;
      setItems(items, { type: qty <= 0 ? "remove" : "qty", id }, qty > 0 ? { ...state.manual, [id]: true } : state.manual);
    },
    remove(id) {
      const items = { ...state.items };
      delete items[id];
      setItems(items, { type: "remove", id });
    },
    restore(items, manual) {
      if (!draft()) return;
      state = { ...state, items: { ...items }, manual: { ...manual }, version: state.version + 1 };
      emit({ type: "restore" });
    },
    clear() { setItems({}, { type: "clear" }); },

    propose(proposal) {
      if (!draft()) return;
      state = { ...state, proposal: { ...proposal, baseVersion: state.version, status: "pending" } };
      emit({ type: "proposal" });
    },
    resolveProposal(accept) {
      const p = state.proposal;
      if (!p) return;
      if (accept && p.baseVersion === state.version) {
        const items = { ...state.items };
        const manual = { ...state.manual };
        for (const c of p.changes) {
          if (c.to <= 0) { delete items[c.id]; delete manual[c.id]; }
          else { items[c.id] = c.to; if (p.pinned?.includes(c.id)) manual[c.id] = true; }
        }
        // exactly the quantities the card showed; no further rebalancing
        state = { ...state, proposal: null, items, manual, version: state.version + 1 };
        emit({ type: "proposal-applied", changes: p.changes });
      } else {
        state = { ...state, proposal: null };
        emit({ type: accept ? "proposal-expired" : "proposal-rejected" });
      }
    },

    submit() {
      state = { ...state, status: "pending", submittedAt: new Date().toISOString(), proposal: null, offer: null, offerDeclined: false };
      emit({ type: "status" });
    },
    setStatus(status, ownerNote = "", offer = null, offerDeclined = false) {
      state = { ...state, status, ownerNote, offer: status === "countered" ? offer : null, offerDeclined };
      emit({ type: "status" });
    },
    // The owner answered with changed quantities; the customer accepts or declines.
    answerOffer(accept) {
      const o = state.offer;
      if (state.status !== "countered" || !o) return;
      if (accept) {
        const items = { ...state.items };
        for (const c of o.changes) { if (c.to <= 0) delete items[c.id]; else items[c.id] = c.to; }
        if (!Object.keys(items).length) return;
        state = { ...state, items, status: "approved", ownerNote: o.note, offer: null, offerDeclined: false, version: state.version + 1 };
      } else {
        state = { ...state, status: "pending", ownerNote: "", offer: null, offerDeclined: true };
      }
      emit({ type: "status", offer: accept ? "accepted" : "declined" });
    },
    reset() { state = blank(); emit({ type: "reset" }); },
  };
}

export const guestsOf = (s) => ({ adults: s.event.adults, children: s.event.children });

export function totals(state, items = state.items) {
  const lines = Object.entries(items)
    .filter(([id, q]) => DISH_BY_ID[id] && q > 0)
    .map(([id, qty]) => {
      const dish = DISH_BY_ID[id];
      return { dish, qty, line: qty * dish.price };
    });
  const subtotal = lines.reduce((s, l) => s + l.line, 0);
  const zone = DELIVERY_ZONES.find((z) => z.id === state.event.zone);
  const delivery = state.event.fulfillment === "delivery" && lines.length ? (zone?.fee ?? 0) : 0;
  return { lines, subtotal, delivery, total: subtotal + delivery };
}

// How many guests this order can feed per course, so the table can say what is missing.
export function coverage(state) {
  const g = guestsOf(state);
  const need = g.adults + g.children * 0.5;
  const byCat = {};
  for (const [id, qty] of Object.entries(state.items)) {
    const d = DISH_BY_ID[id];
    if (!d) continue;
    const portions = d.serves === 1 ? qty * 0.5 : d.kids ? qty * d.serves * 0.5 : qty * d.serves;
    byCat[d.category] = (byCat[d.category] ?? 0) + portions;
  }
  return { need, byCat };
}

export const STATUS_LABEL = {
  draft: "טיוטה",
  pending: "ממתינה לאישור העסק",
  approved: "אושרה על ידי העסק",
  countered: "בעל העסק הציע שינוי",
  rejected: "לא אושרה",
};
