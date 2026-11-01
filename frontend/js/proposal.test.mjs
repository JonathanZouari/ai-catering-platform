// Run with: node frontend/js/proposal.test.mjs
import assert from "node:assert/strict";
import { readEvent, totalFor } from "./proposal.js";

const good = JSON.stringify({ name: "יום הולדת", guests: 40, kids: 3, vegans: 2 });
assert.deepEqual(readEvent(good), { name: "יום הולדת", guests: 40, vegans: 2 });

// Missing, malformed or impossible data falls back to the sample event.
for (const raw of [null, "", "not json", "[]", '{"name":"","guests":10,"vegans":0}', '{"name":"x","guests":0,"vegans":0}', '{"name":"x","guests":5,"vegans":9}', '{"name":"x","guests":1.5,"vegans":0}', '{"name":1,"guests":5,"vegans":0}']) {
  assert.equal(readEvent(raw).guests, 80);
}
assert.equal(readEvent(JSON.stringify({ name: "x".repeat(99), guests: 1, vegans: 0 })).name.length, 40);

assert.equal(totalFor({ vegans: 5 }, false), 6540);
assert.equal(totalFor({ vegans: 5 }, true), 6915);

console.log("proposal.js: ok");
