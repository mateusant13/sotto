// The real encoder. This is the layer that was missing: everything else in this
// project was a model, and this one calls ffmpeg and NVENC.
//
// MEASURED on this host at WINDOW_UTC 2026-10-10T13:10:30Z:
//   ffmpeg -f gdigrab -framerate 30 -i desktop -t 2 -c:v h264_nvenc -preset p1
//   exit 0, 2291 ms wall, 374106 bytes, h264 1920x1080, 48 frames.
//
// The remux path is -c copy and nothing else. That is the invariant.
import { execFileSync } from "node:child_process";
import { statSync, renameSync, rmSync } from "node:fs";
import { dirname, basename, extname, join } from "node:path";
import { probeGop, parseKeyframes } from "./stream-probe.js";

export const NVENC = "h264_nvenc";

// The frame rate THIS MODULE actually captures at. It was three separate `30`
// literals -- captureAndEncode's default, gopOf's default, and the rate the
// proof encodes at -- which is why nothing could observe a drift in any of
// them. DEFAULT_FPS (60) in stream-probe.js describes a different default and
// is NOT the rate this encoder runs at.
export const CAPTURE_FPS = 30;

// ONE source of truth for the bound. This used to live as a literal inside a
// default parameter, where nothing could observe it: a drift to 0 or to 0.5 was
// invisible to every arm, because no arm ever read the value. idr-proof.mjs
// asserts it against 1/CAPTURE_FPS, which is what closes that hole.
//
// DEFECT FIX: it was derived as 1/DEFAULT_FPS = 1/60 s while this module
// captures at 30 fps, where one real frame is 0.033333 s. The bound was 2x
// too tight: it rejected valid clips. Derived from the rate actually in play.
export const KEYFRAME_TOLERANCE_SEC = 1 / CAPTURE_FPS;

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
  #tmpSeq = 0;

  constructor({ preset = "p1", gop = 250 } = {}) {
    this.#preset = preset;
    this.#gop = gop;          // the MEASURED default from this host, not an assumption
    this.#log = [];
  }

  get preset() { return this.#preset; }
  get gop() { return this.#gop; }
  get calls() { return this.#log.map((e) => e.op); }

  // Capture from a real source and encode with the real GPU.
  captureAndEncode(out, { source = "desktop", fps = CAPTURE_FPS, seconds = 2, gop = null } = {}) {
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
  // TOLERANCE is one frame at the rate this module actually captures at
  // (CAPTURE_FPS = 30), not 0.5 s and not 1/DEFAULT_FPS. MEASURED WINDOW_UTC
  // 2026-10-10T18:39:09Z: a 0.5 s tolerance PASSED a mid-GOP cut whose first IDR
  // sat at pts 0.233008 -- a clip that shows corruption for its first 7 frames.
  // The negative arm caught the gate being too loose, which is the arm working.
  // DEFECT FIX: the bound was 1/DEFAULT_FPS = 0.0167 s, half of one real frame
  // at 30 fps, so it also refused clips that were correctly cut.
  //
  // displayFile names the file in the ERROR, which is not always the file that
  // was probed: remux() asserts on a temp sibling and passes the caller's path
  // here, so a refused save reports the path the caller asked about and never
  // leaks this module's private temp name into a message someone reads.
  assertStartsOnKeyframe(file, toleranceSec = KEYFRAME_TOLERANCE_SEC, displayFile = file) {
    const first = this.firstKeyframeSec(file);
    if (first === null) {
      throw new ClipNotKeyframed(
        displayFile, "no keyframe could be read (unreadable file, no video stream, or zero keyframes)");
    }
    if (Math.abs(first) > toleranceSec) {
      throw new ClipNotKeyframed(
        displayFile,
        `first IDR at pts ${first.toFixed(6)}s exceeds tolerance ${toleranceSec.toFixed(6)}s`
      );
    }
    return first;
  }

  // Where ffmpeg writes BEFORE the clip is accepted. Same directory as the
  // destination (rename across directories or volumes is not atomic, or does
  // not work at all) and the SAME EXTENSION, because ffmpeg selects the muxer
  // from the extension -- `.part-123` would have produced "Unable to find a
  // suitable output format" instead of a clip. The sequence number makes two
  // concurrent saves to one destination impossible to confuse.
  #tempSiblingFor(outFile) {
    const ext = extname(outFile);
    const stem = basename(outFile, ext);
    this.#tmpSeq += 1;
    return join(dirname(outFile), `.${stem}.remux-${process.pid}-${this.#tmpSeq}${ext}`);
  }

  // The save-time operation. -c copy. This MUST NOT re-encode.
  //
  // DEFECT FIX -- a refused remux used to leave the clip on disk. MEASURED
  // WINDOW_UTC 2026-10-10T19:02:16Z: ffmpeg ran to completion, so the complete
  // output file already existed, and only THEN did the guard throw
  // ClipNotKeyframed. SavePath.save() had already reserved that filename with
  // clip-writer's openSync(..., "wx") and listed it as written, so a refused
  // clip still handed the caller a playable file at the exact path it was about
  // to give the user.
  //
  // THE FIX IS STRUCTURAL, NOT A CLEANUP: ffmpeg never writes outFile. It writes
  // a temp sibling, the guard runs on those bytes, and renameSync moves them
  // into place only after the guard accepted. So outFile cannot exist unless it
  // was accepted -- there is no window in which a refused clip is visible under
  // its real name, not even if the process dies mid-save, and nothing needs
  // deleting on the failure path at all.
  remux(inFile, outFile) {
    const tmp = this.#tempSiblingFor(outFile);
    const t = process.hrtime.bigint();
    try {
      execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
        "-i", inFile, "-c", "copy", tmp], { stdio: ["ignore", "pipe", "pipe"] });
      const ms = Number(process.hrtime.bigint() - t) / 1e6;
      const inBytes = statSync(inFile).size;
      const outBytes = statSync(tmp).size;
      // The invariant runs on the bytes that actually landed, not on intent.
      const firstIdr = this.assertStartsOnKeyframe(tmp, KEYFRAME_TOLERANCE_SEC, outFile);
      renameSync(tmp, outFile);
      this.#log.push({ op: "remux", inFile, outFile, ms, inBytes, outBytes, firstIdr });
      return { inBytes, outBytes, ms, firstIdr, identical: inBytes === outBytes };
    } catch (err) {
      // The destination was never created, so there is nothing to unlink there.
      // The temp is this module's own file and never reached the caller.
      rmSync(tmp, { force: true });
      throw err;
    }
  }

  // The GOP of a file this encoder produced, read from the file.
  gopOf(file, fps = CAPTURE_FPS) { return probeGop(file, fps); }

  encodeCount() { return this.#log.filter((e) => e.op === "encode").length; }
}