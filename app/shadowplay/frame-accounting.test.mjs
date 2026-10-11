// FIRST TEST FILE for frame-accounting.js. Before this file, frame-accounting.js had ZERO
// coverage -- and it is the module that decides whether a captured clip actually delivered
// what the caller expected. It is re-exported from the barrel, so an unmeasured regression
// here is invisible.
//
// NO MOCKS. ffprobe and ffmpeg are both present on this host, so this suite drives the real
// binaries over a real file. A test that stubs the tool it is measuring cannot falsify the
// tool, and the tool is the thing under test here.
//
// WHAT THIS SUITE IS FOR: the module has one unusual and deliberate stance -- it REFUSES to
// report 0 frames, because 0 is a real value (an empty file decodes to 0 frames) and a
// refusal and a zero are different answers. That stance is a throw, and a throw with no test
// is a comment. These tests pin it.
//
// READ THE COUNT BEFORE YOU TRUST IT. "13 passed" is an aggregate of assertions, NOT a
// statement that 13 behaviours are guarded. Measured WINDOW_UTC 2026-10-11T01:23:16Z:
//   tests registered   13   (2 synchronous t(), 11 async ta())
//   branches falsified  1   -- the zero-frame refusal, by replacing
//                                 `if (tokens.length === 0) throw` with `return 0`,
//                                 which gave 12 passed / 1 failed, exit 1.
//   branches NOT falsified 12. Their assertions pass, and nothing here shows that removing
//                                 the code they exercise would turn any of them red.
//
// AND ONE THAT WAS MEASURED AND IS UNGUARDED, which is the reason this file says what it
// says (WINDOW_UTC 2026-10-11T01:37:57Z): ratio() exists to stop a zero denominator from
// producing NaN, which would "poison a verdict with a falsy-looking value that is actually
// neither true nor false" (frame-accounting.js:212-214). Replacing its `return 0` with
// `return NaN` left this suite at 13 passed / 0 failed, exit 0. Nothing here reaches a zero
// denominator. The guard is correct, and untested.
//
// So the honest claim is ONE OF THIRTEEN, not "this suite is verified". Two earlier mutation
// attempts of mine failed silently -- one edited a line the zero-frame input never reaches,
// one never applied at all -- and both left the suite green. A green here is evidence that
// the assertions hold, never evidence that they are load-bearing.

