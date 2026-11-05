// Column/FK drift is checked against real migrated Postgres in supabase/tests/mvp-postgres.mjs.
import assert from "node:assert/strict";
import { test } from "node:test";
import { GROUPS, RELATIONS, TABLES, formColumns, getTable, labelSelect, primaryKey } from "../js/schema.js";
const OUT_OF_SCOPE = /^(employees|deliveries|payments|equipment_|ingredient)/;
test("the schema describes all 17 MVP tables", () => {
  assert.equal(TABLES.length,17);
  assert.equal(new Set(TABLES.map(t=>t.name)).size,17);
  for (const name of ['ai_conversations','ai_messages','ai_change_proposals']) {
    assert.equal(getTable(name).hiddenFromData,true);
  }
});
test("out-of-scope tables are gone and credential rows are not browsable", () => {
  for (const table of TABLES) assert.doesNotMatch(table.name, OUT_OF_SCOPE);
  assert.equal(getTable("order_submissions").hiddenFromData, true);
  assert.deepEqual(primaryKey(getTable("order_submissions")), ["order_id"]);
  assert.deepEqual(primaryKey(getTable("delivery_zones")), ["id"]);
  assert.equal(getTable("dishes").columns.find((column) => column.name === "id").type, "id");
  assert.ok(!getTable("dishes").columns.some((column) => column.name === "metadata"));
});

test("relations and foreign key columns point at real tables and columns", () => {
  for (const relation of RELATIONS) {
    const from = getTable(relation.from);
    const to = getTable(relation.to);
    for (const name of relation.columns) assert.ok(from.columns.some((c) => c.name === name), `${relation.from}.${name}`);
    for (const name of relation.toColumns) assert.ok(to.columns.some((c) => c.name === name), `${relation.to}.${name}`);
  }
  for (const table of TABLES) {
    for (const column of table.columns.filter((c) => c.fk)) {
      const match = RELATIONS.some((r) => r.from === table.name && r.columns[0] === column.name && r.to === column.fk.table);
      assert.ok(match, `${table.name}.${column.name}`);
    }
  }
});

test("labels are Hebrew only, so English never mixes into a Hebrew line", () => {
  const latin = /[A-Za-z]/;
  for (const table of TABLES) {
    assert.ok(!latin.test(table.label) && !latin.test(table.description), table.name);
    for (const column of table.columns) {
      assert.ok(!latin.test(column.label), `${table.name}.${column.name}`);
      assert.ok(!latin.test(column.hint ?? ""), `${table.name}.${column.name} hint`);
      for (const label of Object.values(column.options ?? {})) assert.ok(!latin.test(label), label);
    }
  }
  for (const group of GROUPS) assert.ok(!latin.test(group.label));
});

test("only the agreed tables are editable, never order history", () => {
  const editable = TABLES.filter((table) => table.editable).map((table) => table.name).sort();
  assert.deepEqual(editable, ["addresses", "allergens", "customers", "dishes"]);
  for (const name of ["order_items", "order_submissions", "dish_dietary", "dish_allergens"]) {
    assert.ok(!getTable(name).editable, name);
    assert.ok(getTable(name).readOnlyReason, name);
  }
});

test("each table has a primary key and a home in a diagram group", () => {
  const groups = new Set(GROUPS.map((group) => group.id));
  for (const table of TABLES) {
    assert.ok(primaryKey(table).length > 0, table.name);
    assert.ok(groups.has(table.group), table.name);
  }
});

test("forms leave out identity keys and database-managed timestamps", () => {
  assert.deepEqual(formColumns(getTable("customers")).map((c) => c.name), ["full_name", "email", "phone"]);
});

test("the submission payload is text holding a document", () => {
  const payload = getTable("order_submissions").columns.find((column) => column.name === "payload");
  assert.equal(payload.type, "jsontext");
});

test("lookups alias the readable column", () => {
  assert.equal(labelSelect(getTable("customers")), "id,label:full_name");
  assert.equal(labelSelect(getTable("dishes")), "id,label:name");
  assert.equal(labelSelect(getTable("orders")), null);
});
