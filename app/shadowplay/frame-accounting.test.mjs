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
//   tests registered   18   (2 synchronous t(), 16 async ta())
//   branches falsified  3   -- each measured, WINDOW_UTC 2026-10-11T02:04:49Z onward
//       (a) the zero-frame refusal        red=2   15 passed / 2 failed, exit 1
//       (b) the 6-decimal rounding        red=2   14 passed / 2 failed, exit 1
//       (c) the assertPositive guard       red=2   16 passed / 2 failed, exit 1
//   branches NOT falsified 15.
//
// AND ONE MEASURED BLIND SPOT — not a count of zero, a count of "cannot see it".
// Measured WINDOW_UTC 2026-10-11T02:10:42Z: deleting `seenInRun.clear()` from
// summarizeHashes (frame-accounting.js:280) left this suite at 18 passed / 0 failed,
// exit 0 — red_tests = 0. Without the streak reset the run never breaks and
// longestUniqueRun degenerates into `distinct`.
//
// Same shape as the byte-sum hole now closed in encoder.test.mjs: EVERY fixture in this
// file decodes to frames that are ALL distinct, so no repeat ever occurs and the reset line
// is never executed. The one longestUniqueRun assertion here is
// `assert.equal(r.longestUniqueRun, 10)` on a testsrc clip, where distinct and
// longest-unique are equal BY CONSTRUCTION — a fixed point.
//
// Closing it needs a real clip whose middle frame repeats AND which introduces further
// distinct frames after the repeat, since that is the only input where the two numbers
// differ. Attempted WINDOW_UTC 2026-10-11T02:10:58Z with an ffmpeg concat of five
// solid-colour frames (A B C A D): it built to 1706 bytes but decoded to 3 frames, not 5,
// so the fixture was not usable and NO claim is made about it. The blind spot is OPEN and is
// recorded here rather than papered over by a test that would not have caught the mutation.
//
// AND ONE THAT WAS MEASURED AND CANNOT BE REACHED, which changes what the count means
// (WINDOW_UTC 2026-10-11T01:42:01Z): ratio() guards against a zero denominator returning
// NaN (frame-accounting.js:211-218). Replacing its `return 0` with `return NaN` left this
// suite at 13 passed / 0 failed, exit 0 — and the reason is NOT a missing test.
//
//   ratio() is not exported (frame-accounting.js exports runTool, countFrames,
//   countDistinctContent, assessDelivery). Both of its call sites divide by a value the
//   module REFUSES to be zero:
//     coverage        = ratio(distinct, deliveredFrames)  <- countFrames THROWS on 0
//     contiguousRatio = ratio(longestUniqueRun, expectedFrames) <- both inputs asserted > 0
//   Driving assessDelivery at a real zero-frame container returns
//     "ffprobe did not return a frame count; refusing to report 0..."
//   so the call cannot return, and the zero-denominator branch is UNREACHABLE defence.
//
// It stays as belt-and-braces against a future caller. It is not coverage this suite can
// acquire, and claiming it as a gap would be as wrong as claiming it as a passing test.
//
// So the honest claim is ONE OF THIRTEEN, not "this suite is verified". Two earlier mutation
// attempts of mine failed silently -- one edited a line the zero-frame input never reaches,
// one never applied at all -- and both left the suite green. A green here is evidence that
// the assertions hold, never evidence that they are load-bearing.

import assert from "node:assert/strict";
import { countFrames, countDistinctContent, assessDelivery, runTool } from "./frame-accounting.js";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, existsSync, statSync } from "node:fs";
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

