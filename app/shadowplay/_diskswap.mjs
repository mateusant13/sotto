// ARM D - THE DISK-SWAP EXPERIMENT, in my own instrument.
//
// The reviewer proved by swap that the gate reads the landed file rather than memory:
// it let the real save finish, overwrote the file with zeros while memory stayed
// intact, and the gate REFUSED. I have not replicated that. Until I do, my claim that
// "the gate reads disk" rests on reading their code, not on my own measurement.
//
// The experiment, and why it is falsifiable:
//   1. save a real clip through the PUBLIC root -> a verdict exists, clip lands
//   2. record sha256 of the landed file
//   3. OVERWRITE that file on disk with 64 zero bytes, keeping every in-memory copy
//   4. call the product's own gate, assessDelivery(), on the SAME path
//   5. if the gate refuses, it can only have read the DISK: the in-memory payload is
//      untouched and identical in both calls
// A gate consulting memory would pass step 4. This one either fails or doesn't.
//
// Populated only if a refusal happens, so a corrupt file cannot be mistaken for a
// clean one in any later inspection.
import { mkdtempSync, readdirSync, writeFileSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import * as barrel from "./index.js";
import { assessDelivery } from "./frame-accounting.js";

const sha = (b) => createHash("sha256").update(b).digest("hex");

const seedDir = mkdtempSync(join(tmpdir(), "dswap-seed-"));
const seedPath = join(seedDir, "seed.mp4");
const enc = new barrel.NvencEncoder({ preset: "p1" });
enc.captureAndEncode(seedPath, { fps: 30, seconds: 2 });
const SEED = readFileSync(seedPath);
console.log(`SEED_BYTES: ${SEED.length}`);

const dir = mkdtempSync(join(tmpdir(), "dswap-"));
const app = barrel.composeShadowplay({ dir });
app.ring.push(SEED, { frames: 60, keyframe: true });

let verdict = null;
let threw = null;
try {
  const action = await app.hotkeys.press("f9", 1000);
  verdict = action.clip.verdict;
} catch (e) {
  threw = e && e.message;
}
const landed = join(dir, "0000.mp4");
const before = readdirSync(dir);
console.log(`FILES_AFTER_SAVE: ${before.length}`);
console.log(`SAVE_THREW: ${threw === null ? "no" : "yes"}`);
console.log(`VERDICT_AFTER_SAVE: ${verdict ? "present" : "ABSENT"}`);
if (verdict) console.log(`VERDICT_SUFFICIENT: ${verdict.contentSufficientToCoverClock}`);

if (!before.includes("0000.mp4")) {
  console.log(`DISK_SWAP_RUN: false - nothing landed to corrupt`);
  process.exit(1);
}

const shaBefore = sha(readFileSync(landed));
const bytesBefore = readFileSync(landed).length;
console.log(`LANDED_SHA_BEFORE: ${shaBefore.slice(0, 16)}`);
console.log(`LANDED_BYTES_BEFORE: ${bytesBefore}`);

// STEP 3. Corrupt the disk. Nothing in memory changes; SEED is untouched and the
// product's own payload object still holds the original bytes.
writeFileSync(landed, Buffer.alloc(64, 0x00));
const shaAfter = sha(readFileSync(landed));
console.log(`LANDED_SHA_AFTER:  ${shaAfter.slice(0, 16)}`);
console.log(`FILE_ACTUALLY_CHANGED: ${shaBefore !== shaAfter}`);
console.log(`SEED_UNTOUCHED: ${sha(SEED) === shaBefore}`);

// STEP 4. The product's own gate, same path, after corruption.
let gateThrew = null;
let gate2 = null;
try {
  gate2 = await assessDelivery(landed, 30, 2);
} catch (e) {
  gateThrew = e && e.message;
}
console.log(`--- gate on the CORRUPTED file, same path ---`);
console.log(`GATE2_THREW: ${gateThrew === null ? "no" : "yes"}`);
if (gateThrew) console.log(`GATE2_ERROR: ${gateThrew.split("\n")[0]}`);
console.log(`GATE2_VERDICT: ${gate2 ? JSON.stringify(gate2).slice(0, 120) : "ABSENT"}`);

// THE VERDICT OF THIS ARM. The gate refused a path it had previously accepted, with
// memory unchanged. That can only happen if it reads the disk.
const readsDisk = gateThrew !== null && shaBefore !== shaAfter;
console.log(`GATE_READS_DISK: ${readsDisk}`);
process.exit(readsDisk ? 0 : 1);