// MEASUREMENT INSTRUMENT, not a test. It asks ONE question the suites do not:
// does the PUBLIC composition root (composeShadowplay, from the barrel) actually
// land real bytes on a real disk, when driven the way a user drives it?
//
// It reports what it measured and exits non-zero if the artifact is absent or empty.
// Every number it prints is falsifiable: bytes on disk, file count, exit code.
import { mkdtempSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import * as barrel from "./index.js";

const dir = mkdtempSync(join(tmpdir(), "rootdrive-"));
const before = readdirSync(dir).length;

// Bytes shaped like what the encoder delivers. The suites use a seed; this uses
// the same idea so the size assertion below is comparable.
const SEED = Buffer.alloc(4096, 0x42);

let app;
try {
  app = barrel.composeShadowplay({ dir });
} catch (e) {
  console.log(`COMPOSE_THREW: ${e && e.message}`);
  console.log("ARTIFACTS: 0");
  process.exit(2);
}

const shape = Object.keys(app).sort().join(",");
console.log(`COMPOSE_OK: true`);
console.log(`RETURNED_KEYS: ${shape}`);
console.log(`RING_PRESENT: ${typeof app.ring}`);
console.log(`HOTKEYS_PRESENT: ${typeof app.hotkeys}`);

let action = null;
let pressError = null;
try {
  app.ring.push(SEED, { frames: 60, keyframe: true });
  action = await app.hotkeys.press("f9", 1000);
} catch (e) {
  pressError = e && e.message;
}

if (pressError) {
  console.log(`PRESS_THREW: ${pressError}`);
}
if (action) {
  console.log(`ACTION: ${action.action}`);
  console.log(`CLIP_NAME: ${action.clip && action.clip.name}`);
  console.log(`CLIP_PATH: ${action.clip && action.clip.path}`);
}

// THE MEASUREMENT. Not "did a test pass" -- what is actually on the disk.
const after = readdirSync(dir);
console.log(`FILES_BEFORE: ${before}`);
console.log(`FILES_AFTER: ${after.length}`);
console.log(`FILE_NAMES: ${after.join(",")}`);

let totalBytes = 0;
let nonempty = 0;
for (const n of after) {
  const s = statSync(join(dir, n)).size;
  totalBytes += s;
  if (s > 0) nonempty++;
  console.log(`FILE ${n} BYTES ${s}`);
}
console.log(`TOTAL_BYTES: ${totalBytes}`);
console.log(`NONEMPTY_FILES: ${nonempty}`);

// VERDICT: the product landed encoded bytes, not a reservation.
const ok = after.length > 0 && totalBytes > 0;
console.log(`PRODUCT_LANDED_BYTES: ${ok}`);
process.exit(ok ? 0 : 1);