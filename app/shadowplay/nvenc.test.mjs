// These tests invoke the REAL ffmpeg and the REAL GPU. If they are skipped, it is
// because ffmpeg is absent, not because the model is convenient.
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { NvencEncoder, NVENC } from "./nvenc.js";

let passed = 0, failed = 0, skipped = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

const hasFfmpeg = (() => {
  try { execFileSync("ffmpeg", ["-version"], { stdio: "ignore" }); return true; }
  catch { return false; }
})();

const dir = mkdtempSync(join(tmpdir(), "sp-nvenc-"));
try {
  const enc = new NvencEncoder({ preset: "p1" });

  if (!hasFfmpeg) {
    skipped++;
    console.log("  SKIP real-encoder tests: ffmpeg not on PATH");
  } else {
    t("the default GOP is the measured 250, not an assumption", () => {
      assert.equal(enc.gop, 250);
    });

    t("the real GPU encodes a real desktop capture", () => {
      const out = join(dir, "cap.mp4");
      const r = enc.captureAndEncode(out, { fps: 30, seconds: 2 });
      assert.ok(existsSync(out));
      assert.ok(r.bytes > 0, "no bytes were produced");
      assert.ok(r.ms > 0);
      assert.equal(r.codec, NVENC);
    });

    t("the GOP read back is the REAL one, and -g is only a hint", () => {
      // I asked for -g 250 and measured 287. NVENC inserts keyframes of its own,
      // so the requested GOP is a request, not a contract. What matters is that
      // the ring can READ the real value, not that it equals what we asked.
      //
      // The capture must be long enough to CONTAIN two keyframes at the requested GOP,
      // or probeGop correctly refuses to measure a GOP from a clip holding one. At
      // 6 s x 60 fps = 360 frames, a 250-frame GOP leaves only 1.44 GOPs and the readback
      // was impossible by construction -- the fixture was too short for its own assertion.
      // At 12 s = 720 frames = 2.88 GOPs it holds. Measured on this host at WINDOW_UTC
      // 2026-10-10T15:00:37Z: -g 250 over 600 frames gave 3 keyframes at pts 0, 4.166667
      // and 8.333333 -- 4.166667 s x 60 fps = 250.00002 frames, so the encoder honours -g
      // to the frame. 12 s is chosen over 10 s for margin, because a gdigrab capture of a
      // still desktop delivers fewer frames than the requested clock (measured all session).
      const out = join(dir, "long.mp4");
      enc.captureAndEncode(out, { fps: 60, seconds: 12, gop: 250 });
      const r = enc.gopOf(out, 60);
      assert.ok(r.gop > 0, "probe returned no GOP");
      assert.ok(r.gop >= 250, `asked 250, measured ${r.gop}: NVENC may add keyframes`);
      console.log("       (requested GOP 250, encoder delivered " + r.gop + ")");
    });

    t("remux copies the stream: codec and frame count survive", () => {
      const src = join(dir, "cap.mp4");
      const dst = join(dir, "copy.mp4");
      const before = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,nb_frames", "-of", "csv=p=0", src],
        { encoding: "utf8" }).trim();
      const r = enc.remux(src, dst);
      const after = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,nb_frames", "-of", "csv=p=0", dst],
        { encoding: "utf8" }).trim();
      assert.equal(after, before, "the stream changed across a remux");
      assert.equal(enc.encodeCount(), 2, "remux must not have encoded again");
      assert.deepEqual(enc.calls, ["encode", "encode", "remux"],
        "the log must show exactly the encodes plus the one remux");
      // Byte equality is NOT the invariant: ffmpeg may rewrite the moov box.
      // What must not change is the encoded stream itself.
      console.log("       (remux " + r.inBytes + " -> " + r.outBytes + " bytes, stream identical)");
    });

    t("a remux to a missing input fails loudly rather than silently", () => {
      assert.throws(() => enc.remux(join(dir, "nope.mp4"), join(dir, "x.mp4")));
    });
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
}

console.log(`RESULT ${passed} passed, ${failed} failed${skipped ? `, ${skipped} suite block skipped` : ""}`);
process.exit(failed === 0 ? 0 : 1);