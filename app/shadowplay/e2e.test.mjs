// End-to-end: barrel -> hotkey -> ring -> writer -> clock, in a REAL temp dir.
// This is the test that was missing. The module suites each proved their own
// arithmetic; this proves the chain runs.
import assert from "node:assert/strict";
// writeFileSync, SessionClock and idrAligned were imported for arms that asserted the
// 0-byte defect: they hand-wrote filler over the reserved file (writeFileSync) and
// counted names from a fresh clock (SessionClock). Those arms are gone, and with them
// the imports -- an unused import is a claim that something still needs it.
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { HotkeyRouter, ReplayRing, SavePath, ClipWriter,
         Encoder, backToNearestIdr, composeShadowplay } from "./index.js";

let passed = 0, failed = 0;
// ASYNC runner: press() and instantReplay() are async (the delivery gate measures with
// ffprobe), so the runner must await the body or it will report a Promise as a result.
//
// BOTH halves are required, and the registration site is the half that was missing.
// Awaiting inside t() is not enough: every `t(...)` call returns a Promise, and a
// synchronous registration loop would drop it on the floor. MEASURED
// 2026-10-10T12:54-12:56Z on this host: with an unawaited registration, `node
// e2e.test.mjs` printed "RESULT 0 passed, 0 failed" and exited 0 -- a green exit code
// for a suite that had asserted nothing. Each registration below is awaited, so
// process.exit() below now runs only after the last assertion has settled.
async function t(name, fn) {
  try { await fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

// A real encoded clip, made here rather than checked in.
//
// MEASURED WINDOW_UTC 2026-10-10T19:34Z on this host, `ffmpeg -f lavfi -i
// testsrc=size=320x240:rate=30:duration=2 -c:v libx264 -pix_fmt yuv420p -g 30`:
// exit 0, 16042 bytes; ffprobe reported 60 frames, duration 2.000000, IDRs at
// pts 0.000000 and 1.000000. ffmpeg is REQUIRED rather than skipped: the arms below
// assert that a press lands a file a decoder can read, and a skip when the encoder is
// missing would turn exactly that assertion into a silent pass.
function makeSeedClip() {
  const seedDir = mkdtempSync(join(tmpdir(), "shadowplay-e2e-seed-"));
  const seed = join(seedDir, "seed.mp4");
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
    rmSync(seedDir, { recursive: true, force: true });
  }
}

const SEED = makeSeedClip();

// One sandbox PER ARM.
//
// They used to share a single directory, which meant every arm's expected clip name
// depended on the arms above it having run first: arm 2 expected 0001..0003 only
// because arm 1 had already taken 0000. That coupling is what let an arm assert a
// name it had not itself earned. Each arm now owns its directory, so its enumeration
// is its own and an arm can be read, run or broken on its own.
function sandbox() {
  const dir = mkdtempSync(join(tmpdir(), "shadowplay-e2e-"));
  // `dir` is wired in so pathFor()/pathOf() resolve to a FULL path. The delivery gate
  // shells out to ffprobe and ffmpeg with the source path as an argument, so a bare
  // name is not a path it can open -- it is a name relative to whatever cwd the host
  // happened to be in.
  const writer = new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir });
  const path = new SavePath({ writer });
  const ring = new ReplayRing({ minutes: 1, fps: 1, gopSize: 10, savePath: path });
  const hk = new HotkeyRouter({ ring, debounceMs: 0 });
  return { dir, path, ring, hk };
}

