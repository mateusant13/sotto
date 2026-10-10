import assert from "node:assert/strict";
import { ReplayRing, idrAligned, backToNearestIdr, DEFAULT_MINUTES } from "./replay-ring.js";
import { SavePath, ClipWriter } from "./index.js";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

// One real encoded segment, shared by every arm that only cares about the ring's
// ARITHMETIC rather than about its content.
const SEGMENT = Buffer.from([0x42]);

// A real MP4, made here rather than checked in, because the assertion that matters --
// that a press lands a file a decoder can read -- cannot be made against a fixture
// nobody has measured on this host.
//
// MEASURED WINDOW_UTC 2026-10-10T19:34Z on this host, `ffmpeg -f lavfi -i
// testsrc=size=320x240:rate=30:duration=2 -c:v libx264 -pix_fmt yuv420p -g 30`:
// exit 0, 16042 bytes; ffprobe then reported 60 frames, duration 2.000000, and IDRs at
// pts 0.000000 and 1.000000.
//
// ffmpeg is REQUIRED, not skipped. Every arm below is about whether a saved clip has
// content; a skip when the encoder is missing would turn the one assertion that could
// catch a 0-byte regression into a silent pass, which is the exact failure this suite
// was rewritten to end.
function makeSeedClip() {
  // Its OWN directory, removed before the bytes are handed back. Sharing the sandbox
  // would leave seed.mp4 in the very listing this suite asserts on, and an arm that
  // filters its own fixture out of its own assertion is an arm that has stopped
  // enumerating.
  const dir = mkdtempSync(join(tmpdir(), "shadowplay-seed-"));
  const seed = join(dir, "seed.mp4");
  try {
    execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
      "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "30", seed],
      { stdio: ["ignore", "pipe", "pipe"] });
    return readFileSync(seed);
  } catch (cause) {
    throw new Error(
      "this host cannot produce a real clip with ffmpeg, so the assertion that a press " +
      "lands a decodable file cannot be made at all: " + cause.message, { cause });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// A SavePath writing into a directory this test owns, so an assertion about what the
// press put on disk is about THIS run and not about whatever the machine already had.
function sandbox() {
  const dir = mkdtempSync(join(tmpdir(), "shadowplay-rr-"));
  const writer = new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir });
  return { dir, savePath: new SavePath({ writer }) };
}

