// Run with: node frontend/js/guests.test.mjs
import assert from "node:assert/strict";
import { MAX_GUESTS, missingField, setGuests, setKids, setVegans, setVegetarians } from "./guests.js";

const base = { guests: 80, kids: 15, vegetarians: 8, vegans: 5 };

// Shrinking the total pulls every subgroup down with it.
const one = setGuests(base, 1);
assert.deepEqual(one, { guests: 1, kids: 1, vegetarians: 1, vegans: 0 });
assert.equal(setGuests(base, 0).guests, 1);
assert.equal(setGuests(base, 9999).guests, MAX_GUESTS);

// Vegetarians and vegans together never exceed the total.
assert.equal(setVegetarians(base, 500).vegetarians, 75);
assert.equal(setVegans(base, 500).vegans, 72);
assert.equal(setKids(base, 500).kids, 80);
assert.equal(setKids(base, -1).kids, 0);

const today = "2026-11-01";
assert.match(missingField({ date: "", delivery: false, address: "" }, today), /תאריך/);
assert.match(missingField({ date: "2020-01-01", delivery: false, address: "" }, today), /עתידי/);
assert.match(missingField({ date: "2026-12-11", delivery: true, address: "  " }, today), /כתובת/);
assert.equal(missingField({ date: "2026-12-11", delivery: true, address: "הרצל 1" }, today), "");
assert.equal(missingField({ date: today, delivery: false, address: "" }, today), "");

console.log("guests.js: ok");