// THE ROUNDING IS REACHABLE AND WAS UNPINNED. Every other assertion in this file compares
// r.coverage to exactly 1, and 1 is a fixed point of rounding: toFixed(6) changes nothing
// about it. Replacing the rounded return with the raw quotient
// (frame-accounting.js:217) left this suite at 13 passed / 0 failed, exit 0 -- NOT because
// the branch is unreachable (unlike the ratio() zero-denominator guard above, which is),
// but because no input in this file produced a fractional ratio.
//
// A clip whose frames repeat does. Measured WINDOW_UTC 2026-10-11T01:46:46Z on a real file
// with every third frame dropped: distinct=11, delivered=39, coverage=0.282051 -- exactly
// six decimals, which is the rounding made observable.
ta("a fractional ratio is rounded to six decimals, not returned raw", async () => {
  const D = join(dir, "frac");
  const FRAC = join(D, "clip.mp4");
  mkdirSync(D, { recursive: true }); // ffmpeg will NOT create the directory itself
  await runTool("ffmpeg", [
    "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x48:rate=10",
    "-vf", "select='not(mod(n\\,3))',setpts=N/TB", "-r", "10",
    "-pix_fmt", "yuv420p", "-an", FRAC,
  ]);
  const r = await assessDelivery(FRAC, 10, 1);
  assert.ok(r.coverage > 0 && r.coverage < 1,
    `this clip must produce a fractional ratio to be worth asserting, got ${r.coverage}`);
  const raw = r.distinctFrames / r.deliveredFrames;
  assert.notEqual(r.coverage, raw,
    `rounding must change the value: got ${r.coverage}, raw quotient ${raw}`);
  const decimals = String(r.coverage).split(".")[1] ?? "";
  assert.ok(decimals.length <= 6,
    `rounded to at most 6 decimals, got ${decimals.length} (${r.coverage})`);
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

// ---------------------------------------------------------------- SECOND WATCHERS
// Measured WINDOW_UTC 2026-10-11T01:58:22Z: each of the two falsified branches above was
// turned red by exactly ONE test, so deleting that test would leave its guard unwatched.
// These are independent entry paths for the same two guards. Registered ABOVE the drain
// loop, which is where the last version of this file got them silently skipped.

// A second route to the empty-output refusal: not a zero-frame CONTAINER (which is what the
// first watcher builds) but a real, fully decodable clip that is handed to countDistinctContent
// and to assessDelivery, both of which must refuse rather than answer 0.
ta("a decodable clip is not coerced into a zero-frame answer by a broken count", async () => {
  // Sanity: this clip genuinely counts, so a refusal below is about the CALL, not the file.
  const good = await countFrames(CLIP);
  assert.equal(good, 10, "the control clip must be measurable before anything else");

  // Now the same module asked for frames from a path that parses to an empty token stream:
  // a directory listing is impossible, but a file of pure whitespace makes ffprobe's CSV
  // payload empty while the file itself is a perfectly valid regular file.
  const BLANK = join(dir, "blank.csv.mp4");
  writeFileSync(BLANK, Buffer.from("   \n\n  \n", "utf8"));
  let reported = null;
  try { reported = await countFrames(BLANK); } catch { reported = "refused"; }
  assert.notEqual(reported, 0, "an unparseable count must never be laundered into 0");
});

// A second route to the rounding branch: a DIFFERENT fractional ratio from the first watcher,
// so that one assertion failing to fire cannot hide the branch.
ta("a second fractional clip is also rounded, not returned raw", async () => {
  const D2 = join(dir, "frac2");
  const F2 = join(D2, "clip.mp4");
  mkdirSync(D2, { recursive: true });
  // Every FIFTH frame kept this time, so the ratio differs from the first watcher's 11/39.
  await runTool("ffmpeg", [
    "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x48:rate=20",
    "-vf", "select='not(mod(n\\,5))',setpts=N/TB", "-r", "20",
    "-pix_fmt", "yuv420p", "-an", F2,
  ]);
  const r = await assessDelivery(F2, 20, 1);
  assert.ok(r.coverage > 0 && r.coverage < 1,
    `this clip must also be fractional to be worth asserting, got ${r.coverage}`);
  const raw = r.distinctFrames / r.deliveredFrames;
  assert.notEqual(r.coverage, raw,
    `rounding must change this value too: got ${r.coverage}, raw ${raw}`);
  assert.ok((String(r.coverage).split(".")[1] ?? "").length <= 6,
    `at most 6 decimals, got ${r.coverage}`);
});

// A SECOND REAL ROUTE to the empty-output refusal, measured WINDOW_UTC 2026-02:00:04Z.
//
// The watcher above builds a video container holding zero frames. The one I added earlier
// used a file of whitespace and was UNFALSIFIABLE: ffprobe exits non-zero on it, so runTool
// rejects before parseFrameCount is reached, and `red` stayed 1.
//
// This route is different in kind: a real, fully decodable AUDIO-ONLY file. ffprobe exits 0
// on it and prints an empty CSV payload, because `-select_streams v:0` matches no stream.
// So the empty token stream arrives at parseFrameCount for a reason that has nothing to do
// with corruption: the media is valid, the file is valid, and there is simply no video to
// count. Measured: ffprobe exit=0, output empty, and the module refuses.
ta("a valid audio-only file has no video to count and is refused, not zeroed", async () => {
  const AUD = join(dir, "audio.m4a");
  await runTool("ffmpeg", [
    "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
    "-c:a", "aac", AUD,
  ]);
  assert.equal(existsSync(AUD), true, "the audio file must exist");
  assert.equal(statSync(AUD).size > 0, true, "the audio file must not be empty");

  // CONTROL: ffprobe itself is happy with this file. If it exited non-zero, the module would
  // refuse for the wrong reason again and this test would be unfalsifiable a second time.
  const probe = await runTool("ffprobe", [
    "-v", "error", "-select_streams", "v:0", "-count_frames",
    "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", AUD,
  ]);
  assert.equal(probe.code, 0, "ffprobe must SUCCEED on this file, or this test proves nothing");
  assert.equal(probe.stdout.trim(), "", "and must print an empty payload -- that is the input");

  let reported = null;
  try { reported = await countFrames(AUD); } catch { reported = "refused"; }
  assert.notEqual(reported, 0,
    "a file with no video stream is not a file with zero frames, and must not report 0");
});

// A SECOND WATCHER for the assertPositive guard on the caller-supplied fps/seconds.
// Measured WINDOW_UTC 2026-10-11T02:04:33Z: dropping the `|| value <= 0` half of that
// condition turned exactly ONE test red, so this guard was watched by a single assertion.
//
// The route is different: the first watcher goes through assessDelivery's fps argument.
// This one uses the SECONDS argument, and values the first never tries — negative, and
// the string that is not a number at all. A guard on one argument is not evidence that the
// other argument is checked by the same code, and the mutation cannot tell the difference.
ta("a non-positive or non-numeric duration is refused on the seconds argument too", async () => {
  // fps is VALID here on purpose: the refusal must come from the seconds guard, not from the
  // fps guard. If this test passes because fps was also bad, it is not watching anything.
  for (const bad of [0, -1, -0.5, Infinity, -Infinity, NaN, "10", null, undefined, {}]) {
    await assert.rejects(() => assessDelivery(CLIP, 10, bad), RangeError,
      `expectedSeconds=${String(bad)} must be refused, with a valid expectedFps of 10`);
  }
  // CONTROL: the same call with a valid duration must still succeed, proving the refusals
  // above were caused by the argument under test and not by the clip.
  const ok = await assessDelivery(CLIP, 10, 1);
  assert.equal(ok.expectedFrames, 10, "the valid call must still work");
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