const dir = mkdtempSync(join(tmpdir(), "shadowplay-e2e-"));
try {
  await t("f9 through the barrel lands a real file on a real disk", async () => {
    const box = sandbox();
    try {
      // WHAT THIS ARM ASSERTED BEFORE, AND WHY THAT WAS THE DEFECT.
      //
      // It drove the whole chain through a press that saved nothing and asserted the
      // refusal: `/^instant replay refused: could not measure delivery of /`. So an arm
      // NAMED "lands a real file on a real disk" could only ever pass while the product
      // wrote 0-byte files -- the assertion and the arm's own name disagreed, and the
      // name was the correct one. It also asserted the error carried
      // join(dir, "0000.mp4"), which is a property of the OLD ordering: save() reserved
      // the name and wrote nothing before the gate ran. That ordering is exactly what
      // this change removes, so that expectation described a file that should no longer
      // exist.
      //
      // The arm now holds the ring with a real clip and asserts the save it promised.
      box.ring.push(SEED, { frames: 60, keyframe: true });

      const action = await box.hk.press("f9", 1000);
      assert.equal(action.action, "instant-replay",
        "a press with real bytes must reach the ring and not be reported as a failure");
      assert.equal(action.clip.name, "0000.mp4", "the first press takes the first name");

      // The load-bearing check, which the old arm had no way to make: CONTENT.
      const landed = join(box.dir, "0000.mp4");
      assert.ok(readdirSync(box.dir).includes("0000.mp4"), "the file is not on disk");
      assert.equal(statSync(landed).size, SEED.byteLength,
        `the clip must carry its encoded bytes, not a reservation: got ${statSync(landed).size} of ${SEED.byteLength}`);
      // And the gate really decoded it. A verdict cannot exist without ffprobe and
      // ffmpeg having read the file, so this is proof the bytes were playable.
      assert.equal(typeof action.clip.verdict.longestUniqueRun, "number");
      assert.equal(action.clip.verdict.contentSufficientToCoverClock, true);
      assert.equal(action.clip.path, landed, "the returned path must be the real one");
      assert.deepEqual(box.path.written(), ["0000.mp4"]);
    } finally {
      rmSync(box.dir, { recursive: true, force: true });
    }
  });

  await t("a press with no lawful cut refuses and leaves NOTHING on disk", async () => {
    const box = sandbox();
    try {
      // The refusal coverage from the old arm, kept because a refusal must stay loud --
      // but pointed at the condition that now causes it. The ring holds nothing, so
      // there is no cut that starts on a keyframe, and instantReplay() refuses BEFORE
      // it reserves a name.
      //
      // This is strictly stronger than what it replaces. The old arm asserted that a
      // refusal NAMED a path; it could not assert that the file was absent, because a
      // file WAS there -- a 0-byte reservation created by the very defect being fixed.
      // "Nothing on disk" is the property the product actually needs, because a
      // consumer enumerates that directory and plays whatever it finds in it.
      // This arm used to run against an EMPTY ring, and the mutation pass showed why
      // that is too easy: a writer that cut anyway would still be refused, because an
      // empty ring has nothing to cut. The ring here therefore holds REAL CONTENT that
      // simply does not begin on an IDR -- which is the case the product actually has
      // to refuse, and the one a "just cut from the oldest segment anyway" shortcut
      // gets wrong.
      box.ring.push(SEED, { frames: 60, keyframe: false });
      assert.ok(box.ring.heldBytes() > 0, "the ring must really be holding content");

      const err = await box.hk.press("f9", 1000).then(() => null, (e) => e);
      assert.ok(err instanceof Error, "a press with nothing lawful to cut must refuse, never report success");
      assert.match(err.message, /instant replay refused/);
      assert.match(err.message, /none of them begins on an IDR/);
      assert.deepEqual(readdirSync(box.dir), [],
        "a refused cut must not leave a 0-byte clip a consumer would find and try to play");
      assert.deepEqual(box.path.written(), [], "nothing may be recorded as written");
    } finally {
      rmSync(box.dir, { recursive: true, force: true });
    }
  });

  await t("repeated presses produce increasing, sortable names on disk", async () => {
    const box = sandbox();
    try {
      // Before this change the presses were expected to REFUSE, and the arm asserted
      // the names they had consumed on the way to refusing -- a file that existed only
      // as an empty reservation. Now each press is a real save with real content.
      box.ring.push(SEED, { frames: 60, keyframe: true });
      for (const tms of [1000, 2000, 3000]) {
        const action = await box.hk.press("f9", tms);
        assert.equal(action.action, "instant-replay",
          `the press at ${tms}ms must save, not refuse`);
      }
      const names = box.path.written();
      assert.deepEqual(names, ["0000.mp4", "0001.mp4", "0002.mp4"]);
      for (const n of names) {
        assert.equal(box.path.pathOf(n), join(box.dir, n),
          "an issued name must resolve to a full path");
        assert.equal(statSync(join(box.dir, n)).size, SEED.byteLength,
          `${n} must carry the clip, not a reservation`);
      }
      const onDisk = readdirSync(box.dir).sort();
      assert.deepEqual(onDisk, [...onDisk].sort(), "disk listing must sort stably");
      assert.deepEqual(onDisk, ["0000.mp4", "0001.mp4", "0002.mp4"]);
    } finally {
      rmSync(box.dir, { recursive: true, force: true });
    }
  });

  await t("encoding happens once; the save-time op is a remux, never a re-encode", async () => {
    const enc = new Encoder({ gopSize: 10 });
    for (let i = 0; i < 30; i++) enc.encodeFrame(i, 100);
    const before = enc.encodeCount();
    const cut = backToNearestIdr(25, 10, 15);
    assert.equal(cut, 10, "25 back 15 is 10, and 10 is an IDR at gopSize 10");
    const out = enc.remux(cut);
    assert.equal(enc.encodeCount(), before, "remux must not encode anything");
    assert.equal(out.startType, 0);
    assert.equal(out.frames, 20, "frames 10..29 inclusive");
    assert.equal(out.bytes, 2000);
    assert.deepEqual(enc.operations().filter((o) => o === "remux").length, 1);
  });

  await t("a remux that would not start on an IDR is refused", async () => {
    const enc = new Encoder({ gopSize: 10 });
    for (let i = 0; i < 30; i++) enc.encodeFrame(i, 100);
    assert.throws(() => enc.remux(21), RangeError);
  });

  await t("the whole chain runs with the overlay disabled", async () => {
    const box = sandbox();
    try {
      // Before this change the arm asserted a refusal here too, on the reasoning that
      // "what stops it is the delivery gate". It conflated two different questions: it
      // was reading the gate's failure as evidence about the OVERLAY. The arm's actual
      // claim is that the overlay is a VIEW and disabling it must not disable capture --
      // which is only demonstrated by a capture that SUCCEEDS with the overlay off.
      box.hk.setOverlay(false);
      box.ring.push(SEED, { frames: 60, keyframe: true });

      const action = await box.hk.press("f9", 1000);
      assert.equal(box.hk.overlayOn, false, "the overlay really is off for this press");
      assert.equal(action.action, "instant-replay",
        "with the overlay off the press must still reach the ring AND save");
      assert.deepEqual(box.path.written(), ["0000.mp4"],
        "the disabled overlay must not block the writer");
      assert.equal(statSync(join(box.dir, "0000.mp4")).size, SEED.byteLength,
        "the clip saved with the overlay off must still carry its bytes");
    } finally {
      rmSync(box.dir, { recursive: true, force: true });
    }
  });

  // THE ARM THAT WAS MISSING. Every arm above builds its own object graph from leaf
  // classes -- ClipWriter, SavePath, ReplayRing, HotkeyRouter -- assembled by hand in
  // sandbox(). They prove each part and the way those parts were wired BY THE TEST.
  //
  // They never call composeShadowplay, which is the code a real caller enters. Measured
  // 2026-10-10T23:31:56Z: `Select-String composeShadowplay` over POP=13 suites returned
  // 0 call sites. So a wiring bug inside the composition root -- a directory not
  // threaded through, a ring built with the wrong minutes budget, a router wired to the
  // wrong writer -- would leave every arm above green.
  //
  // This arm enters through the public root and asserts the clip lands there. It is the
  // difference between "the parts work" and "the assembled product works".
  await t("the composition root wires a press through to a real file", async () => {
    const rootDir = mkdtempSync(join(tmpdir(), "shadowplay-root-"));
    try {
      // The real entry point, with only a directory injected. Everything else is the
      // product's own wiring.
      const app = composeShadowplay({ dir: rootDir });
      assert.ok(app && app.ring && app.hotkeys,
        "composeShadowplay must return a usable product, not a partial graph");

      app.ring.push(SEED, { frames: 60, keyframe: true });
      const action = await app.hotkeys.press("f9", 1000);

      // The three conditions _rootdrive2.mjs established, asserted permanently here:
      // the press did not refuse, bytes are on a real disk, and the gate read the file.
      assert.equal(action.action, "instant-replay",
        `a press through the root must save, not refuse: ${JSON.stringify(action.clip && action.clip.error)}`);
      assert.equal(action.clip.name, "0000.mp4",
        "the first press through the root takes the first name");

      const landed = join(rootDir, "0000.mp4");
      assert.ok(readdirSync(rootDir).includes("0000.mp4"),
        "the composition root must land the clip in the directory it was given");
      assert.equal(statSync(landed).size, SEED.byteLength,
        `the root's clip must carry its encoded bytes, not a reservation: got ${statSync(landed).size} of ${SEED.byteLength}`);

      // A verdict object can only exist if ffprobe and ffmpeg read the landed file, so
      // this is the proof the bytes are playable rather than merely present.
      assert.equal(typeof action.clip.verdict.longestUniqueRun, "number",
        "the gate must have measured the clip the root wrote");
      assert.equal(action.clip.verdict.contentSufficientToCoverClock, true);
      assert.equal(action.clip.path, landed, "the returned path must be the real one");
    } finally {
      rmSync(rootDir, { recursive: true, force: true });
    }
  });
} finally {
  rmSync(dir, { recursive: true, force: true });
}

console.log(`RESULT ${passed} passed, ${failed} failed`);
// process.exitCode, NOT process.exit(). Under `node --test` this file runs as a child
// process whose stdout is a PIPE, and writes to a pipe are async. process.exit() kills
// the process without draining that pipe, so the RESULT line above -- the only record
// of what actually asserted -- could be lost while the exit code still said "green".
// Measured fix, 2026-10-10: setting exitCode lets Node flush the pipe at natural exit.
// The code is identical in intent: 0 when nothing failed, 1 the moment one did.
process.exitCode = failed === 0 ? 0 : 1;