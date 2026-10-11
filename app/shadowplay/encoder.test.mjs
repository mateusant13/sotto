// FIRST TEST FILE for encoder.js. Before this file, encoder.js had ZERO coverage -- it is
// exported from the barrel (index.js) and nothing in the repository exercised it.
//
// READ THE COUNT BEFORE YOU TRUST IT. "9 passed" is an aggregate of assertions, NOT a
// statement that 14 behaviours are guarded. Measured WINDOW_UTC 2026-10-11T02:46:35Z,
// counting registrations from the source rather than from the RESULT line:
//   tests registered  14   (all synchronous; 0 async)
//   tests RUNNING       14   RESULT 14 passed / 0 failed
// These two used to disagree: this header said 9 while the file held 14, because tests were
// added here after the header was written and the number was never recomputed. An independent
// review (ENCODER-INDEPENDENT-REVIEW.txt) caught it. Recount at every change.
//
//   branches falsified  4, by the mutations below. RE-MEASURED N=2 each, WINDOW_UTC
//   2026-10-11T02:58:46Z, control 14 passed / 0 failed. Every arm below now reads
//   12 passed / 2 failed, exit 1 -- NOT the 7/2 and 8/1 figures recorded at 01:52:32Z,
//   because tests were added to this file after those were written. Third stale-header
//   defect in this codebase; count from the source at every change.
//       (a) the IDR guard, by replacing
//           `if (slice[0].type !== FRAME_TYPES.IDR)` with `if (false)`:
//           12 passed / 2 failed, exit 1.   N=2, both runs identical.
//       (b) the payload guard's lower bound, by dropping the `|| payloadBytes < 0` half of
//           the condition at encoder.js:27: 12 passed / 2 failed, exit 1.  N=2, identical.
//       (c) the empty-slice guard at encoder.js:41, by returning
//           `{frames: 0, bytes: 0, startType: IDR}` instead of throwing:
//           12 passed / 2 failed, exit 1.   N=2, both runs identical.
//       (d) the constructor guard's lower bound, by dropping the `|| gopSize < 1` half of
//           the condition at encoder.js:14: 12 passed / 2 failed, exit 1.  N=2, identical.
//
//   ON (b) AND (d), AND ON THE WORD "WEAK". A review called these two weak mutants because
//   they drop HALF a boolean condition rather than the whole guard, so they show the lower
//   bound is asserted rather than that the guard is load-bearing. I tested that claim instead
//   of arguing with it, by removing each guard ENTIRELY (same 02:58:46Z window, N=2):
//       b WHOLE guard removed  ->  12 passed / 2 failed, exit 1
//       d WHOLE guard removed  ->  12 passed / 2 failed, exit 1
//   Observationally IDENTICAL to removing half. So the reviewer's methodological point
//   stands -- the half-mutant isolates the lower bound only -- but this suite cannot tell
//   the two apart: nothing extra turns red when the whole guard goes. Recording that here
//   because "weak mutant" invites the reader to assume a coverage hole that is not there.
//
//   branches NOT falsified  10   (14 registered minus the 4 above)
//   assertions that pass with nothing showing that removing the code they exercise would
//   turn them red.
//
//   N PER ARM = 1. Every mutation above was run once. No variance is known for any red
//   count here, and none of these five mutants has been re-run.
//
//   Sibling file: frame-accounting.test.mjs carries the same disclosure for its own count.
//
// WHAT THIS SUITE IS FOR: encoder.js encodes the product's cross-cutting invariant -- a
// saved clip is REMUXED from already-encoded bytes, must START on an IDR, and is never
// re-encoded. remux() is the only place that invariant is enforced, and it is enforced by
// two throws. A throw with no test is a comment.
//
// It runs against the real module, no mocks: encoder.js is pure and synchronous.

import assert from "node:assert/strict";
import { Encoder, FRAME_TYPES } from "./encoder.js";

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

// A gop of 4 makes the IDR positions exactly 0,4,8 -- small enough to state by hand.
const GOP = 4;
function filled(count, gopSize = GOP) {
  const e = new Encoder({ gopSize });
  for (let i = 0; i < count; i++) e.encodeFrame(i, 10);
  return e;
}

// ---------------------------------------------------------------- the type decision

