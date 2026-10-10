// Proof that the IDR invariant is real and that the gate can say NO.
// POPULATION = 1 real encode, 1 real remux, 3 negative arms.
// WINDOW = the stdout below. Every number here comes from ffprobe on a real file.
import { execFileSync } from "node:child_process";
import { statSync, writeFileSync, rmSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { NvencEncoder, ClipNotKeyframed } from "./nvenc.js";

const D = join(tmpdir(), "idr-proof");
mkdirSync(D, { recursive: true });
const enc = join(D, "enc.mp4");
const clip = join(D, "clip.mp4");
const cut = join(D, "midgop.mp4");
const junk = join(D, "notavideo.txt");

const say = (s) => process.stdout.write(s + "\n");
let fails = 0;
const expect = (name, cond, detail) => {
  say(`${cond ? "PASS" : "FAIL"}  ${name}${detail ? "  " + detail : ""}`);
  if (!cond) fails++;
};

say("WINDOW_UTC: " + new Date().toISOString().replace(/\.\d+Z$/, "Z"));

// ---- ARM 1: real encode, real remux, invariant enforced on real bytes -------
let firstIdr = null;
try {
  const e = new NvencEncoder({ preset: "p1", gop: 30 });
  const r = e.captureAndEncode(enc, { seconds: 2, fps: 30, gop: 30 });
  expect("encode produced bytes", r.bytes > 0, `${r.bytes} B in ${r.ms.toFixed(0)} ms`);
  const m = e.remux(enc, clip);
  firstIdr = m.firstIdr;
  expect("remux returned firstIdr", typeof firstIdr === "number", `pts=${firstIdr}`);
  expect("first IDR within tolerance", Math.abs(firstIdr) <= 0.5, `${firstIdr}s`);
  expect("clip on disk is non-empty", statSync(clip).size > 0, `${statSync(clip).size} B`);
} catch (err) {
  expect("arm1 happy path", false, err.message);
}

// ---- ARM 2 (NEG): mid-GOP cut with -c copy must be refused ----------------
// Cutting at 1.0s inside a GOP=30 (1s) stream with stream copy must not yield a
// clip that starts on an IDR. If the file happens to be keyframed anyway the
// arm is reported as INCONCLUSIVE, never as a pass.
let cutFirst = "n/a";
try {
  execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
    "-i", enc, "-ss", "1.0", "-c", "copy", cut], { stdio: ["ignore", "pipe", "pipe"] });
} catch (e) { say(`note: mid-GOP cut command failed: ${e.message}`); }
try {
  const e2 = new NvencEncoder();
  cutFirst = e2.firstKeyframeSec(cut);
  say(`midgop first keyframe pts = ${cutFirst}`);
} catch (e) { say(`note: midgop probe failed: ${e.message}`); }

if (typeof cutFirst === "number" && cutFirst > 1 / 60) {
  const e3 = new NvencEncoder();
  let threw = null;
  try { e3.assertStartsOnKeyframe(cut); } catch (err) { threw = err; }
  expect("NEG mid-GOP clip is REFUSED", threw instanceof ClipNotKeyframed,
    threw ? `code=${threw.code} detail=${threw.message}` : "did not throw");
} else {
  say(`FAIL arm2: expected a mid-GOP clip to start off an IDR, got pts=${cutFirst}`);
  fails++;
}

// ---- ARM 3 (NEG): zero-keyframe input must be refused, not silently passed --
writeFileSync(junk, "this is not a video\n");
const e4 = new NvencEncoder();
let junkErr = null;
try { e4.assertStartsOnKeyframe(junk); } catch (err) { junkErr = err; }
expect("NEG non-video file is REFUSED",
  junkErr instanceof ClipNotKeyframed, junkErr ? `code=${junkErr.code}` : "did not throw");

// ---- ARM 4 (NEG): the error carries a machine-readable code ---------------
expect("error code is stable", new ClipNotKeyframed("f", "d").code === "ERR_CLIP_NOT_KEYFRAMED");
expect("error name is stable", new ClipNotKeyframed("f", "d").name === "ClipNotKeyframed");

for (const f of [enc, clip, cut, junk]) { try { rmSync(f, { force: true }); } catch {} }
say(`FAILS: ${fails}`);
process.exit(fails === 0 ? 0 : 1);