let passed = 0, failed = 0;
// ASYNC runner: press() and instantReplay() are async (the delivery gate measures with
// ffprobe), so the runner must await the body or it will report a Promise as a result.
//
// BOTH halves are required, and the registration site is the half that was missing.
// Awaiting inside t() is not enough: every `t(...)` call returns a Promise, and a
// synchronous registration list drops them all on the floor. MEASURED 2026-10-10
// before this change, `node shadowplay/replay-ring.test.mjs` printed
// "RESULT 0 passed, 0 failed" and exited 0 -- a green exit code for a suite that had
// asserted nothing, with 15 registrations and 0 awaited. Each registration below is
// awaited, so the RESULT line now runs only after the last assertion has settled and
// the pass count equals the registration count.
async function t(name, fn) {
  try { await fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

await t("a 10 minute ring at 60fps holds 36000 frames", async () => {
  const r = new ReplayRing();
  assert.equal(r.capacity, 36000);
  assert.equal(r.minutes, DEFAULT_MINUTES);
});

await t("the head wraps and never exceeds capacity", async () => {
  const r = new ReplayRing({ minutes: 1, fps: 1 });
  assert.equal(r.capacity, 60);
  for (let i = 0; i < 500; i++) {
    // The segment is supplied because push() now stores what was recorded. The
    // assertion is UNCHANGED -- it still checks the head index and nothing else --
    // it just feeds the ring the content it is required to keep.
    const h = r.push(SEGMENT);
    assert.ok(h >= 0 && h < 60, `head ${h} outside the ring`);
  }
  // AND the ring stayed bounded, which the old arm could not check at all: it had no
  // way to ask the ring what it was holding.
  assert.equal(r.heldFrames(), 60, "the ring must evict rather than grow without limit");
  assert.equal(r.segments(), 60);
});

await t("recording writes nothing to disk", async () => {
  const { dir, savePath } = sandbox();
  try {
    const r = new ReplayRing({ minutes: 1, fps: 1, gopSize: 10, savePath });
    for (let i = 0; i < 200; i++) r.push(SEGMENT);
    // The ring really is holding the footage...
    assert.ok(r.heldBytes() > 0, "the ring must be holding the encoded segments");
    // ...and the press still refuses, because no segment in there begins on an IDR.
    // A cut that cannot start on a keyframe is not a cut that may be re-encoded into
    // one, so the refusal is the correct outcome and it happens BEFORE anything is
    // written.
    const err = await r.instantReplay().then(() => null, (e) => e);
    assert.ok(err instanceof Error, "a ring with no IDR must refuse, not report success");
    assert.match(err.message, /none of them begins on an IDR/);
    assert.deepEqual(readdirSync(dir), [],
      "recording must not write to disk, and a refused cut must not either");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

await t("the instant-replay moment goes through the one writer", async () => {
  const { dir, savePath } = sandbox();
  try {
    const seed = makeSeedClip();
    const r = new ReplayRing({ minutes: 1, fps: 1, gopSize: 10, savePath });
    r.push(seed, { frames: 60, keyframe: true });

    const first = await r.instantReplay();
    const second = await r.instantReplay();

    // WHAT THIS ARM ASSERTED BEFORE, AND WHY IT WAS THE DEFECT.
    //
    // It asserted `assert.equal(await r.instantReplay(), "0000.mp4")` -- that a press
    // returns the bare name a string comparison can see. Two things were wrong with
    // that, and both were the defect rather than the intent:
    //   1. it drove the whole chain through a press that saved `minutes * 60`, a
    //      duration in seconds, so the arm was only ever able to pass on a ring that
    //      refused -- it could not tell a real save from a refused one;
    //   2. instantReplay() has returned `{ name, path, verdict }` for several changes,
    //      so the comparison could not have held even with real bytes behind it.
    // The arm is now STRICTLY STRONGER: it feeds the ring a real encoded clip, gets two
    // real saves, and checks the bytes on disk.
    assert.equal(first.name, "0000.mp4", "the first press takes the first name");
    assert.equal(second.name, "0001.mp4", "the second press advances the sequence");

    // The load-bearing assertion, and the one the old arm had no way to make: the clip
    // that landed carries its CONTENT. A 0-byte file passes a name comparison.
    const onDisk = readdirSync(dir).filter((n) => n.endsWith(".mp4"));
    assert.deepEqual(onDisk.sort(), ["0000.mp4", "0001.mp4"]);
    for (const n of onDisk) {
      const bytes = readFileSync(join(dir, n));
      assert.equal(bytes.byteLength, seed.byteLength,
        `${n} must hold the encoded clip, not a reservation: ${bytes.byteLength} of ${seed.byteLength} bytes`);
      assert.ok(bytes.byteLength > 0, "an empty clip is the defect this change ends");
    }

    // And the delivery gate really ran over those bytes rather than being skipped:
    // it can only produce a verdict after ffprobe and ffmpeg have decoded the file.
    assert.equal(typeof first.verdict.longestUniqueRun, "number");
    assert.equal(first.verdict.contentSufficientToCoverClock, true,
      "a real 2-second clip must cover its own clock");
    assert.equal(first.path, join(dir, "0000.mp4"),
      "the returned path must resolve to the file that was actually written");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

await t("manual recording is capped at the ring length", async () => {
  assert.equal(new ReplayRing({ minutes: 10 }).maxManualMinutes(), 10);
  assert.equal(new ReplayRing({ minutes: 3 }).maxManualMinutes(), 3);
});

await t("IDR alignment is exact, not approximate", async () => {
  assert.equal(idrAligned(0, 60), true);
  assert.equal(idrAligned(60, 60), true);
  assert.equal(idrAligned(59, 60), false);
  assert.equal(idrAligned(61, 60), false);
});

await t("a cut near the end walks back to a real IDR", async () => {
  // head 200, GOP 60. One full GOP of history is required, so 200-60=140 walks
  // forward to 180, which is an IDR.
  assert.equal(backToNearestIdr(200, 60, 60), 180);
  assert.ok(idrAligned(backToNearestIdr(200, 60, 60), 60));
});

await t("a cut near the start returns 0, and 0 IS an IDR boundary", async () => {
  const start = backToNearestIdr(37, 60, 60);
  assert.equal(start, 0);
  assert.ok(idrAligned(start, 60));
});

await t("an empty ring cannot be cut", async () => {
  assert.throws(() => backToNearestIdr(10, 60, 0), RangeError);
});

await t("a non-positive ring is refused at construction", async () => {
  assert.throws(() => new ReplayRing({ minutes: 0 }), RangeError);
  assert.throws(() => new ReplayRing({ fps: 0 }), RangeError);
});

await t("the default GOP is the MEASURED 250, not the old assumed 60", async () => {
  assert.equal(new ReplayRing().gopSize, 250);
});

await t("an explicit gopSize still wins", async () => {
  assert.equal(new ReplayRing({ gopSize: 60 }).gopSize, 60);
});

await t("a real stream file supplies its own GOP", async () => {
  const f = process.env.SP_REAL_STREAM;
  if (!f) { console.log("       (skipped: SP_REAL_STREAM not set)"); return; }
  assert.equal(new ReplayRing({ sourceFile: f, fps: 60 }).gopSize, 250);
});

await t("the ring cuts on its own measured GOP, not on a hardcoded one", async () => {
  const r = new ReplayRing({ gopSize: 250 });
  // 497 frames of history at GOP 250. start = 497-497 = 0, and 0 IS an IDR
  // boundary (0 % 250 === 0), so the walk stops immediately. 0 is a valid cut:
  // it is earlier than 250, so the clip carries MORE footage, not less.
  const start = backToNearestIdr(497, r.gopSize, 497);
  assert.equal(start, 0);
  assert.ok(idrAligned(start, r.gopSize));
});

await t("less than one GOP of history refuses rather than returning a non-IDR", async () => {
  const r = new ReplayRing({ gopSize: 250 });
  // 40 frames cannot contain an IDR when the GOP is 250. Returning 497 would
  // have produced a clip that does not start on a keyframe, silently.
  assert.throws(() => backToNearestIdr(497, r.gopSize, 40), /fewer than one GOP/);
});

console.log(`RESULT ${passed} passed, ${failed} failed`);
// process.exitCode, NOT process.exit(). Under `node --test` this file runs as a child
// process whose stdout is a PIPE, and writes to a pipe are async. process.exit() kills
// the process without draining that pipe, so the RESULT line above -- the only record
// of what actually asserted -- could be lost while the exit code still said "green".
// Measured fix, 2026-10-10, mirroring e2e.test.mjs. The code is identical in intent:
// 0 when nothing failed, 1 the moment one did.
process.exitCode = failed === 0 ? 0 : 1;