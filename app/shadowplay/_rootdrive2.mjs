// MEASUREMENT INSTRUMENT v2. v1 was too generous: it printed
// PRODUCT_LANDED_BYTES:true because 4096 B reached the disk, while the press had
// actually THROWN. Bytes on disk + a refusal is not a save. This version makes
// the verdict AND over three falsifiable conditions:
//   1. press() did not throw
//   2. the file exists on a real disk with real bytes
//   3. the delivery gate produced a verdict object (ffprobe/ffmpeg read the file)
// The seed is a REAL NVENC-encoded clip, not a filler buffer: the v1 seed was
// rejected with "moov atom not found", which is the instrument's fault, not the
// product's. A gate that cannot say NO is useless, so arm B is a deliberate
// broken input that MUST fail -- if it passes, this instrument is broken.
import { mkdtempSync, readdirSync, statSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import * as barrel from "./index.js";

function census(label, dir, action, threw) {
  const files = readdirSync(dir);
  let total = 0;
  for (const n of files) total += statSync(join(dir, n)).size;
  const gate = action && action.clip && action.clip.verdict;
  const landed = files.length > 0 && total > 0;
  console.log(`--- ${label} ---`);
  console.log(`FILES: ${files.length} [${files.join(",")}]`);
  console.log(`TOTAL_BYTES: ${total}`);
  console.log(`PRESS_THREW: ${threw === null ? "no" : "yes -> " + threw}`);
  console.log(`GATE_VERDICT: ${gate ? "present" : "ABSENT"}`);
  if (gate) {
    console.log(`GATE_LONGEST_UNIQUE_RUN: ${gate.longestUniqueRun}`);
    console.log(`GATE_SUFFICIENT: ${gate.contentSufficientToCoverClock}`);
  }
  // THE CORRECTED VERDICT. All three, not any one.
  const ok = threw === null && landed && !!gate;
  console.log(`SAVED: ${ok}`);
  return ok;
}

// A REAL CLIP. Encoded by the same NVENC encoder the product uses.
const seedDir = mkdtempSync(join(tmpdir(), "rootdrive-seed-"));
const seedPath = join(seedDir, "seed.mp4");
const enc = new barrel.NvencEncoder({ preset: "p1" });
enc.captureAndEncode(seedPath, { fps: 30, seconds: 2 });
// The encoder WRITES the container to disk; its return value carries no bytes.
// Reading the artifact back is the honest source, and v1's mistake was assuming
// otherwise.
const SEED = readFileSync(seedPath);
console.log(`SEED_BYTES: ${SEED.length}`);
console.log(`SEED_ON_DISK: ${existsSync(seedPath)}`);
console.log(`SEED_IS_REAL_CONTAINER: ${SEED.length > 10000}`);

const dir = mkdtempSync(join(tmpdir(), "rootdrive2-"));
const app = barrel.composeShadowplay({ dir });
// FRAMES is footage count, not byte count. v2 passed SEED.length (490914 frames,
// ~4.5 hours) into a ring sized for `minutes`; the segment was evicted on push and
// the ring correctly reported 0 segments. The seed is a 2s @30fps capture = 60 frames.
app.ring.push(SEED, { frames: 60, keyframe: true });

let action = null;
let threw = null;
try {
  action = await app.hotkeys.press("f9", 1000);
} catch (e) {
  threw = e && e.message;
}
const ok = census("ARM A - real encoded seed", dir, action, threw);

// ARM B - the control negative. A deliberately broken input must be REFUSED.
// If this arm passes, the instrument cannot tell a save from a failure and every
// ARM A result above is void.
let threwB = null;
const dirB = mkdtempSync(join(tmpdir(), "rootdrive-neg-"));
const appB = barrel.composeShadowplay({ dir: dirB });
appB.ring.push(Buffer.alloc(64, 0x00), { frames: 1, keyframe: true });
try {
  await appB.hotkeys.press("f9", 1000);
} catch (e) {
  threwB = e && e.message;
}
const filesB = readdirSync(dirB);
const negRefused = threwB !== null;
console.log(`--- ARM B - control negative (64 zero bytes) ---`);
console.log(`NEG_PRESS_THREW: ${threwB === null ? "no" : "yes -> " + threwB}`);
console.log(`NEG_FILES: ${filesB.length}`);
console.log(`NEG_REFUSED: ${negRefused}`);
console.log(`INSTRUMENT_CAN_SAY_NO: ${negRefused}`);

console.log(`PRODUCT_SAVES_REAL_CLIP: ${ok && negRefused}`);
process.exit(ok && negRefused ? 0 : 1);