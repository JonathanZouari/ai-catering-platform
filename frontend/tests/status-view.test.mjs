import assert from "node:assert/strict";
import { test } from "node:test";

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.events = {}; }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(name, fn) { this.events[name] = fn; }
  querySelector() { return null; }
  set textContent(value) { this.children = [String(value)]; }
  get textContent() { return this.children.map(c => typeof c === "string" ? c : c.textContent).join(" "); }
}
globalThis.Node = Element;
const events = {};
globalThis.document = {
  visibilityState: "visible", createElement: tag => new Element(tag), createTextNode: text => String(text),
  addEventListener: (name, fn) => { events[name] = fn; }, removeEventListener: name => delete events[name],
};
globalThis.window = { addEventListener: (name, fn) => { events[name] = fn; }, removeEventListener: name => delete events[name] };
const order = { id: 11, version: 1, status: "pending_approval", accessToken: "a".repeat(64),
  event: { type: "בדיקה", date: "2026-12-15", slot: "10:00-12:00", fulfillment: "pickup" },
  snapshot: { submittedAt: "2026-11-08", lines: [{ name: "חומוס", qty: "1 מגש", lineTotal: 85 }], total: 85, subtotal: 85, deliveryFee: 0 },
};
const storage = new Map([["catering.customer.draft.v1", JSON.stringify({ order, step: "status" })]]);
globalThis.localStorage = { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) };
const { mountStatus } = await import("../js/customer/views/status.js");

test("visible pending page polls and renders live owner decision; errors retain receipt; cleanup stops polling", async () => {
  const originalInterval = globalThis.setInterval;
  const originalClear = globalThis.clearInterval;
  const originalTimeout = globalThis.setTimeout;
  let poll;
  let cleared = false;
  globalThis.setInterval = (fn, ms) => { assert.equal(ms, 15000); poll = fn; return 987; };
  globalThis.clearInterval = id => { assert.equal(id, 987); cleared = true; };
  globalThis.setTimeout = () => 1; // confetti is unrelated to status correctness
  const root = new Element("main");
  const flush = () => new Promise(resolve => setImmediate(resolve));
  try {
    const cleanup = mountStatus(root);
    assert.match(root.textContent, /ממתין לאישור העסק/);
    let requests = 0;
    globalThis.fetch = async () => { requests++; return Response.json({}, { status: 503 }); };
    poll(); await flush();
    assert.match(root.textContent, /מוצג המצב האחרון/);
    assert.match(root.textContent, /ממתין לאישור העסק/);
    document.visibilityState = "hidden";
    poll(); await flush();
    assert.equal(requests, 1);
    document.visibilityState = "visible";
    globalThis.fetch = async () => { requests++; return Response.json({ ...order, status: "approved", version: 2, ownerNote: "אושר לבדיקה" }); };
    events.visibilitychange(); await flush();
    assert.match(root.textContent, /ההזמנה אושרה/);
    assert.match(root.textContent, /אושר לבדיקה/);
    assert.match(root.textContent, /85/);
    assert.doesNotMatch(root.textContent, /מוצג המצב האחרון/);
    poll(); await flush();
    assert.equal(requests, 2); // terminal orders do not keep polling
    cleanup();
    assert.equal(cleared, true);
    assert.deepEqual(events, {});
  } finally {
    globalThis.setInterval = originalInterval;
    globalThis.clearInterval = originalClear;
    globalThis.setTimeout = originalTimeout;
  }
});
