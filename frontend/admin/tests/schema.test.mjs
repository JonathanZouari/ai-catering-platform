// Compares the static schema with the real migration, so the offline explorer cannot drift.
// Set CATERING_MIGRATIONS_DIR to read the migration from another checkout.
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { GROUPS, RELATIONS, TABLES, formColumns, getTable, labelSelect, primaryKey } from "../js/schema.js";

const here = dirname(fileURLToPath(import.meta.url));
const migrationsDir = process.env.CATERING_MIGRATIONS_DIR ?? resolve(here, "../../../supabase/migrations");
const hasMigrations = existsSync(migrationsDir);
const skip = hasMigrations ? false : `migrations not found at ${migrationsDir}`;

function foundationSql() {
  const file = readdirSync(migrationsDir).find((name) => name.endsWith("foundation.sql"));
  return readFileSync(join(migrationsDir, file), "utf8");
}

// Splits a CREATE TABLE body on commas that are not inside parentheses.
function splitTopLevel(body) {
  const parts = [];
  let depth = 0;
  let current = "";
  for (const char of body) {
    if (char === "(") depth += 1;
    if (char === ")") depth -= 1;
    if (char === "," && depth === 0) {
      parts.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  if (current.trim()) parts.push(current.trim());
  return parts;
}

function parseMigration(sql) {
  sql = sql.replace(/^\s*--[^\n]*/gm, "");
  const tables = new Map();
  const relations = [];
  for (const match of sql.matchAll(/CREATE TABLE public\.(\w+) \(([\s\S]*?)\n\);/g)) {
    const [, name, body] = match;
    const columns = [];
    for (const part of splitTopLevel(body)) {
      const composite = /^FOREIGN KEY \(([^)]+)\)\s+REFERENCES public\.(\w+)\s*\(([^)]+)\)/.exec(part);
      if (composite) {
        relations.push({
          from: name,
          columns: composite[1].split(",").map((text) => text.trim()),
          to: composite[2],
          toColumns: composite[3].split(",").map((text) => text.trim()),
        });
        continue;
      }
      if (/^(CHECK|UNIQUE|PRIMARY KEY)\b/.test(part)) continue;
      const column = /^(\w+)\s/.exec(part)[1];
      columns.push(column);
      const inline = /REFERENCES public\.(\w+)\s*\((\w+)\)/.exec(part);
      if (inline) relations.push({ from: name, columns: [column], to: inline[1], toColumns: [inline[2]] });
    }
    tables.set(name, columns);
  }
  return { tables, relations };
}

const relationKey = (relation) => `${relation.from}(${relation.columns})->${relation.to}(${relation.toColumns})`;

test("the static schema lists the same 16 tables as the migration", { skip }, () => {
  const { tables } = parseMigration(foundationSql());
  assert.equal(tables.size, 16);
  assert.deepEqual(TABLES.map((table) => table.name).sort(), [...tables.keys()].sort());
});

test("every table has the same columns as the migration", { skip }, () => {
  const { tables } = parseMigration(foundationSql());
  for (const table of TABLES) {
    const known = table.columns.filter((column) => !column.addedByLaterMigration).map((column) => column.name);
    assert.deepEqual([...known].sort(), [...tables.get(table.name)].sort(), table.name);
  }
});

test("every foreign key in the migration is described, with no extras", { skip }, () => {
  const { relations } = parseMigration(foundationSql());
  assert.deepEqual(RELATIONS.map(relationKey).sort(), relations.map(relationKey).sort());
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

test("only the six agreed tables are editable, never the append-only ones", () => {
  const editable = TABLES.filter((table) => table.editable).map((table) => table.name).sort();
  assert.deepEqual(editable, ["addresses", "customers", "dishes", "employees", "equipment_items", "ingredients"]);
  for (const name of ["payments", "equipment_movements", "ingredient_movements", "order_items", "order_submissions"]) {
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

test("lookups alias the readable column, including inside the dish document", () => {
  assert.equal(labelSelect(getTable("customers")), "id,label:full_name");
  assert.equal(labelSelect(getTable("dishes")), "id,label:metadata->>name");
  assert.equal(labelSelect(getTable("orders")), null);
});
