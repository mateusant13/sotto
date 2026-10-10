// The barrel, and now the COMPOSITION ROOT.
//
// Before this file the project had modules and tests but no entry point: every
// module was individually correct and nothing constructed any of them together,
// so the product could not run. MEASURED WINDOW_UTC 2026-10-10T19:41Z over the
// directory (POP=31 .js/.mjs files): `attach()` had zero callers, `sidecar()`
// had zero callers, and hotkeys.js:54 was the single router-reachable route --
// which meant exactly ONE code path in the whole tree could ever produce a clip.
//
// What composeShadowplay() constructs, and WHY each argument is the value it is.
//
//   ClipWriter({ exists, dir })    clip-writer.js:62
//     `exists` is mandatory (TypeError without it) and `dir` is what turns a NAME
//     into a PATH. With dir null, pathFor() returns a bare name and no caller can
//     hand that to ffprobe -- which is exactly the state replay-ring.js:196
//     documents as having made the delivery gate unmeasurable.
//
//   SavePath({ writer })           save-path.js:195
//     The injected writer wins over the default, which is what lets a caller
//     choose the directory. save() stays the only writer in the product.
//
//   NvencEncoder({ preset, gop })  nvenc.js:54
//     preset p1 and gop 60 are MEASURED on this host, not assumed.
//
//   ReplayRing({ minutes, fps, savePath })   replay-ring.js:89
//     FPS MUST BE CAPTURE_FPS (30) AND NOT THE CLASS DEFAULT OF 60.
//     MEASURED WINDOW_UTC 2026-10-10T19:44Z, POP=3 desktop captures at 8s:
//     longestUniqueRun measured 51, 38, 37. The delivery gate refuses when
//     longestUniqueRun < ring.fps (replay-ring.js:285, via frame-accounting.js:355
//     `oneSecondOfClock = expectedFps`). At fps=60 every one of those three REAL
//     captures is refused. At fps=30 all three pass. The default would have made
//     this composition root refuse correct clips -- so the root states the rate
//     the encoder actually captures at rather than accepting the default.
//
//   HotkeyRouter({ ring, debounceMs, overlayOn, onRefusal })  hotkeys.js:16
//     onRefusal is how the failure path is RECORDED; see hotkeys.js.
//
// Frontend is explicitly last in this project (INTEGRATION-PLAN), so this root
// exposes a headless API and builds no UI.
import { existsSync, readFileSync, rmSync, mkdirSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// THE BARREL. These `export ... from` lines are the module's PUBLIC API and are
// load-bearing for other modules' tests, which import from here rather than from
// the leaf file.
//
// MEASURED WINDOW_UTC 2026-10-10T19:40Z (local 16:40Z-3): adding the composition root downgraded
// these twelve lines to plain `import`, and four suites went red on the spot with
// `SyntaxError: ./index.js does not provide an export named 'ClipWriter'` --
// replay-ring.test.mjs, captions.test.mjs, audio-track.test.mjs and
// session-clock.test.mjs, POP=4 of 15 suites in the directory. A composition root
// that breaks the barrel is not a composition root, it is a breaking change
// wearing one. They are re-exports AND the root imports what it needs below.
export { SessionClock, format, WIDTH, CEILING } from "./session-clock.js";
export { ClipWriter, MAX_ATTEMPTS, parseSeq } from "./clip-writer.js";
export { SavePath, ROUTES, ensureClipsDir, defaultClipsDir } from "./save-path.js";
export { ReplayRing, idrAligned, backToNearestIdr, DEFAULT_MINUTES } from "./replay-ring.js";
export { mix, sumPower, toDbFS, fromDbFS, safeGain, HEADROOM_DB } from "./audio-mix.js";
export { HotkeyRouter, DEFAULT_DEBOUNCE_MS } from "./hotkeys.js";
export { Encoder, FRAME_TYPES } from "./encoder.js";
export { AudioTrack } from "./audio-track.js";
export { Broadcast, TRANSPORTS } from "./broadcast.js";
export { CaptionTrack, MAX_CAPTION_MS } from "./captions.js";
export { probeGop, gopFromKeyframes, parseKeyframes, DEFAULT_FPS } from "./stream-probe.js";
export { NvencEncoder, ClipNotKeyframed, NVENC, KEYFRAME_TOLERANCE_SEC, CAPTURE_FPS } from "./nvenc.js";
// Re-exported now that the root depends on it: a test that wants to assert the
// composed path's delivery verdict must be able to reach the same function the
// root uses, rather than importing a second copy of the idea.
export { assessDelivery, countFrames } from "./frame-accounting.js";

// What the composition root itself constructs. These imports are LOCAL: they bind
// the names used below and are not part of the barrel's public API.
import { ClipWriter } from "./clip-writer.js";
import { SavePath, ensureClipsDir } from "./save-path.js";
import { ReplayRing, DEFAULT_MINUTES } from "./replay-ring.js";
import { HotkeyRouter, DEFAULT_DEBOUNCE_MS } from "./hotkeys.js";
import { NvencEncoder, ClipNotKeyframed, KEYFRAME_TOLERANCE_SEC, CAPTURE_FPS } from "./nvenc.js";
import { countFrames } from "./frame-accounting.js";

// The capture defaults this root encodes into the product. Measured, not chosen
// for taste -- see the comment on FPS above for the 30.
//
// `seconds: 8` IS LOAD-BEARING AND NOT A UNIVERSAL SAFE VALUE. The delivery gate
// refuses a clip whose longest run of contiguous distinct frames is shorter than
// one second of its own clock (frame-accounting.js:355, `oneSecondOfClock =
// expectedFps`), and a real desktop capture's run length depends on how much the
// screen actually CHANGES.
//
// MEASURED WINDOW_UTC 2026-10-10T20:31Z, WINDOW = this host's live desktop,
// POPULATION = 5 captures at the same 30 fps, one delivery each:
//   seconds=2 -> REFUSED (run 24, needs 30)
//   seconds=3 -> delivered (run 44)
//   seconds=4 -> REFUSED (run 24, needs 30)
//   seconds=6 -> delivered (run 33)
//   seconds=8 -> delivered (run 36, and run 37 on a repeat)
// Two of five short captures were refused and a 3s capture was accepted while a
// 4s one was refused: the boundary is a property of the PICTURE, not of the
// duration, so no constant here can make it disappear. 8s is chosen because every
// 8s desktop capture measured so far cleared it (POP=3 at WINDOW_UTC 19:44Z,
// run 51/38/37; plus run 37 and run 36 here), NOT because it is proven for every
// screen. A still desktop can hold run=24 at any duration and be refused, which
// is the gate working, not a defect to route around.
//
// The refusal is correct behaviour and the caller is told why, which is what the
// onRefusal wiring below exists for.
export const CAPTURE_DEFAULTS = Object.freeze({
  source: "desktop",
  seconds: 8,
  fps: CAPTURE_FPS,
  gop: 60,
  minutes: DEFAULT_MINUTES,
  preset: "p1",
  debounceMs: DEFAULT_DEBOUNCE_MS,
});

// One clip, captured for real and cut on an IDR, with nothing re-encoded.
export class Shadowplay {
  #encoder; #writer; #savePath; #ring; #hotkeys; #staging; #captures = 0;

  constructor({ encoder, writer, savePath, ring, hotkeys, staging }) {
    this.#encoder = encoder; this.#writer = writer; this.#savePath = savePath;
    this.#ring = ring; this.#hotkeys = hotkeys; this.#staging = staging;
  }

  get encoder() { return this.#encoder; }
  get savePath() { return this.#savePath; }
  get ring() { return this.#ring; }
  get hotkeys() { return this.#hotkeys; }
  get dir() { return this.#writer.dir; }
  captures() { return this.#captures; }

  // CAPTURE. Encodes a real source with the real GPU encoder and hands the
  // ENCODED BYTES to the ring -- bytes, not a frame count, because a number
  // describes footage nobody has (save-path.js:170 and replay-ring.js:311 both
  // refuse one, correctly).
  //
  // The segment's `keyframe` flag is the encoder's own MEASUREMENT
  // (firstKeyframeSec read off the encoded file), never an assumption. If the
  // encode did not begin on an IDR the segment is refused here, at the capture
  // boundary, rather than being pushed and discovered later by a gate that has
  // to guess which of many segments was meant.
  async capture({ source = CAPTURE_DEFAULTS.source, seconds = CAPTURE_DEFAULTS.seconds, fps = CAPTURE_DEFAULTS.fps, gop = null } = {}) {
    const out = join(this.#staging, `cap-${process.pid}-${++this.#captures}.mp4`);
    let encoded;
    try {
      encoded = this.#encoder.captureAndEncode(out, { source, fps, seconds, gop });
      const firstIdr = this.#encoder.firstKeyframeSec(out);
      if (firstIdr === null || Math.abs(firstIdr) > KEYFRAME_TOLERANCE_SEC) {
        throw new ClipNotKeyframed(
          source,
          `the captured segment begins at pts ${firstIdr}, outside tolerance ` +
          `${KEYFRAME_TOLERANCE_SEC}s; a segment the ring cannot cut on is not pushed`,
        );
      }
      const bytes = readFileSync(out);
      const frames = await countFrames(out);   // REAL frame count, not seconds*fps
      this.#ring.push(bytes, { frames, keyframe: true });
      return { out, bytes: encoded.bytes, frames, firstIdr, codec: encoded.codec, fps };
    } finally {
      rmSync(out, { force: true });
    }
  }

  // DELIVER. The one router-reachable route, hotkeys.js:54. A refusal is
  // recorded on the SavePath AND re-thrown to the caller; see hotkeys.js.
  async deliver(key = "f9", nowMs = 0) { return this.#hotkeys.press(key, nowMs); }

  // The full composed capture-to-clip pass, as one call.
  async captureAndDeliver(opts = {}) {
    const captured = await this.capture(opts);
    const delivered = await this.deliver("f9", captured.frames);
    return { captured, delivered };
  }
}

// The composition root. Builds every object the product needs, in the only
// order that works: a writer needs its directory, a SavePath needs the writer,
// the ring needs the SavePath, and the router needs the ring.
export function composeShadowplay({
  env = process.env,
  dir = null,
  source = CAPTURE_DEFAULTS.source,
  seconds = CAPTURE_DEFAULTS.seconds,
  fps = CAPTURE_DEFAULTS.fps,
  gop = CAPTURE_DEFAULTS.gop,
  preset = CAPTURE_DEFAULTS.preset,
  minutes = CAPTURE_DEFAULTS.minutes,
  debounceMs = CAPTURE_DEFAULTS.debounceMs,
  overlayOn = true,
} = {}) {
  // The directory. ensureClipsDir() CREATES it (mkdirSync recursive); an
  // injected dir is respected as-is but still created, because ClipWriter's
  // exclusive create fails with ENOENT on a missing parent (clip-writer.js:204).
  const clipsDir = dir ?? ensureClipsDir(env);
  mkdirSync(clipsDir, { recursive: true });

  const exists = (name) => existsSync(join(clipsDir, name));
  const writer = new ClipWriter({ exists, dir: clipsDir });
  const savePath = new SavePath({ writer });

  const encoder = new NvencEncoder({ preset, gop });
  // fps is CAPTURE_FPS, never the class default of 60. See the header: at 60
  // every real capture measured on this host is refused by the delivery gate.
  const ring = new ReplayRing({ minutes, fps, savePath });

  // THE FAILURE PATH, wired. recordFailure is what makes a refused capture
  // visible instead of silently absent (save-path.js:253).
  const hotkeys = new HotkeyRouter({
    ring,
    debounceMs,
    overlayOn,
    onRefusal: (err, context) => {
      savePath.recordFailure(context.route, err);
    },
  });

  // Staging lives OUTSIDE the clips directory. A consumer enumerating the clips
  // directory must never see a half-written working file, which is the same
  // reasoning clip-writer.js:26 gives for refusing a `.part` sibling.
  const staging = mkdtempSync(join(tmpdir(), "shadowplay-"));

  return new Shadowplay({ encoder, writer, savePath, ring, hotkeys, staging });
}