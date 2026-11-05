// Renders real views on a minimal DOM whose append behaves like the native one: anything that is
// not a node becomes text. That is how an unspread array printed "[object HTMLElement]".
import assert from "node:assert/strict";
import { test } from "node:test";

class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.style = {};
    this.dataset = {};
    this.clientWidth = 1000;
    this.classList = { toggle() {} };
  }
  append(...items) {
    for (const item of items) this.children.push(item instanceof FakeNode ? item : String(item));
  }
  replaceChildren() {
    this.children = [];
  }
  setAttribute(name, value) {
    this.attrs[name] = value;
  }
  removeAttribute(name) {
    delete this.attrs[name];
  }
  addEventListener() {}
  querySelectorAll() {
    return [];
  }
  set textContent(value) {
    this.children = [String(value)];
  }
}

globalThis.document = {
  createElement: (tag) => new FakeNode(tag),
  createElementNS: (_ns, tag) => new FakeNode(tag),
};
globalThis.window = { addEventListener() {}, removeEventListener() {} };

const { renderErdView, renderSchemaView } = await import("../js/schema-views.js");
const { createDataView } = await import("../js/data-view.js");

function walk(node, visit) {
  visit(node);
  if (node instanceof FakeNode) node.children.forEach((child) => walk(child, visit));
}

function assertNoStrayText(root) {
  walk(root, (node) => {
    if (typeof node === "string") assert.doesNotMatch(node, /\[object |^false$|^true$|^null$|^undefined$/);
  });
}

function count(root, predicate) {
  let total = 0;
  walk(root, (node) => {
    if (node instanceof FakeNode && predicate(node)) total += 1;
  });
  return total;
}

test("the schema view renders all 17 table cards as elements", () => {
  const container = new FakeNode("div");
  renderSchemaView(container);
  assertNoStrayText(container);
  assert.equal(count(container, (node) => node.attrs.class === "schema-card"), 17);
});

test("the diagram renders 17 tables and 17 relationships", () => {
  const container = new FakeNode("div");
  renderErdView(container, { onOpenTable() {} });
  assertNoStrayText(container);
  assert.equal(count(container, (node) => node.attrs.class === "erd-node"), 17);
  assert.equal(count(container, (node) => node.tag === "path" && String(node.attrs.class).startsWith("erd-edge")), 17);
});

test("the data view toolbar prints no stray values", async () => {
  const query = {
    select: () => query,
    order: () => query,
    range: async () => ({ data: [], count: 0, error: null }),
  };
  const channel = { on: () => channel, subscribe: () => channel };
  const client = { from: () => query, channel: () => channel, removeChannel: async () => {} };
  const container = new FakeNode("div");
  const view = createDataView({ client, container, onSessionLost() {} });
  await new Promise((resolve) => setImmediate(resolve));
  assertNoStrayText(container);
  view.destroy();
});
