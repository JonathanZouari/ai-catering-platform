import assert from "node:assert/strict";
import { test } from "node:test";
import { DISHES, newOrder } from "../js/customer/mock-backend.js";
import { addDays, toIsoDate } from "../js/lib/format.js";

const key = "catering.customer.draft.v1";
let moduleId = 0;
async function storeWith(order) {
  const data = new Map([[key, JSON.stringify({ order, step: "summary" })]]);
  globalThis.localStorage = {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
  };
  return import(`../js/customer/store.js?test=${++moduleId}`);
}

function draft() {
  const order = newOrder();
  order.event = { ...order.event, type: "יום הולדת", date: toIsoDate(addDays(new Date(), 20)), slot: "10:00-12:00" };
  order.contact = { name: "Test", phone: "0500000000" };
  order.items = { d1: 1 };
  return order;
}

DISHES.push({ id: "d1", name: "Test dish", price: 85, unit: "tray" });

test("failed transmission stays a draft; retry reuses its persisted credential", async () => {
  const store = await storeWith(draft());
  const tokens = [];
  globalThis.fetch = async (path, options) => {
    tokens.push(options.headers["X-Order-Token"]);
    assert.equal(JSON.parse(localStorage.getItem(key)).order.accessToken, tokens.at(-1));
    if (tokens.length === 1) throw new TypeError("offline");
    return Response.json({ ...draft(), id: 7, status: "pending_approval", snapshot: { total: 85 } });
  };
  assert.ok((await store.submitOrder()).errors.server);
  assert.equal(store.getState().order.status, "draft");
  assert.deepEqual((await store.submitOrder()).errors, {});
  assert.equal(tokens[0], tokens[1]);
  assert.equal(store.getState().order.id, 7);
});

test("reload after a lost response restores the receipt from the server", async () => {
  const order = { ...draft(), accessToken: "a".repeat(64) };
  const store = await storeWith(order);
  globalThis.fetch = async (path, options) => {
    assert.equal(path, "/api/orders/receipt");
    assert.equal(options.headers["X-Order-Token"], order.accessToken);
    return Response.json({ ...draft(), id: 9, status: "pending_approval", snapshot: { total: 85 } });
  };
  await store.restoreOrder();
  assert.equal(store.getState().order.id, 9);
  assert.equal(store.getState().step, "status");
});

test("legacy mock receipt is not displayed as a real submitted order", async () => {
  const store = await storeWith({ ...draft(), status: "pending_approval", snapshot: { total: 85 } });
  await store.restoreOrder();
  assert.equal(store.getState().order.status, "draft");
  assert.equal(store.getState().order.snapshot, null);
});

test("no submission when browser cannot retain its recovery credential", async () => {
  const store = await storeWith(draft());
  localStorage.setItem = () => { throw new Error("storage unavailable"); };
  globalThis.fetch = () => { assert.fail("must not transmit"); };
  assert.ok((await store.submitOrder()).errors.server);
  assert.equal(store.getState().order.status, "draft");
});