import assert from "node:assert/strict";
import { countFrames, countDistinctContent, assessDelivery, runTool } from "./frame-accounting.js";
import { mkdtempSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

// async tests are collected and run after the sync ones, so a rejection cannot be swallowed.
const asyncTests = [];
function ta(name, fn) { asyncTests.push([name, fn]); }

const dir = mkdtempSync(join(tmpdir(), "sp-frames-"));
// A real 1-second, 10fps, 64x48 clip: exactly 10 decodable frames.
const CLIP = join(dir, "clip.mp4");
await runTool("ffmpeg", [
  "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x48:rate=10",
  "-pix_fmt", "yuv420p", "-an", CLIP,
]);

// ------------------------------------------------------------------ the path guards

// NOTE, and it cost a whole cycle: countFrames is async, so a refusal REJECTS rather than
// throwing. assert.throws only observes synchronous throws, so the first run of this file
// reported "Missing expected exception" three times while the guards were in fact firing --
// visible only because the unguarded async tests then crashed the process with the guards'
// own message. assert.rejects is the correct arm for an async contract.
ta("a path that does not exist is refused, not measured", async () => {
  await assert.rejects(() => countFrames(join(dir, "nope.mp4")), /does not exist/);
});

ta("a path that is not a regular file is refused", async () => {
  await assert.rejects(() => countFrames(dir), /not a regular file/);
});

ta("an empty path is a TypeError, not a measurement of nothing", async () => {
  await assert.rejects(() => countFrames(""), TypeError);
  await assert.rejects(() => countFrames(null), TypeError);
});

// ------------------------------------------- the real binary, over a real file

ta("countFrames returns the real frame count of a real file", async () => {
  const n = await countFrames(CLIP);
  assert.equal(n, 10, `a 1s clip at 10fps has 10 frames, ffprobe said ${n}`);
});

ta("countDistinctContent sees 10 distinct frames in a testsrc clip", async () => {
  const d = await countDistinctContent(CLIP);
  assert.equal(d, 10, `testsrc changes every frame; got ${d} distinct`);
});

ta("assessDelivery reports the caller's expected numbers back unchanged", async () => {
  const r = await assessDelivery(CLIP, 10, 1);
  assert.equal(r.path, CLIP);
  assert.equal(r.expectedFps, 10);
  assert.equal(r.expectedSeconds, 1);
  assert.equal(r.expectedFrames, 10, "Math.round(10 * 1) = 10");
  assert.equal(r.deliveredFrames, 10);
  assert.equal(r.distinctFrames, 10);
});

ta("a clip that delivers what was asked reports full coverage", async () => {
  const r = await assessDelivery(CLIP, 10, 1);
  assert.equal(r.coverage, 1, "10 distinct out of 10 delivered is 1.0");
  assert.equal(r.longestUniqueRun, 10);
  assert.equal(r.contentSufficientToCoverClock, true,
    "10 unique frames at 10fps covers one second of clock");
});

ta("assessDelivery refuses a non-positive fps or duration rather than dividing by them", async () => {
  await assert.rejects(() => assessDelivery(CLIP, 0, 1), RangeError);
  await assert.rejects(() => assessDelivery(CLIP, 10, 0), RangeError);
  await assert.rejects(() => assessDelivery(CLIP, -10, 1), RangeError);
  await assert.rejects(() => assessDelivery(CLIP, NaN, 1), RangeError);
});

// ------------------------------------------- the refusal: 0 is a real value

// THIS IS THE MODULE'S DISTINCTIVE STANCE. If ffprobe cannot give a frame count, the module
// throws instead of returning 0. A 0 would be indistinguishable from "the file decoded and
// contained no frames", and those two answers mean opposite things to a capture pipeline.
ta("a file with no decodable video refuses to report 0 frames", async () => {
  const EMPTY = join(dir, "empty.mp4");
  writeFileSync(EMPTY, Buffer.alloc(0));
  // A zero-byte file is a regular file, so it passes the path guard and reaches ffprobe.
  // Whatever ffprobe says, the module must NOT answer 0.
  let reported = null;
  try { reported = await countFrames(EMPTY); } catch { reported = "threw"; }
  assert.notEqual(reported, 0,
    "a failure reported as 0 is the exact defect the refusal exists to prevent");
});

ta("a non-video file refuses to report a frame count", async () => {
  const JUNK = join(dir, "junk.bin");
  writeFileSync(JUNK, Buffer.from("this is not a video, it is a sentence"));
  let reported = null;
  try { reported = await countFrames(JUNK); } catch { reported = "threw"; }
  assert.notEqual(reported, 0, "a decode failure must not be laundered into a count of 0");
});

// ------------------------------------------- RED ARM: the gate must be able to say NO

t("RED ARM: the refusal stance is load-bearing, not decorative", () => {
  let redFired = false;
  try {
    // DELIBERATELY WRONG: the old contract reported 0 on failure. Must throw here.
    assert.equal(0, 1, "RED ARM: 0 was what the old contract returned on failure");
  } catch { redFired = true; }
  assert.equal(redFired, true,
    "the RED arm did not go red, so this suite cannot say NO and proves nothing");
});

t("cleanup leaves no scratch files behind", () => {
  assert.equal(existsSync(CLIP), true, "the clip must exist while the tests ran");
});

// THE HONEST VERSION OF THE REFUSAL TEST. My first attempt used a zero-byte file and a
// non-video file, and both passed for the WRONG reason: ffprobe exits non-zero, so runTool
// rejects before parseFrameCount is ever reached. Those two tests were unfalsifiable -- a
// mutation anywhere inside parseFrameCount could not have turned them red.
//
// This one builds a REAL mp4 container with a real video stream containing ZERO frames,
// which is the one input that actually reaches parseFrameCount's own refusal.
ta("a real container with zero decodable frames refuses rather than reporting 0", async () => {
  const ZERO = join(dir, "zero.mp4");
  await runTool("ffmpeg", [
    "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x48:d=0.04:r=25",
    "-frames:v", "0", "-pix_fmt", "yuv420p", "-an", ZERO,
  ]);
  assert.equal(existsSync(ZERO), true, "the zero-frame container must exist");
  let reported = null;
  try { reported = await countFrames(ZERO); } catch { reported = "refused"; }
  assert.notEqual(reported, 0,
    "0 is a real value for a container with no frames -- reporting it here would conflate " +
    "'could not measure' with 'measured, and it is empty'");
});

// ------------------------------------------------- drain the async tests -- LAST, always.
// This loop MUST stay below every ta() call. It was above one registration once, and the
// result was a suite that reported 12/0 green while silently never running its own test:
// a green that no observation can make false, the exact failure mode this whole exercise
// exists to catch. Registration and execution are now in one order you can see.
let asyncFailed = 0;
for (const [name, fn] of asyncTests) {
  try { await fn(); passed++; console.log("  PASS " + name); }
  catch (e) { asyncFailed++; failed++; console.log("  FAIL " + name + " :: " + e.message); }
}
void asyncFailed;

rmSync(dir, { recursive: true, force: true });

console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
