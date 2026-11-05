import assert from "node:assert/strict";
import { test } from "node:test";

import { replaceDishImage } from "../js/dish-images.js";
import {
  MAX_IMAGE_BYTES,
  buildDishImagePath,
  buildPatch,
  createRequestGuard,
  describeError,
  dishToFields,
  edgePath,
  escapeLike,
  formatCell,
  isLtrCell,
  isSessionInvalidError,
  jsonCellText,
  milliToInput,
  minorToInput,
  pageInfo,
  pageRange,
  parseCloudConfig,
  parseMilli,
  parseMoneyToMinor,
  sniffImageType,
  staffRoleOf,
  tokenHasStaffRole,
  validateColumn,
  validateColumns,
  validateDishForm,
  validateImageFile,
  validateTableRules,
} from "../js/helpers.js";
import { getTable } from "../js/schema.js";

const jwt = (payload) => `h.${Buffer.from(JSON.stringify(payload)).toString("base64url")}.s`;

test("only a server-set staff role in app_metadata passes the gate", () => {
  assert.equal(staffRoleOf({ app_metadata: { role: "catering_owner" } }), "catering_owner");
  assert.equal(staffRoleOf({ app_metadata: { role: "catering_manager" } }), "catering_manager");
  assert.equal(staffRoleOf({ app_metadata: { role: "admin" } }), null);
  assert.equal(staffRoleOf({ app_metadata: {} }), null);
  assert.equal(staffRoleOf(null), null);
  // A self-edited profile must never grant access.
  assert.equal(staffRoleOf({ user_metadata: { role: "catering_owner" } }), null);
});

test("token role check reads app_metadata and tolerates garbage", () => {
  assert.equal(tokenHasStaffRole(jwt({ app_metadata: { role: "catering_owner", name: "דנה" } })), true);
  assert.equal(tokenHasStaffRole(jwt({ user_metadata: { role: "catering_owner" } })), false);
  assert.equal(tokenHasStaffRole("not-a-token"), false);
  assert.equal(tokenHasStaffRole(undefined), false);
});

test("cloud config needs the configured flag, an https url and a key", () => {
  const good = { configured: true, url: "https://x.supabase.co", publishableKey: "sb_publishable_a" };
  assert.deepEqual(parseCloudConfig(good), good);
  assert.equal(parseCloudConfig({ configured: false, url: null, publishableKey: null }).configured, false);
  assert.equal(parseCloudConfig({ ...good, url: "http://x" }).configured, false);
  assert.equal(parseCloudConfig({ ...good, publishableKey: null }).configured, false);
  assert.equal(parseCloudConfig(null).configured, false);
});

test("cloud config accepts only publishable keys", () => {
  const withKey = (publishableKey) => parseCloudConfig({ configured: true, url: "https://x.supabase.co", publishableKey });
  assert.equal(withKey("sb_publishable_abc").configured, true);
  assert.equal(withKey("sb_secret_abc").configured, false);
  assert.equal(withKey("eyJhbGciOiJIUzI1NiJ9.service_role.sig").configured, false);
  assert.equal(withKey("SB_PUBLISHABLE_abc").configured, false);
});

test("pagination maps pages to inclusive ranges and reports position", () => {
  assert.deepEqual(pageRange(0, 25), { from: 0, to: 24 });
  assert.deepEqual(pageRange(2, 25), { from: 50, to: 74 });
  assert.deepEqual(pageInfo(60, 2, 25), { total: 60, totalPages: 3, first: 51, last: 60, hasPrev: true, hasNext: false });
  assert.deepEqual(pageInfo(0, 0, 25), { total: 0, totalPages: 1, first: 0, last: 0, hasPrev: false, hasNext: false });
  assert.equal(pageInfo(25, 0, 25).hasNext, false);
  assert.equal(pageInfo(26, 0, 25).hasNext, true);
});

test("request guard rejects responses after a newer request or an invalidation", () => {
  const guard = createRequestGuard();
  const first = guard.next();
  const second = guard.next();
  assert.equal(guard.isCurrent(first), false);
  assert.equal(guard.isCurrent(second), true);
  guard.invalidate();
  assert.equal(guard.isCurrent(second), false);
});

test("money and milli parsing is exact and strict", () => {
  assert.equal(parseMoneyToMinor("19.99"), 1999);
  assert.equal(parseMoneyToMinor("0.07"), 7);
  assert.equal(parseMoneyToMinor("85"), 8500);
  assert.equal(parseMoneyToMinor(" 1.5 "), 150);
  assert.equal(parseMoneyToMinor("1.999"), null);
  assert.equal(parseMoneyToMinor("-1"), null);
  assert.equal(parseMoneyToMinor("1e3"), null);
  assert.equal(parseMoneyToMinor("99999999999999999"), null);
  assert.equal(parseMilli("0.5"), 500);
  assert.equal(parseMilli("0.0005"), null);
  assert.equal(minorToInput(1999), "19.99");
  assert.equal(minorToInput(7), "0.07");
  assert.equal(minorToInput(8500), "85");
  assert.equal(minorToInput(150), "1.5");
  assert.equal(milliToInput(500), "0.5");
  assert.equal(milliToInput(4000), "4");
});

