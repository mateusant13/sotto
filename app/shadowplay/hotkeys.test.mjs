import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { HotkeyRouter, DEFAULT_DEBOUNCE_MS } from "./hotkeys.js";
import { ReplayRing } from "./replay-ring.js";
import { ClipWriter } from "./clip-writer.js";
import { SavePath } from "./save-path.js";
import { SessionClock } from "./session-clock.js";
import { CAPTURE_FPS, KEYFRAME_TOLERANCE_SEC } from "./nvenc.js";

let passed = 0, failed = 0;
// ASYNC runner: press() and instantReplay() are async (the delivery gate measures with
// ffprobe), so the runner must await the body or it will report a Promise as a result.
async function t(name, fn) {
  try { await fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

// A rejection that escapes every runner is a failure of the SUITE, not of one
// arm, and the default Node handler kills the process before the RESULT line is
// printed -- which is how the baseline run ended with a stack trace and no
// verdict at all. It is caught here so it is REPORTED as a failed arm instead.
// The exit code below is still driven by the arms, never by this handler.
process.on("unhandledRejection", (err) => {
  failed++;
  console.log("  FAIL unhandled rejection escaped the runner :: " + (err?.message ?? String(err)));
});

// -- the real fixture ------------------------------------------------------
//
// The press path is NOT a model: pressing f9 runs the delivery gate, which shells
// out to ffprobe and ffmpeg and refuses a clip that cannot cover its clock. So
// these arms need a REAL clip that the ring can lawfully cut, or every f9
// assertion would be measuring the refusal path instead of the behaviour under
// test. MEASURED WINDOW_UTC 2026-10-10T19:44Z: a lavfi testsrc clip at rate 30
// for 2s encodes to 60 distinct contiguous frames starting on an IDR at pts
// 0.000000, which clears the gate (which needs longestUniqueRun >= ring fps).
//
// Encoded ONCE and reused: the fixture is a constant of the suite, and re-encoding
// it per arm would make ten ffmpeg invocations out of what is one fact.
const FIXTURE = join(mkdtempSync(join(tmpdir(), "hk-fixture-")), "fixture.mp4");
execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
  "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30", "-t", "2",
  "-c:v", "h264_nvenc", "-preset", "p1", "-pix_fmt", "yuv420p", "-g", "60",
  FIXTURE], { stdio: ["ignore", "pipe", "pipe"] });
const FIXTURE_BYTES = readFileSync(FIXTURE);

// A fresh, empty clips directory per arm. Fresh matters: the writer's SessionClock
// starts at 0 and the claim is O_EXCL, so a SHARED directory would hand the second
// arm 0001.mp4 and the first arm's assertion would pass for the wrong reason.
const madeDirs = [];
function freshDir() {
  const d = mkdtempSync(join(tmpdir(), "hk-clips-"));
  madeDirs.push(d);
  return d;
}

// A REAL composed ring over a REAL directory, holding the real fixture.
// fps is CAPTURE_FPS (30), the rate the fixture and the encoder actually run at.
// The ReplayRing class default is 60, and at 60 the gate demands 60 contiguous
// distinct frames, which this 2s@30 fixture cannot supply -- a ring that lied
// about its rate would refuse correct clips.
function ringOver(dir) {
  const writer = new ClipWriter({ exists: (n) => existsSync(join(dir, n)), dir });
  const savePath = new SavePath({ writer });
  const ring = new ReplayRing({ minutes: 10, fps: CAPTURE_FPS, savePath });
  ring.push(FIXTURE_BYTES, { frames: 60, keyframe: true });
  return { ring, savePath, writer };
}

process.on("exit", () => {
  for (const d of madeDirs) { try { rmSync(d, { recursive: true, force: true }); } catch {} }
  try { rmSync(join(FIXTURE, ".."), { recursive: true, force: true }); } catch {}
});

// THE load-bearing rule: the overlay is a view. Disabling it must not stop capture.
await t("hotkeys still fire with the overlay disabled", async () => {
  const { ring } = ringOver(freshDir());
  const h = new HotkeyRouter({ ring });
  h.setOverlay(false);
  assert.equal(h.overlayOn, false);
  const r = await h.press("f9", 1000);
  assert.equal(r.action, "instant-replay");
  // instantReplay() answers { name, path, verdict } -- the clip's IDENTITY is in
  // .name, and in a fresh directory the first clip is 0000.mp4. Asserting on the
  // whole object would be weaker; asserting on .name keeps the original claim
  // (this press produced the first clip) against the real return shape.
  assert.equal(r.clip.name, "0000.mp4");
  assert.ok(existsSync(r.clip.path), "the clip named by the press must exist on disk");
});

await t("the clip written with the overlay off is identical to the overlay on", async () => {
  const onDir = freshDir(), offDir = freshDir();
  const on = new HotkeyRouter({ ring: ringOver(onDir).ring });
  const offRing = ringOver(offDir);
  const off = new HotkeyRouter({ ring: offRing.ring });
  off.setOverlay(false);
  await on.press("f9", 1000);
  await off.press("f9", 1000);
  assert.equal(on.press === undefined, false); // sanity: method exists
  assert.equal(off.history()[0].clip.name, on.history()[0].clip.name);
  // STRONGER than the name comparison above: the overlay must not change a BYTE
  // of what lands on disk, which is the property the two documents actually ask
  // for. Comparing two names that are both "0000.mp4" cannot tell a difference
  // in content; this can.
  const onBytes = readFileSync(on.history()[0].clip.path);
  const offBytes = readFileSync(off.history()[0].clip.path);
  assert.equal(onBytes.byteLength, offBytes.byteLength);
  assert.ok(onBytes.equals(offBytes), "overlay state must not alter one byte of the clip");
});

