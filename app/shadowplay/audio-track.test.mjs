import assert from "node:assert/strict";
import { AudioTrack } from "./audio-track.js";
import { SavePath, ClipWriter, SessionClock, HEADROOM_DB, mix } from "./index.js";
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

const indep = [{ clock: "a", amplitude: 0.5 }, { clock: "b", amplitude: 0.5 }];
const same  = [{ clock: "a", amplitude: 0.5 }, { clock: "a", amplitude: 0.5 }];

t("independent clocks are uncorrelated; a shared clock is correlated", () => {
  assert.equal(new AudioTrack({ sources: indep }).correlated(), false);
  assert.equal(new AudioTrack({ sources: same }).correlated(), true);
});

t("the correlation decision changes the ungained level", () => {
  // mix() is the raw sum; render() then applies gain. The gap lives in mix().
  const u = mix([0.5, 0.5], { correlated: false });
  const c = mix([0.5, 0.5], { correlated: true });
  assert.notEqual(u.linear, c.linear, "the two cases must not collapse");
  assert.ok(Math.abs((c.dbfs - u.dbfs) - HEADROOM_DB) < 0.05,
    `gap ${(c.dbfs - u.dbfs).toFixed(3)} is not the documented headroom`);
});

t("headroom equalises the two cases after gain -- that is its whole job", () => {
  const u = new AudioTrack({ sources: indep }).render();
  const c = new AudioTrack({ sources: same }).render();
  assert.ok(Math.abs(u.dbfs - c.dbfs) < 0.01,
    `after gain the two cases must match, got ${u.dbfs.toFixed(3)} vs ${c.dbfs.toFixed(3)}`);
  assert.ok(c.unclipped && u.unclipped);
});

t("a correlated render stays unclipped once headroom is applied", () => {
  const c = new AudioTrack({ sources: same }).render();
  assert.ok(c.unclipped, "the correlated case clipped despite the headroom");
  assert.ok(c.dbfs < 0);
});

t("nothing is ever reported as unclipped while sitting above 0 dBFS", () => {
  for (const sources of [indep, same]) {
    const r = new AudioTrack({ sources }).render(4);
    if (r.dbfs >= 0) assert.equal(r.unclipped, false, "clipped but reported clean");
  }
});

t("audio goes through the same one writer as video", () => {
  // TWO THINGS WERE WRONG WITH THE OLD ARM, and both were the defect.
  //
  // 1. It built `new ClipWriter({ exists: () => false })` with no `dir`. That writer
  //    can reserve a NAME but has nowhere to put bytes, so it could only ever be asked
  //    to produce the 0-byte placeholder -- which is why the payload is now refused
  //    rather than written. The writer is given a real directory here.
  // 2. It called `a.attach(4800)` -- a frame count. There is no audio behind the
  //    number 4800, and save() refuses a number because a length is not content. The
  //    arm now supplies the audio itself.
  //
  // And it asserts the CONTENT, which the name comparison it replaced could not: a
  // 0-byte file called 0000.mp4 passes every name assertion there was.
  const dir = mkdtempSync(join(tmpdir(), "shadowplay-at-"));
  try {
    const w = new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir });
    const p = new SavePath({ writer: w });
    const a = new AudioTrack({ sources: indep, savePath: p });

    const audio = Buffer.from("not really audio, but bytes that exist", "utf8");
    assert.equal(a.attach(4800, audio), "0000.mp4");
    assert.equal(a.attach(4800, audio), "0001.mp4");

    for (const n of ["0000.mp4", "0001.mp4"]) {
      assert.ok(readdirSync(dir).includes(n), `${n} is not on disk`);
      assert.equal(statSync(join(dir, n)).size, audio.byteLength,
        `${n} must carry the audio, not a reservation`);
    }
    assert.equal(readFileSync(join(dir, "0000.mp4"), "utf8"), audio.toString("utf8"),
      "the bytes on disk must be the audio handed in, byte for byte");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

t("a frame count with no audio is refused rather than written", () => {
  // The arm that replaced the number-passing one. A caller who still believes a count
  // is enough must be told so HERE, at the audio boundary, rather than discovering it
  // one layer deeper inside save() with a message about clips.
  const dir = mkdtempSync(join(tmpdir(), "shadowplay-at-"));
  try {
    const w = new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir });
    const a = new AudioTrack({ sources: indep, savePath: new SavePath({ writer: w }) });
    assert.throws(() => a.attach(4800), TypeError, "a count alone must be refused");
    assert.throws(() => a.attach(4800, null), TypeError);
    assert.deepEqual(readdirSync(dir), [], "a refused attach must not create a file");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

t("rate and channels are reported as given", () => {
  const a = new AudioTrack({ rate: 44100, channels: 1, sources: indep });
  assert.equal(a.rate, 44100);
  assert.equal(a.channels, 1);
});

t("a track with no sources is refused", () => {
  assert.throws(() => new AudioTrack({ sources: [] }), RangeError);
});

t("a non-positive rate or channel count is refused", () => {
  assert.throws(() => new AudioTrack({ sources: indep, rate: 0 }), RangeError);
  assert.throws(() => new AudioTrack({ sources: indep, channels: 0 }), RangeError);
});

t("attaching zero frames is refused", () => {
  const a = new AudioTrack({ sources: indep });
  assert.throws(() => a.attach(0), RangeError);
});

console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