test("column validation follows the migration's rules", () => {
  const required = { name: "a", type: "text" };
  const optional = { name: "a", type: "text", nullable: true };
  assert.ok(validateColumn(required, "   ").error);
  assert.deepEqual(validateColumn(optional, "  "), { value: null });
  assert.deepEqual(validateColumn(required, " שלום "), { value: "שלום" });
  assert.ok(validateColumn({ type: "email", nullable: true }, "nope").error);
  assert.deepEqual(validateColumn({ type: "email" }, "a@b.co"), { value: "a@b.co" });
  assert.ok(validateColumn({ type: "phone" }, "abc").error);
  assert.deepEqual(validateColumn({ type: "phone" }, "050-1234567"), { value: "050-1234567" });
  assert.ok(validateColumn({ type: "date" }, "2026-02-30").error);
  assert.deepEqual(validateColumn({ type: "date" }, "2026-02-28"), { value: "2026-02-28" });
  assert.ok(validateColumn({ type: "int" }, "1.5").error);
  assert.ok(validateColumn({ type: "int" }, "-1").error);
  assert.deepEqual(validateColumn({ type: "int" }, "12"), { value: 12 });
  assert.ok(validateColumn({ type: "milli" }, "0").error);
  assert.deepEqual(validateColumn({ type: "money" }, "0"), { value: 0 });
  assert.deepEqual(validateColumn({ type: "bool" }, false), { value: false });
  const enumColumn = { type: "enum", options: { a: "א" } };
  assert.deepEqual(validateColumn(enumColumn, "a"), { value: "a" });
  assert.ok(validateColumn(enumColumn, "toString").error, "prototype keys are not valid options");
});

test("a customer needs an email or a phone", () => {
  const columns = getTable("customers").columns.filter((c) => ["full_name", "email", "phone"].includes(c.name));
  const missing = validateColumns(columns, { full_name: "דנה", email: "", phone: "" });
  validateTableRules("customers", missing.values, missing.errors);
  assert.ok(missing.errors.phone);
  const fine = validateColumns(columns, { full_name: "דנה", email: "", phone: "0501234567" });
  validateTableRules("customers", fine.values, fine.errors);
  assert.deepEqual(fine.errors, {});
});

test("patches contain only changed columns", () => {
  const original = { name: "א", cost: null, meta: { a: 1 }, updated_at: "x" };
  assert.deepEqual(buildPatch(original, { name: "א", cost: null, meta: { a: 1 } }), {});
  assert.deepEqual(buildPatch(original, { name: "ב", cost: 0, meta: { a: 2 } }), { name: "ב", cost: 0, meta: { a: 2 } });
});

test("search terms cannot inject wildcards", () => {
  assert.equal(escapeLike("50%_a\\"), "50\\%\\_a\\\\");
});

const seed = {
  id: "d8",
  metadata: { id: "d8", categoryId: "mains", name: "תבשיל", description: "ירקות", price: 170, unit: "tray", kashrut: "pareve", vegetarian: true, vegan: true, allergens: null, futureKey: "keep" },
  price_minor: 17000,
  step_milli: 1000,
  image_path: null,
};

test("an untouched dish form produces no change at all", () => {
  const result = validateDishForm(dishToFields(seed), seed);
  assert.deepEqual(result.errors, {});
  const { id, ...values } = result.row;
  assert.equal(id, "d8");
  assert.deepEqual(buildPatch(seed, values), {});
});

test("unknown allergens stay unknown and are never turned into an empty list", () => {
  const fields = dishToFields(seed);
  assert.equal(fields.allergenState, "unknown");
  assert.equal(validateDishForm(fields, seed).row.metadata.allergens, null);
  const known = validateDishForm({ ...fields, allergenState: "known", allergens: "" }, seed);
  assert.deepEqual(known.row.metadata.allergens, []);
  const listed = validateDishForm({ ...fields, allergenState: "known", allergens: "חלב, אגוזים," }, seed);
  assert.deepEqual(listed.row.metadata.allergens, ["חלב", "אגוזים"]);
});

