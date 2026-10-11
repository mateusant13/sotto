// WHY 28 UNIQUE FRAMES, MEASURED RATHER THAN REASONED.
//
// WHAT THIS IS FOR. At WINDOW_UTC 2026-10-11T09:07:05Z one gate run recorded
//   compose-probe.mjs FAILED exit 1: deliver() -> THREW Error: instant replay refused:
//     ...0000.mp4 holds 28 contiguous d...
// and every other run of the same probe delivered a 219-234 frame clip. This file exists
// to test ONE hypothesis about where 28 comes from, and to fail honestly if it is wrong.
//
// THE HYPOTHESIS. replay-ring.js:182-188, #cutFromLastKeyframe():
//     for (let i = this.#segments.length - 1; i >= 0; i--) {
//       if (!this.#segments[i].keyframe) continue;
//       return Buffer.concat(this.#segments.slice(i).map((s) => s.bytes));
//     }
// It walks BACKWARDS and cuts from the LAST keyframe to the end. So the clip length is
// (number of frames deposited) MINUS (frames before the last keyframe). If the encoder
// deposits exactly one keyframe, at the head, the cut is the whole capture -- which is the
// 219-234 frame case. If it deposits a SECOND keyframe near the tail, the cut collapses to
// whatever sits after it. At 30 fps a GOP boundary 28 frames from the end yields exactly
// 28 frames, which is UNDER oneSecondOfClock, and frame-accounting.js:367 then sets
// contentSufficientToCoverClock false and replay-ring.js:340 refuses. 28 is what this
// predicts, which is why it is worth measuring rather than asserting.
//
// WHAT THIS MEASURES. After a real capture, the shape of the ring: how many segments, how
// many are keyframes, and where they sit. It reads the ring through the same public getter
// the composition root exposes; it writes nothing and edits nothing.
//
// WHAT IT CANNOT SETTLE. If every run shows exactly one keyframe at the head, that is
// CONSISTENT with the hypothesis and does not prove it -- the failing run is the one that
// would show a second keyframe, and 6 direct runs did not reproduce it. I will report that
// as unconfirmed rather than upgrade it.
import { composeShadowplay } from "./index.js";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const dir = mkdtempSync(join(tmpdir(), "shadowplay-kf-"));
let app = null;
try {
  app = composeShadowplay({ dir });
} catch (err) {
  console.log(`COMPOSE_FAILED ${err.message}`);
  process.exit(1);
}

const captured = await app.capture();
const ring = app.ring;
// segments() is a COUNT, not the list. The list is private. So I cannot enumerate which
// segments are keyframes from outside -- and I am not going to reach past the private
// field to get it, because a probe that reads the internals it is measuring stops being
// evidence about the product. What IS observable: the count of segments, and the verdict
// deliver() reaches.
const segCount = ring.segments();
let delivered = null, threw = null;
try {
  delivered = await app.deliver("f9", captured.frames);
} catch (err) {
  threw = err.message;
}
console.log(`CAPTURED_FRAMES ${captured.frames}`);
console.log(`RING_SEGMENTS ${segCount}`);
console.log(`DELIVERED ${delivered ? JSON.stringify(delivered).slice(0, 120) : "none"}`);
console.log(`THREW ${threw ? threw.slice(0, 160) : "no"}`);
try { rmSync(dir, { recursive: true, force: true }); } catch { /* best effort */ }
console.log("DONE");
process.exit(threw ? 1 : 0);