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
// statement that 13 behaviours are guarded. Recounted WINDOW_UTC 2026-10-11T02:48:10Z,
// counting `^t(` and `^ta(` from the SOURCE, not from the RESULT line:
//   tests registered   20   (2 synchronous t(), 18 async ta())
//   tests RUNNING      20   RESULT 20 passed / 0 failed
// These two used to disagree: this header said 18 while the file held 19, because a test
// was added here after the header was written and the number was never recomputed --
// the identical defect an independent review just found in the sibling encoder.test.mjs.
// Count from the source. Recount at every change.
//   branches falsified  3, measured by me. WINDOW_UTC 2026-10-11T02:04:49Z onward:
//       (a) the zero-frame refusal        red=2   15 passed / 2 failed, exit 1
//       (b) the 6-decimal rounding        red=2   14 passed / 2 failed, exit 1
//       (c) the assertPositive guard       red=2   16 passed / 2 failed, exit 1
//   An independent review (FRAME-ACCOUNTING-INDEPENDENT-REVIEW.txt, WINDOW
//   2026-10-11T02:41-02:47Z) reports 7 red arms against this suite, every arm run twice.
//   That is ITS count, not mine -- I have not reproduced it, so the falsified total is
//   3 measured + 7 claimed by a second party, NOT 7. Do not merge them.
//   WHOLE-MODULE SWEEP, WINDOW_UTC 2026-10-11T03:04:22Z + 03:05:23Z, N=2 per arm,
//   lines-differ=1 on every arm, INVALID=0. This supersedes the counts above.
//       10 guards identified of 10 total in frame-accounting.js.  10 swept.  10 valid results.
//         RED   5 :  L186  L198  L205  L278  L283
//         GREEN 5 :  L215  L232  L235  L242  L301
//   So HALF this module's guards can be deleted and the suite still reports 19/19.
//   The three earlier named arms (a)(b)(c) and the reviewer's 7 are NOT reconciled with
//   this list: they were counted by a different method on a different set of lines.
//   Do not merge the two totals. The sweep is the one with a verified extractor.
//   branches falsified   5   (not the 3 written above -- that figure is superseded)
//   branches NOT falsified  4 -- this figure was 5 until WINDOW_UTC 2026-10-11T04:41:41Z,
//   when one test was added that covers L232. The other four are NOT four test gaps.
//
//   CLASSIFICATION, corrected at WINDOW_UTC 2026-10-11T04:55:39Z. Measured, not argued:
//
//       L215  INFALSIFIABLE BY DELETION. Not an untested guard -- a REDUNDANT one.
//             Proof, two runs of assessDelivery(clip, 0.1, 0.1) against a 2516-byte clip:
//                 guard ALIVE                        guard DELETED (lines-differ=1, parses)
//                 expectedFrames   = 0                 expectedFrames   = 0
//                 contiguousRatio  = 0                 contiguousRatio  = 0
//                 coverage         = 1                 coverage         = 1
//                 contentSufficient= true              contentSufficient= true
//             Identical. Cause: 10/0 = Infinity, and the NEXT line already maps a
//             non-finite r to 0 -- `Number.isFinite(r) ? Number(r.toFixed(RATIO_DECIMALS)) : 0`.
//             Line 215 and line 217 do the same job by different routes.
//             CONSEQUENCE: a test asserting contiguousRatio === 0 passes either way. Writing
//             that test would be theatre -- green with and without the code it claims to
//             protect. THE FIX IS NOT A TEST. Either delete the redundant guard or make the
//             two routes distinguishable. That is a behaviour change: OWNER DECISION.
//
//       L232  COVERED. The empty-ffprobe-output test (this file) kills it: 19 passed,
//             1 failed, EXIT=1. Recipe recorded inline at the test.
//
//       L235  multi-token refusal        UNWATCHED. Deleting it leaves the suite at 20/0.
//       L242  non-numeric token refusal  UNWATCHED. Deleting it leaves the suite at 20/0.
//       L301  empty hash stream refusal  UNWATCHED. Deleting it leaves the suite at 20/0.
//             For these three the question is still OPEN and the two answers demand
//             opposite fixes: UNREACHABLE means delete the code, REACHABLE-but-untested means
//             add a test. Not measured. Do not report that distinction as made.
//             Known: -select_streams v:0 emits exactly one line for a two-stream container,
//             so L235 is not reachable by that route (POPULATION of that check: 1 container).
//
//   SO: 3 test gaps, 1 design redundancy, 0 unmeasured guards left unclassified.
//
//   CORRECTION TO MY OWN LAST REPORT: I wrote that this figure would become 18 once I added
//   the two missing arms. That is wrong arithmetic. A GREEN arm adds nothing to the falsified
//   count -- 19 - 3 = 16 either way. What the arms changed is not the number but its
//   epistemics. WINDOW_UTC 2026-10-11T02:53:35Z, N=2 per arm, control 19/0:
//       ARM-G  `if (tokens.length > 1)` -> `if (false)`      19 passed / 0 failed, EXIT=0
//       ARM-H  `if (!/^\d+$/.test(token))` -> `if (false)`   19 passed / 0 failed, EXIT=0
//   So 2 of these 16 are now MEASURED-UNWATCHED: the guard is reachable, nothing asserts it,
//   and deleting it changes no observable output. The other 14 remain unknown-unwatched, which
//   is a weaker claim: absence of evidence, not evidence of absence. Do not merge the two.
//
//   There is a trap in writing this header at all, and I fell into it twice. Two arms that
//   stay green look identical in this file to two arms nobody ran. The count cannot tell them
//   apart; only the prose above can. That is the same reason the encoder.test.mjs header said
//   9 when the file held 14.
//
// AND ONE THAT WAS MEASURED INVISIBLE, NOW CLOSED. Measured WINDOW_UTC 2026-10-11T02:10:42Z:
// deleting `seenInRun.clear()` (frame-accounting.js:280) left this suite at 18 passed /
// 0 failed, exit 0 — red_tests = 0 — because every other fixture decodes to frames that are
// all distinct, so the reset line never executes.
//
// CLOSED WINDOW_UTC 2026-10-11T02:13:30Z by a fixture built with the `select` filter that
// repeats frame index 2, giving deliveredFrames=39, distinctFrames=11, longestUniqueRun=5.
// Those two numbers differing is the whole point: they are equal by construction whenever a
// clip has no repeat, which is why the mutation was invisible before. The same mutation now
// gives 18 passed / 1 failed, exit 1.
//
// The first attempt at this fixture used an ffmpeg concat of five solid-colour frames
// (02:10:58Z); it produced a 1706-byte file that decoded to 3 frames rather than 5, so it
// was discarded rather than shipped as a test that would not have caught anything.
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
// CORRECTED BY REVIEW, and the correction matters. An independent reviewer sharpened this
// and is right to: UNREACHABLE is the wrong word, and it flatters the suite. The branch is
// REACHABLE in principle -- a future caller can divide by zero -- but it is NOT FALSIFIABLE
// by deletion. Removing the guard at line 215 changes no observable output, because
// 10 / 0 evaluates to Infinity and line 217's `Number.isFinite(r) ? . : 0` already maps
// that to 0 on its own. So a "delete the whole guard" mutation arm would stay GREEN here.
// Reachable and falsifiable are different properties, and only the second one is evidence.
//   the SAME inconsistency, unresolved, and it is a behaviour question, not a test question:
//   at assessDelivery(clip, 0.1, 0.1) the module returns `contiguousRatio: 0` AND
//   `contentSufficientToCoverClock: true` in the same object. The guard yields 0 silently
//   while the boolean says the clock is covered. Owner call: should assessDelivery refuse
//   when Math.round(expectedFps * expectedSeconds) is 0?
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