test("dish edits keep unknown keys and sync price and step into the document", () => {
  const result = validateDishForm({ ...dishToFields(seed), price_minor: "180.50", step_milli: "0.5", perGuest: "1.5" }, seed);
  assert.equal(result.row.price_minor, 18050);
  assert.equal(result.row.metadata.price, 180.5);
  assert.equal(result.row.step_milli, 500);
  assert.equal(result.row.metadata.step, 0.5);
  assert.equal(result.row.metadata.perGuest, 1.5);
  assert.equal(result.row.metadata.futureKey, "keep");
  const cleared = validateDishForm({ ...dishToFields({ ...seed, metadata: { ...seed.metadata, perGuest: 2 } }), perGuest: "" }, seed);
  assert.equal("perGuest" in cleared.row.metadata, false);
});

test("new dish ids must be safe storage path segments", () => {
  const fields = { ...dishToFields(null), id: "../x", name: "ש", categoryId: "mains", unit: "kg", kashrut: "meat", price_minor: "1", allergenState: "unknown" };
  assert.ok(validateDishForm(fields, null).errors.id);
  const created = validateDishForm({ ...fields, id: "new-dish_1" }, null);
  assert.deepEqual(created.errors, {});
  assert.equal(created.row.metadata.id, "new-dish_1");
  assert.equal(created.row.metadata.step, 1);
});

test("a vegan dish must also be vegetarian", () => {
  const result = validateDishForm({ ...dishToFields(seed), vegetarian: false, vegan: true }, seed);
  assert.ok(result.errors.vegetarian);
});

test("image rules: type, extension and size", () => {
  assert.deepEqual(validateImageFile({ name: "A.JPEG", type: "image/jpeg", size: 10 }), { extension: "jpg", contentType: "image/jpeg" });
  assert.equal(validateImageFile({ name: "a.webp", type: "image/webp", size: MAX_IMAGE_BYTES }).extension, "webp");
  assert.ok(validateImageFile({ name: "a.png", type: "image/png", size: MAX_IMAGE_BYTES + 1 }).error);
  assert.ok(validateImageFile({ name: "a.png", type: "image/png", size: 0 }).error);
  assert.ok(validateImageFile({ name: "a.svg", type: "image/svg+xml", size: 10 }).error);
  assert.ok(validateImageFile({ name: "a.gif", type: "image/gif", size: 10 }).error);
  assert.ok(validateImageFile({ name: "a.png", type: "image/jpeg", size: 10 }).error);
});

test("image content must match its signature", () => {
  assert.equal(sniffImageType(new Uint8Array([0xff, 0xd8, 0xff, 0xe0])), "image/jpeg");
  assert.equal(sniffImageType(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])), "image/png");
  assert.equal(sniffImageType(new TextEncoder().encode("RIFF1234WEBPVP8")), "image/webp");
  assert.equal(sniffImageType(new TextEncoder().encode("RIFF1234WAVEfmt")), null);
  assert.equal(sniffImageType(new TextEncoder().encode("<svg xmlns=")), null);
});

test("image paths follow the agreed layout and reject traversal", () => {
  assert.equal(buildDishImagePath("d1", "png", "uuid"), "dishes/d1/uuid.png");
  assert.throws(() => buildDishImagePath("../d1", "png", "uuid"));
  assert.throws(() => buildDishImagePath("a/b", "png", "uuid"));
});

test("errors keep a Hebrew message apart from the raw detail", () => {
  const unique = describeError({ code: "23505", message: "duplicate key value" });
  assert.match(unique.message, /ייחודי/);
  assert.doesNotMatch(unique.message, /[A-Za-z]/);
  assert.equal(unique.detail, "23505: duplicate key value");
  assert.match(describeError({ code: "invalid_credentials", message: "x" }).message, /סיסמה/);
  assert.match(describeError({ message: "TypeError: Failed to fetch" }).message, /תקשורת/);
  assert.match(describeError({ statusCode: "403", message: "denied" }).message, /הרשאה/);
  assert.equal(describeError({ message: "weird" }).message, "הפעולה נכשלה.");
});

test("a session is treated as invalid only for auth failures, not network ones", () => {
  assert.equal(isSessionInvalidError({ status: 401 }), true);
  assert.equal(isSessionInvalidError({ name: "AuthSessionMissingError" }), true);
  assert.equal(isSessionInvalidError({ name: "AuthRetryableFetchError", status: 0 }), false);
  assert.equal(isSessionInvalidError({ status: 500 }), false);
});

test("cells format by column type and mask token digests", () => {
  assert.equal(formatCell({ type: "text" }, null), "—");
  assert.match(formatCell({ type: "money" }, 8550), /85\.50/);
  assert.equal(formatCell({ type: "bool" }, false), "לא");
  assert.equal(formatCell({ type: "date" }, "2026-11-05"), "05/11/2026");
  assert.equal(formatCell({ type: "enum", options: { a: "א" } }, "a"), "א");
  assert.equal(formatCell({ type: "enum", options: {} }, "new_value"), "new_value");
  assert.equal(formatCell({ type: "text", masked: true }, "abcdefghijklmnop"), "abcdefghij…");
});

