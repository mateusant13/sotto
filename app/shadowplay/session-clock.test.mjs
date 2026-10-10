// Run: node app/shadowplay/session-clock.test.mjs
import assert from "node:assert/strict";
import { SessionClock, format, WIDTH, CEILING } from "./index.js";

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

// The invariant the design depends on: sort order == chronological order.
t("sort equals insertion order within a session", () => {
  const c = new SessionClock();
  const names = Array.from({ length: 500 }, () => c.nextName());
  assert.deepEqual([...names].sort(), names);
});

t("format pads to width 4", () => assert.equal(format(7), "0007"));
t("format rejects 10000", () => assert.throws(() => format(CEILING), RangeError));
t("format rejects non-integer", () => assert.throws(() => format(1.5), TypeError));
t("format rejects negative", () => assert.throws(() => format(-1), RangeError));
t("clock throws past ceiling", () => {
  const c = new SessionClock({ ceiling: 3 });
  c.nextName(); c.nextName(); c.nextName();
  assert.throws(() => c.nextName(), RangeError);
});

// Real exhaustion: 10000 valid names, the 10001st throws.
t("clock yields exactly 10000 names then throws", () => {
  const c = new SessionClock();
  for (let i = 0; i < CEILING; i++) c.nextName();
  assert.throws(() => c.nextName(), RangeError);
});

t("the naive sort inversion the clock exists to prevent", () => {
  const naive = ["clip_9998", "clip_9999", "clip_10000", "clip_10001"];
  assert.equal([...naive].sort().join(" "),
    "clip_10000 clip_10001 clip_9998 clip_9999");
});

t("private counter cannot be seeded from outside", () => {
  const c = new SessionClock();
  c.next = 9998;               // must NOT move the private field
  assert.equal(c.nextName(), "0000");
});

console.log(`RESULT ${passed} passed, ${failed} failed, WIDTH=${WIDTH}`);
process.exit(failed === 0 ? 0 : 1);