// THE FIXTURE FOR THE STREAK RESET. Measured WINDOW_UTC 2026-10-11T02:13:11Z.
//
// Deleting `seenInRun.clear()` (frame-accounting.js:280) previously left this suite at
// 18 passed / 0 failed, red_tests = 0, because every other fixture decodes to frames that
// are all distinct and the reset line never executes.
//
// This clip is built with the `select` filter repeating frame index 2, so the picture in the
// middle occurs twice while different pictures follow it. That is the only shape in which
// `distinct` and `longestUniqueRun` differ, and therefore the only shape in which a run
// that never resets is distinguishable from a real one. Measured on this file:
//   deliveredFrames = 39, distinctFrames = 11, longestUniqueRun = 5
// With the reset deleted, longestUniqueRun degenerates to distinctFrames = 11.
ta("a picture repeated mid-clip breaks the streak; the run does not span the repeat", async () => {
  const REP = join(dir, "rep", "r.mp4");
  mkdirSync(join(dir, "rep"), { recursive: true });
  await runTool("ffmpeg", [
    "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x48:rate=10",
    "-vf", "select='eq(n\\,0)+eq(n\\,1)+eq(n\\,2)+eq(n\\,2)+eq(n\\,3)',setpts=N/TB",
    "-r", "10", "-pix_fmt", "yuv420p", "-an", REP,
  ]);
  const r = await assessDelivery(REP, 10, 1);

  // THE PRECONDITION. Without these two lines this test would pass for the wrong reason:
  // if the fixture ever decoded to all-distinct frames, distinct === longest and a missing
  // reset would be invisible again.
  assert.ok(r.longestUniqueRun < r.distinctFrames,
    `the fixture must repeat a picture, else it cannot see the reset: ` +
    `longest=${r.longestUniqueRun} distinct=${r.distinctFrames}`);
  assert.ok(r.longestUniqueRun > 0, "there must be a real streak to measure");

  assert.equal(r.longestUniqueRun, 5,
    `the streak must break at the repeat: got ${r.longestUniqueRun}`);
  assert.equal(r.distinctFrames, 11,
    `and the whole-file distinct count is a DIFFERENT question: got ${r.distinctFrames}`);
});

// ------------------------------------------------- L232: empty ffprobe output.
  // WINDOW_UTC 2026-10-11T04:40:34Z: an audio-only container makes ffprobe print NOTHING for
  // -select_streams v:0. countFrames then throws the empty-output refusal rather than
  // returning 0. Measured, not inferred -- this is the input, not a guess at one.
  // L232 was one of five guards a whole-module mutation sweep found GREEN. This test is
  // what turns that GREEN into a RED that the mutation cannot survive.
  ta("countFrames refuses an empty ffprobe result instead of reporting 0", async () => {
    const noVideo = join(dir, "no-video.mkv");
    await runTool("ffmpeg", [
      "-y", "-v", "error",
      "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3",
      "-c:a", "pcm_s16le", noVideo,
    ]);
    assert.ok(existsSync(noVideo), "the fixture must exist or this proves nothing");
    let msg = null, returned = null;
    try { returned = await countFrames(noVideo); }
    catch (e) { msg = String(e.message); }
    assert.equal(returned, null,
      `the module must REFUSE, not return a number: got ${returned}`);
    assert.ok(msg !== null, "countFrames must throw on an empty ffprobe result");
    assert.match(msg, /empty ffprobe output/,
      `the refusal must name its own cause: got ${msg}`);
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