test("document cells parse text columns and tolerate invalid content", () => {
  const text = { type: "jsontext" };
  assert.equal(jsonCellText(text, '{"a":1}'), '{\n  "a": 1\n}');
  assert.equal(jsonCellText(text, "not json"), "not json");
  assert.equal(jsonCellText({ type: "jsonb" }, { a: 1 }), '{\n  "a": 1\n}');
  assert.equal(isLtrCell(text), true);
});

test("diagram edges connect facing sides and self references loop", () => {
  const a = { x: 0, y: 0, width: 100, height: 50 };
  const b = { x: 300, y: 0, width: 100, height: 50 };
  const c = { x: 0, y: 300, width: 100, height: 50 };
  assert.ok(edgePath(a, b).startsWith("M 100 25"));
  assert.ok(edgePath(a, b).endsWith("300 25"));
  assert.ok(edgePath(a, c).startsWith("M 50 50"));
  assert.ok(edgePath(a, a).includes("C"));
});

/* ---------- dish image save sequence ---------- */

function fakeClient({ uploadError = null, linkError = null, linkRejects = null } = {}) {
  const calls = [];
  const query = {
    eq(column, value) { calls.push(["eq", column, value]); return query; },
    is(column, value) { calls.push(["is", column, value]); return query; },
    select() { return query; },
    single: async () => {
      calls.push(["single"]);
      if (linkRejects) throw linkRejects;
      return linkError ? { data: null, error: linkError } : { data: { id: "d1" }, error: null };
    },
  };
  return {
    calls,
    storage: {
      from: (bucket) => ({
        upload: async (path, _file, options) => {
          calls.push(["upload", bucket, path, options]);
          return { data: uploadError ? null : { path }, error: uploadError };
        },
        remove: async (paths) => {
          calls.push(["remove", paths]);
          return { data: [], error: null };
        },
      }),
    },
    from: (table) => ({
      update(values) {
        calls.push(["update", table, values]);
        return query;
      },
    }),
  };
}

const imageArgs = { dishId: "d1", file: {}, info: { extension: "png", contentType: "image/png" }, uuid: "u1" };
const names = (client) => client.calls.map((call) => call[0]);

test("image save uploads, then links, and deletes nothing", async () => {
  const client = fakeClient();
  const result = await replaceDishImage({ client, oldPath: "dishes/d1/old.png", ...imageArgs });
  assert.deepEqual(result, { ok: true, path: "dishes/d1/u1.png" });
  assert.deepEqual(names(client).filter((n) => n !== "eq"), ["upload", "update", "single"]);
  assert.equal(client.calls[0][1], "dish-images");
  assert.equal(client.calls[0][3].upsert, false);
  assert.ok(client.calls.some((c) => c[0] === "eq" && c[1] === "image_path" && c[2] === "dishes/d1/old.png"));
});

test("a failed upload never touches the row or any object", async () => {
  const client = fakeClient({ uploadError: { message: "denied" } });
  const result = await replaceDishImage({ client, oldPath: "dishes/d1/old.png", ...imageArgs });
  assert.equal(result.ok, false);
  assert.equal(result.stage, "upload");
  assert.deepEqual(names(client), ["upload"]);
});

test("an ambiguous link error keeps the uploaded object, which may already be live", async () => {
  // The row may have committed before the response was lost, so the new path could be current.
  const client = fakeClient({ linkError: { message: "TypeError: Failed to fetch" } });
  const result = await replaceDishImage({ client, oldPath: "dishes/d1/old.png", ...imageArgs });
  assert.equal(result.stage, "link");
  assert.equal(names(client).includes("remove"), false);
});

test("a rejected link request is ambiguous too and deletes nothing", async () => {
  const lost = new Error("connection reset");
  const client = fakeClient({ linkRejects: lost });
  const result = await replaceDishImage({ client, oldPath: "dishes/d1/old.png", ...imageArgs });
  assert.deepEqual(result, { ok: false, stage: "link", error: lost });
  assert.equal(names(client).includes("remove"), false);
});

test("retrying after a committed link is refused by the old-path match, deleting nothing", async () => {
  const client = fakeClient({ linkError: { code: "PGRST116", message: "0 rows" } });
  const result = await replaceDishImage({ client, oldPath: "dishes/d1/old.png", ...imageArgs });
  assert.equal(result.stage, "link");
  assert.equal(result.error.code, "PGRST116");
  assert.equal(names(client).includes("remove"), false);
});

test("a first image links only while the column is still empty", async () => {
  const client = fakeClient();
  await replaceDishImage({ client, oldPath: null, ...imageArgs });
  assert.ok(client.calls.some((c) => c[0] === "is" && c[1] === "image_path" && c[2] === null));
  assert.equal(names(client).includes("remove"), false);
});
