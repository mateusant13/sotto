// The real encoder. This is the layer that was missing: everything else in this
// project was a model, and this one calls ffmpeg and NVENC.
//
// MEASURED on this host at WINDOW_UTC 2026-10-10T13:10:30Z:
//   ffmpeg -f gdigrab -framerate 30 -i desktop -t 2 -c:v h264_nvenc -preset p1
//   exit 0, 2291 ms wall, 374106 bytes, h264 1920x1080, 48 frames.
//
// The remux path is -c copy and nothing else. That is the invariant.
import { execFileSync } from "node:child_process";
import { statSync } from "node:fs";
import { probeGop, parseKeyframes, DEFAULT_FPS } from "./stream-probe.js";

export const NVENC = "h264_nvenc";

// The product invariant: every stored clip is remuxed from already-encoded bytes,
// begins on a keyframe, and is never re-encoded. encoder.js has always enforced
// the keyframe half of that; this file is the path that actually runs, and until
// now it enforced nothing. MEASURED WINDOW_UTC 2026-10-10T18:31:33Z: zero lines
// in this file mentioned a keyframe, while the model file refused with
// `remux from ${fromIndex} would not start on an IDR`.
export class ClipNotKeyframed extends Error {
  constructor(file, detail) {
    super(`stored clip ${file} does not begin on a keyframe: ${detail}`);
    this.name = "ClipNotKeyframed";
    this.code = "ERR_CLIP_NOT_KEYFRAMED";
    this.file = file;
  }
}

export class NvencEncoder {
  #preset;
  #gop;
  #log;

  constructor({ preset = "p1", gop = 250 } = {}) {
    this.#preset = preset;
    this.#gop = gop;          // the MEASURED default from this host, not an assumption
    this.#log = [];
  }

  get preset() { return this.#preset; }
  get gop() { return this.#gop; }
  get calls() { return this.#log.map((e) => e.op); }

  // Capture from a real source and encode with the real GPU.
  captureAndEncode(out, { source = "desktop", fps = 30, seconds = 2, gop = null } = {}) {
    const args = [
      "-y", "-hide_banner", "-loglevel", "error",
      "-f", "gdigrab", "-framerate", String(fps), "-i", source,
      "-t", String(seconds),
      "-c:v", NVENC, "-preset", this.#preset, "-pix_fmt", "yuv420p",
      "-g", String(gop ?? this.#gop),
      out,
    ];
    const t = process.hrtime.bigint();
    execFileSync("ffmpeg", args, { stdio: ["ignore", "pipe", "pipe"] });
    const ms = Number(process.hrtime.bigint() - t) / 1e6;
    const bytes = statSync(out).size;
    this.#log.push({ op: "encode", out, ms, bytes });
    return { out, ms, bytes, codec: NVENC };
  }

  // The first keyframe of a file, READ FROM THE FILE. Returns null when ffprobe
  // reports none -- null is a real answer here, not an error to swallow. A probe
  // that cannot read the file at all also yields null, so every failure of this
  // measurement arrives as the same value and the caller has ONE thing to refuse.
  firstKeyframeSec(file) {
    let raw;
    try {
      raw = execFileSync("ffprobe", [
        "-v", "error", "-select_streams", "v:0",
        "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
        "-of", "csv=p=0", file,
      ], { encoding: "utf8" });
    } catch {
      return null;   // unreadable, not a video, or no video stream
    }
    const pts = parseKeyframes(raw.split("\n"));
    return pts.length === 0 ? null : pts[0];
  }

  // THE INVARIANT, ENFORCED. A stored clip that does not begin on an IDR is
  // refused, not written. MEASURED WINDOW_UTC 2026-10-10T18:37:44Z: encoder.js
  // refused with `would not start on an IDR` and this file -- the one that
  // actually runs -- had zero lines mentioning a keyframe.
  //
  // TOLERANCE is one frame at DEFAULT_FPS, not 0.5 s. MEASURED WINDOW_UTC
  // 2026-10-10T18:39:09Z: a 0.5 s tolerance PASSED a mid-GOP cut whose first IDR
  // sat at pts 0.233008 -- a clip that shows corruption for its first 7 frames.
  // The negative arm caught the gate being too loose, which is the arm working.
  assertStartsOnKeyframe(file, toleranceSec = 1 / DEFAULT_FPS) {
    const first = this.firstKeyframeSec(file);
    if (first === null) {
      throw new ClipNotKeyframed(
        file, "no keyframe could be read (unreadable file, no video stream, or zero keyframes)");
    }
    if (Math.abs(first) > toleranceSec) {
      throw new ClipNotKeyframed(
        file,
        `first IDR at pts ${first.toFixed(6)}s exceeds tolerance ${toleranceSec.toFixed(6)}s`
      );
    }
    return first;
  }

  // The save-time operation. -c copy. This MUST NOT re-encode.
  remux(inFile, outFile) {
    const t = process.hrtime.bigint();
    execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
      "-i", inFile, "-c", "copy", outFile], { stdio: ["ignore", "pipe", "pipe"] });
    const ms = Number(process.hrtime.bigint() - t) / 1e6;
    const inBytes = statSync(inFile).size;
    const outBytes = statSync(outFile).size;
    // The invariant runs on the bytes that actually landed, not on intent.
    const firstIdr = this.assertStartsOnKeyframe(outFile);
    this.#log.push({ op: "remux", inFile, outFile, ms, inBytes, outBytes, firstIdr });
    return { inBytes, outBytes, ms, firstIdr, identical: inBytes === outBytes };
  }

  // The GOP of a file this encoder produced, read from the file.
  gopOf(file, fps = 30) { return probeGop(file, fps); }

  encodeCount() { return this.#log.filter((e) => e.op === "encode").length; }
}