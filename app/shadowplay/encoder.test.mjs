// FIRST TEST FILE for encoder.js. Before this file, encoder.js had ZERO coverage -- it is
// exported from the barrel (index.js) and nothing in the repository exercised it.
//
// READ THE COUNT BEFORE YOU TRUST IT. "9 passed" is an aggregate of assertions, NOT a
// statement that 9 behaviours are guarded. Measured WINDOW_UTC 2026-10-11T01:30:26Z, counting
// registrations from the source rather than from the RESULT line:
//   tests registered   9   (all synchronous; 0 async)
//   branches falsified  3   -- measured WINDOW_UTC 2026-10-11T01:48:55Z
//       (a) the IDR guard, by replacing
//           `if (slice[0].type !== FRAME_TYPES.IDR)` with `if (false)`:
//           7 passed / 2 failed, exit 1.
//       (b) the payload guard's lower bound, by dropping the `|| payloadBytes < 0` half of
//           the condition at encoder.js:27: 8 passed / 1 failed, exit 1.
//       (c) the empty-slice guard at encoder.js:41, by returning
//           `{frames: 0, bytes: 0, startType: IDR}` instead of throwing:
//           8 passed / 1 failed, exit 1.
//       (b) and (c) each turn exactly ONE test red, so both are covered but only singly.
//   branches NOT falsified 6. Their assertions pass, and nothing here shows that removing
//                                 the code they exercise would turn any of them red.
// Sibling file: frame-accounting.test.mjs carries the same disclosure for its own count.
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

console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);