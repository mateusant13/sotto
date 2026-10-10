// The GOP is a property of the encoded stream, not a constant in our code.
// MEASURED on this host, NVENC h264_nvenc -preset p1: keyframes at pts
// 0.000000 and 4.166667. At 60 fps that is frame 250, so the encoder chose
// GOP=250 -- not the 60 that ReplayRing used to assume. The ring must read it.
import { execFileSync } from "node:child_process";

export const DEFAULT_FPS = 60;

// ffprobe is the measurement; this function is only a parser of its output.
export function parseKeyframes(ptsLines) {
  return ptsLines
    // A blank line must be dropped BEFORE Number(), because Number("") is 0 and
    // 0 is finite. Without this, ffprobe's trailing newline becomes a phantom
    // keyframe at t=0 and the measured GOP collapses to 0. Caught by the suite.
    .filter((s) => String(s).trim().length > 0)
    // A frame that carries side data makes `csv=p=0` print a trailing comma
    // with nothing after it. libx264 writes an x264 SEI on its first IDR, so
    // that frame's line is `0.000000,` while every later line is bare.
    // Number("0.000000,") is NaN, so the finite-filter below used to DISCARD
    // THE REAL FIRST KEYFRAME and return the second one as pts[0].
    // MEASURED WINDOW_UTC 2026-10-10T18:52:55Z, raw ffprobe on this host:
    //   "0.000000,\r\n1.000000\r\n2.000000\r\n"
    //   before: firstKeyframeSec(libx264 clip) = 1  (true first is 0)
    //           assertStartsOnKeyframe THREW ERR_CLIP_NOT_KEYFRAMED
    //   after:  firstKeyframeSec(libx264 clip) = 0
    .map((s) => String(s).trim().replace(/,+$/, "").trim())
    // The blank-line guard above runs BEFORE the comma strip, so a line that is
    // only "," is not blank but strips to "". Number("") is 0 and 0 is finite --
    // the exact phantom keyframe the first guard exists to prevent. Re-checked
    // here, after the strip, where the empty string can actually be produced.
    .filter((s) => s.length > 0)
    .map(Number)
    .filter((n) => Number.isFinite(n))
    .sort((a, b) => a - b);
}

// The GOP is the gap between consecutive keyframes, in frames.
export function gopFromKeyframes(ptsSeconds, fps = DEFAULT_FPS) {
  const pts = parseKeyframes(ptsSeconds);
  if (pts.length < 2) {
    throw new RangeError(
      `need at least 2 keyframes to measure a GOP, got ${pts.length}`
    );
  }
  const gaps = pts.slice(1).map((t, i) => Math.round((t - pts[i]) * fps));
  const uniq = [...new Set(gaps)].sort((a, b) => a - b);
  if (uniq.length > 1) {
    // variable GOP is legal; the smallest is the safe cut granularity
    return { gop: uniq[0], variable: true, gaps: uniq };
  }
  return { gop: uniq[0], variable: false, gaps: uniq };
}

export function probeGop(file, fps = DEFAULT_FPS) {
  const out = execFileSync("ffprobe", [
    "-v", "error", "-select_streams", "v:0",
    "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
    "-of", "csv=p=0", file,
  ], { encoding: "utf8" });
  return gopFromKeyframes(out.split("\n"), fps);
}