await t("a repeat inside the debounce window is swallowed", async () => {
  const h = new HotkeyRouter({ ring: ringOver(freshDir()).ring, debounceMs: 250 });
  // (await h.press(...)).action -- the parenthesis is load-bearing. As written
  // before this change it was `await h.press(...).action`, which reads `.action`
  // off the PROMISE (undefined) and compares that to a string, so the assertion
  // failed no matter what the router did. Three arms had this shape.
  assert.equal((await h.press("f9", 1000)).action, "instant-replay");
  assert.equal((await h.press("f9", 1100)).action, "debounced");
  assert.equal((await h.press("f9", 1249)).action, "debounced");
  assert.equal((await h.press("f9", 1250)).action, "instant-replay");
});

await t("debouncing is per-key, not global", async () => {
  const h = new HotkeyRouter({ ring: ringOver(freshDir()).ring, debounceMs: 250 });
  await h.press("f9", 1000);
  assert.equal((await h.press("f10", 1010)).action, "toggle-recording");
});

await t("debouncing is separate per key over repeated presses", async () => {
  const { ring } = ringOver(freshDir());
  const h = new HotkeyRouter({ ring, debounceMs: 250 });
  await h.press("f9", 1000);      // fires
  await h.press("f9", 1100);      // inside the window -> debounced
  await h.press("f9", 1400);      // 400ms later -> fires again
  const n = h.history().filter((e) => e.action === "debounced").length;
  assert.equal(n, 1);
  assert.equal(h.history().filter((e) => e.action === "instant-replay").length, 2);
});

await t("an unbound key is reported as unbound, not silently ignored", async () => {
  const h = new HotkeyRouter();
  assert.equal((await h.press("f1", 1000)).action, "unbound");
});

await t("the default debounce is 250 ms", async () => {
  assert.equal(DEFAULT_DEBOUNCE_MS, 250);
});

await t("the history records overlay state without gating on it", async () => {
  const h = new HotkeyRouter();
  h.setOverlay(false);
  await h.press("f10", 5000);
  assert.equal(h.history()[0].overlayOn, false);
  assert.equal(h.history()[0].action, "toggle-recording");
});

await t("an empty hotkey is refused", async () => {
  const h = new HotkeyRouter();
  // press() is async, so an invalid key surfaces as a REJECTION, not a synchronous
  // throw. assert.throws cannot observe it -- it needs assert.rejects.
  await assert.rejects(() => h.press("", 0), TypeError);
});

await t("a negative debounce is refused", async () => {
  assert.throws(() => new HotkeyRouter({ debounceMs: -1 }), RangeError);
});

// -- the failure path ------------------------------------------------------
//
// A refusal must be BOTH recorded and surfaced (hotkeys.js). These arms exist
// because that decision is the only thing between "the user pressed a key and
// nothing happened" and a silent failure nobody can diagnose.

await t("a refusal is RECORDED, not just thrown", async () => {
  const dir = freshDir();
  const { savePath } = ringOver(dir);
  // A ring holding nothing: the cut cannot happen, so the press must refuse.
  const empty = new ReplayRing({ minutes: 10, fps: CAPTURE_FPS, savePath });
  const seen = [];
  const h = new HotkeyRouter({ ring: empty, onRefusal: (e, ctx) => { seen.push([e, ctx]); savePath.recordFailure(ctx.route, e); } });
  await assert.rejects(() => h.press("f9", 1000));
  assert.equal(seen.length, 1, "the recorder must be told exactly once");
  assert.equal(seen[0][1].route, "instant-replay");
  assert.equal(savePath.blocked(), 1, "a refused save must be visible in blocked()");
  assert.equal(existsSync(join(dir, "0000.mp4")), false, "a refused press must leave no clip behind");
});

await t("a refusal is SURFACED to the caller, not swallowed", async () => {
  const { savePath } = ringOver(freshDir());
  const empty = new ReplayRing({ minutes: 10, fps: CAPTURE_FPS, savePath });
  const h = new HotkeyRouter({ ring: empty, onRefusal: () => {} });
  // Recording must not turn the refusal into a success-shaped return value.
  await assert.rejects(() => h.press("f9", 1000), (err) => {
    assert.ok(err instanceof Error);
    assert.match(err.message, /IDR|instant replay refused/i);
    return true;
  });
});

await t("a broken recorder cannot mask the real refusal", async () => {
  const { savePath } = ringOver(freshDir());
  const empty = new ReplayRing({ minutes: 10, fps: CAPTURE_FPS, savePath });
  const h = new HotkeyRouter({
    ring: empty,
    onRefusal: () => { throw new Error("the recorder itself is broken"); },
  });
  // The caller must receive the RING's refusal, not the recorder's bug.
  await assert.rejects(() => h.press("f9", 1000), (err) => {
    assert.doesNotMatch(err.message, /recorder itself is broken/);
    return true;
  });
});

await t("a router with no recorder still surfaces the refusal", async () => {
  const h = new HotkeyRouter();   // default ring: nothing captured
  await assert.rejects(() => h.press("f9", 1000));
});

console.log(`RESULT ${passed} passed, ${failed} failed`);
// process.exitCode, NOT process.exit(). Under `node --test` this file runs as a child
// process whose stdout is a PIPE, and writes to a pipe are async. process.exit() kills the
// process without draining that pipe, so the RESULT line above -- the only record
// of what actually asserted -- can be lost while the exit code still says "green".
process.exitCode = failed === 0 ? 0 : 1;