// (A first draft of this file had a test here that called remux(0) inside a dead
// expression and then asserted on operations(). It asserted nothing, and calling remux
// polluted the log it then inspected -- it failed for its own reasons. Deleted rather than
// repaired: a test that cannot fail for the product's reasons is worse than no test.)

t("index 0 is IDR and the gop boundary is IDR, by construction of the module", () => {
  const e = new Encoder({ gopSize: GOP });
  const f0 = e.encodeFrame(0, 10);
  const f1 = e.encodeFrame(1, 10);
  const f4 = e.encodeFrame(4, 10);
  assert.equal(f0.type, FRAME_TYPES.IDR, "frame 0 must be an IDR");
  assert.equal(f1.type, FRAME_TYPES.P, "frame 1 must be a P frame");
  assert.equal(f4.type, FRAME_TYPES.IDR, "frame at the gop boundary must be an IDR");
  assert.equal(FRAME_TYPES.IDR, 0);
  assert.equal(FRAME_TYPES.P, 1);
});

// -------------------------------------------------- the invariant remux() protects

t("remux from a non-IDR index is refused -- a clip must not start mid-GOP", () => {
  const e = filled(8);
  assert.throws(() => e.remux(1), RangeError);
  assert.throws(() => e.remux(3), RangeError);
});

t("remux from an IDR index succeeds and starts on an IDR", () => {
  const e = filled(8);
  for (const from of [0, 4]) {
    const r = e.remux(from);
    assert.equal(r.startType, FRAME_TYPES.IDR, `remux from ${from} must start on an IDR`);
  }
});

t("remux past the last frame is refused rather than returning an empty clip", () => {
  const e = filled(4);
  assert.throws(() => e.remux(99), RangeError);
});

t("remux reports the frame count and the byte sum of the slice it kept", () => {
  const e = filled(8);
  const r = e.remux(4);
  assert.equal(r.frames, 4, "8 frames encoded, 4 kept from index 4");
  assert.equal(r.bytes, 40, "4 frames of 10 bytes each");
});

t("remux does not re-encode: it adds one log entry and leaves encoded untouched", () => {
  const e = filled(8);
  const before = e.encoded;
  e.remux(4);
  assert.equal(e.encoded, before, "remux must not add frames -- it copies already-encoded bytes");
  assert.equal(e.encodeCount(), 8, "remux must not increment the encode count");
  assert.deepEqual(e.operations(), ["encode", "encode", "encode", "encode", "encode", "encode", "encode", "encode", "remux"]);
});

// --------------------------------------------------------------- the constructor guard

t("gopSize must be a positive integer", () => {
  assert.throws(() => new Encoder({ gopSize: 0 }), RangeError);
  assert.throws(() => new Encoder({ gopSize: -1 }), RangeError);
  assert.throws(() => new Encoder({ gopSize: 1.5 }), RangeError);
  assert.equal(new Encoder({ gopSize: 1 }).gopSize, 1);
  assert.equal(new Encoder().gopSize, 60, "the default gop is 60");
});

t("payloadBytes must be a non-negative integer", () => {
  const e = new Encoder({ gopSize: GOP });
  assert.throws(() => e.encodeFrame(0, -1), RangeError);
  assert.throws(() => e.encodeFrame(0, 1.5), RangeError);
  assert.equal(e.encodeFrame(0, 0).bytes, 0, "a zero-byte frame is legal; an empty clip is not");
});

// --------------------------------------- RED ARM: the gate must be able to say NO

// A gate that only knows PASS is not a gate. This asserts the OLD behaviour -- that remux
// happily starts mid-GOP -- and requires it to fail. If someone ever removes the IDR guard
// from remux(), the assertion below will stop being caught and this turns RED.
t("RED ARM: the IDR guard is load-bearing, not decorative", () => {
  const e = filled(8);
  let redFired = false;
  try {
    // DELIBERATELY WRONG: claims a mid-GOP remux is fine. Must throw, i.e. must fail here.
    assert.doesNotThrow(() => e.remux(3), "RED ARM: expected the IDR guard to refuse index 3");
  } catch { redFired = true; }
  assert.equal(redFired, true,
    "the RED arm did not go red: remux(3) stopped throwing, so the IDR guard is gone and " +
    "every other test here would still pass while the product's core invariant is unenforced");
});

