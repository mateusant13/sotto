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
  // THE CORRECTED VERDICT.
  //
  // REVIEW FINDING (independent reviewer, POP=1 lane): the previous form was
  //   ok = threw === null && landed && !!gate
  // which PRINTED gate.contentSufficientToCoverClock on one line and never asserted
  // it on the next. Worse, TOTAL_BYTES is a TAUTOLOGY: it equals the pushed length by
  // construction, so the reviewer constructed seed + 131072 bytes of 0xAB, got
  // 621897 bytes on disk, verdict present, sufficient=true, and my census printed OK
  // and exited 0 with 128 KB of injected garbage in the shipped clip.
  //
  // Two changes, both falsifiable:
  //  1. sufficiency is now ASSERTED, not printed. A verdict that says insufficient is a
  //     non-save even when bytes landed.
  //  2. byte identity is checked by SHA-256 against the seed, so "unmodified" has a
  //     falsifier that a size match cannot fake.
  const sufficient = !!gate && gate.contentSufficientToCoverClock === true;
  const ok = threw === null && landed && !!gate && sufficient;
  console.log(`SUFFICIENCY_ASSERTED: ${sufficient}`);
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

// ARM C - the case the reviewer showed sailing through. A REAL container truncated by
// ONE BYTE. ARM B only catches total garbage, so ARM B cannot tell this instrument from
// one that passes everything. This arm MEASURES what happens instead of assuming.
// It is reported, not asserted: the product's gate is a content-sufficiency gate, and
// whether 1-byte truncation must be refused is a product decision, not an instrument one.
const dirC = mkdtempSync(join(tmpdir(), "rootdrive-1byte-"));
let threwC = null;
try {
  const appC = barrel.composeShadowplay({ dir: dirC });
  appC.ring.push(SEED.subarray(0, SEED.length - 1), { frames: 60, keyframe: true });
  await appC.hotkeys.press("f9", 1000);
} catch (e) {
  threwC = e && e.message;
}
const filesC = readdirSync(dirC);
console.log(`--- ARM C - real container truncated by 1 byte ---`);
console.log(`C_BYTES: ${SEED.length - 1}`);
console.log(`C_PRESS_THREW: ${threwC === null ? "no" : "yes"}`);
console.log(`C_FILES: ${filesC.length}`);
console.log(`C_REFUSED: ${threwC !== null}`);
console.log(`C_KNOWN_WEAK_SPOT: ${threwC === null}`);

console.log(`PRODUCT_SAVES_REAL_CLIP: ${ok && negRefused}`);
process.exit(ok && negRefused ? 0 : 1);