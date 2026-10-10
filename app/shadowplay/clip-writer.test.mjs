import assert from "node:assert/strict";
import { ClipWriter, MAX_ATTEMPTS, parseSeq } from "./clip-writer.js";
import { SessionClock, WIDTH } from "./session-clock.js";

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

// clean directory: every name is free
t("clean directory yields 0000.mp4 first", () => {
  const w = new ClipWriter({ exists: () => false });
  assert.equal(w.nextClipName(), "0000.mp4");
});

t("names are fixed-width and sort chronologically", () => {
  const w = new ClipWriter({ exists: () => false });
  const names = Array.from({ length: 50 }, () => w.nextClipName());
  for (const n of names) assert.equal(n.length, WIDTH + ".mp4".length);
  assert.deepEqual([...names].sort(), names);
});

// the collision arm -- the whole point of MAX_ATTEMPTS
t("an occupied name is skipped, not returned", () => {
  const taken = new Set(["0000.mp4", "0001.mp4"]);
  const w = new ClipWriter({ exists: (n) => taken.has(n) });
  const name = w.nextClipName();
  assert.equal(name, "0002.mp4");
  assert.ok(!taken.has(name));
  assert.equal(w.attemptsFor("0000.mp4"), 1);
});

t("exactly 10 occupied names still resolves on the 10th", () => {
  const taken = new Set(Array.from({ length: MAX_ATTEMPTS - 1 },
    (_, i) => String(i).padStart(WIDTH, "0") + ".mp4"));
  const w = new ClipWriter({ exists: (n) => taken.has(n) });
  assert.equal(w.nextClipName(), "0009.mp4");
});

t("an exhausted directory throws instead of returning a taken name", () => {
  let counter = 0;
  // everything this writer would ever produce already exists
  const w = new ClipWriter({
    exists: () => { counter++; return true; },
  });
  assert.throws(() => w.nextClipName(), /no free sequence value after 10 attempts/);
  assert.equal(counter, MAX_ATTEMPTS);
});

t("parseSeq round-trips the writer's own names", () => {
  const w = new ClipWriter({ exists: () => false });
  const name = w.nextClipName();
  assert.equal(parseSeq(name), 0);
  assert.ok(Number.isNaN(parseSeq("clip_final.mp4")));
});

// negative arms: the writer must refuse to exist without a predicate
t("a writer without an exists predicate is refused", () => {
  assert.throws(() => new ClipWriter({}), TypeError);
});

t("exhaustion of the underlying clock surfaces as RangeError", () => {
  const w = new ClipWriter({ exists: () => false, clock: new SessionClock({ ceiling: 2 }) });
  w.nextClipName(); w.nextClipName();
  assert.throws(() => w.nextClipName(), RangeError);
});

console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);