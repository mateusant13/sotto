import assert from "node:assert/strict";
import { gopFromKeyframes, parseKeyframes, DEFAULT_FPS } from "./stream-probe.js";

// These are the pts values ffprobe ACTUALLY returned on this host at
// WINDOW_UTC 2026-10-10T13:01:47Z. Not invented -- measured.
const MEASURED = ["0.000000", "4.166667"];

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

t("the measured keyframes parse to two sorted times", () => {
  assert.deepEqual(parseKeyframes(MEASURED), [0, 4.166667]);
});

t("the measured GOP is 250, not the 60 the ring assumed", () => {
  const r = gopFromKeyframes(MEASURED, 60);
  assert.equal(r.gop, 250, "the hardware chose 250; the code assumed 60");
  assert.equal(r.variable, false);
});

t("garbage and blank lines are dropped, not parsed as zero", () => {
  assert.deepEqual(parseKeyframes(["", "0.0", "  ", "NaN", "2.0", "4.0"]), [0, 2, 4]);
});

t("a single keyframe cannot define a GOP", () => {
  assert.throws(() => gopFromKeyframes(["0.0"], 60), RangeError);
});

t("zero keyframes is refused rather than defaulting to something", () => {
  assert.throws(() => gopFromKeyframes([], 60), RangeError);
});

t("a variable GOP reports the smallest safe cut and says so", () => {
  const r = gopFromKeyframes(["0.0", "2.0", "5.0"], 60);
  assert.equal(r.variable, true);
  assert.equal(r.gop, 120);
  assert.deepEqual(r.gaps, [120, 180]);
});

t("a different fps yields a different frame GOP from the same timestamps", () => {
  assert.equal(gopFromKeyframes(MEASURED, 30).gop, 125);
  assert.equal(gopFromKeyframes(MEASURED, 60).gop, 250);
});

console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);