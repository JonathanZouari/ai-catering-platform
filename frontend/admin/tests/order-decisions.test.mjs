import assert from "node:assert/strict";
import { test } from "node:test";
import { submitDecision, openOrderDecision } from "../js/order-decisions.js";

const client = { auth: { getSession: async () => ({ data: { session: { access_token: "test-owner-token" } } }) } };
test("decision goes through authenticated server with immutable expected version", async () => {
  globalThis.fetch = async (path, options) => {
    assert.equal(path, "/api/admin/orders/11/decision");
    assert.equal(options.method, "POST");
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers.Authorization, "Bearer test-owner-token");
    assert.deepEqual(JSON.parse(options.body), { decision: "rejected", expected_version: 1, note: "Reason" });
    return Response.json({ id: 11, version: 2, status: "rejected" });
  };
  assert.equal((await submitDecision({ client, orderId: 11, decision: "rejected", expectedVersion: 1, note: " Reason " })).status, "rejected");
});
test("missing session never sends a decision", async () => {
  globalThis.fetch = () => assert.fail("must not send");
  await assert.rejects(submitDecision({ client: { auth: { getSession: async () => ({ data: { session: null } }) } } }), { status: 401 });
});
test("session destroyed while retrieving credentials never sends a decision", async () => {
  globalThis.fetch = () => assert.fail("must not send");
  assert.equal(await submitDecision({ client, isAlive: () => false }), null);
});
test("version conflicts propagate and never report success", async () => {
  globalThis.fetch = async () => Response.json({ detail: "Changed" }, { status: 409 });
  await assert.rejects(submitDecision({ client, orderId: 11, decision: "approved", expectedVersion: 1, note: "" }), { status: 409 });
});

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.events = {}; this.value = ""; }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(name, fn) { this.events[name] = fn; }
  showModal() {}
  close() {}
  remove() {}
  set textContent(value) { this.children = [String(value)]; }
}
const find = (root, predicate) => predicate(root) ? root : root.children?.map(c => find(c, predicate)).find(Boolean);
const flush = () => new Promise(resolve => setImmediate(resolve));
function mount({ itemsError = false } = {}) {
  const body = new Element("body");
  globalThis.document = { body, createElement: tag => new Element(tag), getElementById: () => new Element("toast") };
  const readClient = { ...client, from: (table) => {
    const query = { select: () => query, eq: () => query,
      order: async () => ({ data: [{ name: "חומוס", quantity_milli: 1000, line_total_minor: 8500 }], error: itemsError }),
      single: async () => ({ data: { event_type: "בדיקה", event_date: "2026-12-15", adults: 20, children: 0 } }),
    }; return query;
  } };
  let saved = 0;
  openOrderDecision({ client: readClient, row: { id: 11, event_id: 11, version: 1, status: "pending_approval", total_minor: 8500 },
    isSessionAlive: () => true, onSaved: () => saved++, onSessionLost() {}, registerDialog() {} });
  return { body, saved: () => saved,
    button: text => find(body, n => n.tag === "button" && n.children.includes(text)),
    note: find(body, n => n.tag === "textarea") };
}
test("unavailable order details keep both decisions disabled", async () => {
  const ui = mount({ itemsError: true });
  await flush();
  assert.equal(ui.button("אישור ההזמנה").disabled, true);
  assert.equal(ui.button("דחיית הבקשה").disabled, true);
});
test("a rejected invalid body can be corrected without locking the decision", async () => {
  const ui = mount();
  await flush();
  globalThis.fetch = async () => Response.json({}, { status: 422 });
  await ui.button("אישור ההזמנה").events.click();
  assert.equal(ui.note.disabled, false);
  assert.equal(Boolean(ui.button("דחיית הבקשה").disabled), false);
  assert.equal(ui.saved(), 0);
});
test("lost decision response locks payload and prevents an opposing retry or double click", async () => {
  const ui = mount();
  await flush();
  ui.note.value = "Original note";
  let resolve;
  const bodies = [];
  globalThis.fetch = (_path, options) => { bodies.push(JSON.parse(options.body)); return new Promise(r => { resolve = r; }); };
  const first = ui.button("אישור ההזמנה").events.click();
  await flush();
  await ui.button("אישור ההזמנה").events.click();
  assert.equal(bodies.length, 1);
  resolve(Response.json({}, { status: 503 }));
  await first;
  assert.equal(ui.note.disabled, true);
  assert.equal(ui.button("דחיית הבקשה").disabled, true);
  assert.equal(ui.saved(), 0);
  ui.note.value = "Changed by caller";
  globalThis.fetch = async (_path, options) => { bodies.push(JSON.parse(options.body)); return Response.json({}, { status: 409 }); };
  await ui.button("אישור ההזמנה").events.click();
  assert.deepEqual(bodies[1], bodies[0]);
  assert.equal(ui.button("אישור ההזמנה").disabled, true);
  assert.equal(ui.saved(), 1); // refresh the list on conflict, not a success notification
});