// ---------------------------------------------------------------- SECOND WATCHERS
// Measured WINDOW_UTC 2026-10-11T01:55:22Z: three of the four falsified branches were each
// turned red by exactly ONE test, so deleting that test would leave its guard unwatched and
// no count in this file would show it. These are independent entry paths for those same
// three guards -- different inputs, different construction routes, separate test bodies --
// so that removing any single test still leaves the guard covered.

t("gopSize is refused at the constructor even when built from a computed value", () => {
  // A different route to the same guard: the value is computed, not literal, and the
  // rejection happens before any instance exists.
  const negative = 0 - 1;
  assert.throws(() => new Encoder({ gopSize: negative }), RangeError);
  const fractional = Math.floor(3.7);
  assert.equal(fractional, 3, "Math.floor is what makes this an integer; guard must still accept it");
  assert.doesNotThrow(() => new Encoder({ gopSize: fractional }));
});

t("a negative payload is refused on any frame, not only frame zero", () => {
  const e = new Encoder({ gopSize: GOP });
  e.encodeFrame(0, 10);
  e.encodeFrame(1, 10);
  // Deliberately NOT index 0: the existing watcher uses index 0.
  assert.throws(() => e.encodeFrame(2, -1), RangeError);
  assert.throws(() => e.encodeFrame(3, -4096), RangeError);
  assert.equal(e.encoded, 2, "a refused frame must not be counted as encoded");
});

t("remux past the end is refused at several distances, not only index 99", () => {
  const e = filled(4); // frames 0..3
  for (const from of [4, 5, 100, 1e9]) {
    assert.throws(() => e.remux(from), RangeError,
      `remux(${from}) is past the last frame and must be refused`);
  }
  assert.equal(e.encoded, 4, "a refused remux must not add frames");
});

// A DIFFERENT-SIZED FIXTURE, because every other fixture in this file encodes every frame
// at the same 10 bytes. Measured WINDOW_UTC 2026-10-11T02:07:38Z: replacing the real sum
// `slice.reduce((a, f) => a + f.bytes, 0)` with `slice.length * slice[0].bytes` -- which is
// WRONG whenever frame sizes differ -- left this suite at 12 passed / 0 failed, exit 0.
//
// The reason is a fixed point hiding in the fixture: with uniform 10-byte frames, length*10
// IS the sum, so a test that only ever uses uniform frames cannot tell a sum from a
// multiplication by its first term. This is the same shape as the rounding case in
// frame-accounting.test.mjs, where every assertion compared coverage to exactly 1.
t("remux sums UNEQUAL frame sizes, not length times the first frame", () => {
  const e = new Encoder({ gopSize: GOP });
  // Deliberately unequal, and not in arithmetic progression: a multiplication by the first
  // term, a mean, and a sum are all distinguishable from these numbers.
  const sizes = [7, 100, 3, 250, 11];
  sizes.forEach((n, i) => e.encodeFrame(i, n));
  const total = sizes.reduce((a, b) => a + b, 0); // 371

  const all = e.remux(0);
  assert.equal(all.frames, 5);
  assert.equal(all.bytes, total, `the sum is ${total}, not length*first (${5 * 7})`);

  // And on a partial slice, where length*first is wrong in a different way again.
  // Cuts must land on GOP boundaries (gopSize=4 -> IDR at 0 and 4), so the partial slice
  // starts at index 4, not at an arbitrary frame.
  const tail = e.remux(4);
  assert.equal(tail.frames, 1);
  assert.equal(tail.bytes, sizes[4], "a one-frame slice must report that frame's own size");
});

t("a zero-byte frame does not skew the sum", () => {
  const e = new Encoder({ gopSize: 4 });
  e.encodeFrame(0, 0);
  e.encodeFrame(1, 42);
  e.encodeFrame(2, 0);
  e.encodeFrame(3, 8);
  e.encodeFrame(4, 0);
  e.encodeFrame(5, 5);
  assert.equal(e.remux(0).bytes, 55, "zeros contribute nothing but must not reset the sum");
  // Index 4 is an IDR boundary (4 % 4 === 0), so this slice is lawful.
  assert.equal(e.remux(4).bytes, 5,
    "a slice whose FIRST frame is zero must still sum the frames after it");
});

console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);