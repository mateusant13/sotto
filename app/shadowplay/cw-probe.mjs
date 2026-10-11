// End-to-end probe: can ClipWriter actually land real encoded bytes on disk?
// POPULATION = 1 writer, 1 payload, 1 directory. WINDOW = stdout header.
import { ClipWriter } from "./clip-writer.js";
import { mkdtempSync, statSync, rmSync, existsSync, writeSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const WINDOW = new Date().toISOString().replace(/\.\d+Z$/, "Z");
const dir = mkdtempSync(join(tmpdir(), "cw-probe-"));
let seq = 0;
const clock = { nextName: () => String(++seq).padStart(4, "0") };

const w = new ClipWriter({ dir, clock, exists: () => false });
const name = w.nextClipName();
const p = join(dir, name);

const afterClaim = existsSync(p) ? statSync(p).size : -1;
console.log(`WINDOW_UTC: ${WINDOW}`);
console.log(`name=${name}  after_claim_bytes=${afterClaim}`);

const payload = Buffer.from("REAL ENCODED CLIP BYTES ".repeat(512));
console.log(`payload_bytes=${payload.length}`);

let landed = -1;
let mode = "none";
let landedName = "(none)";
try {
  if (typeof w.writeClip === "function") {
    // CORRECTED SHAPE: writeClip(data) takes ONLY the payload; it opens its own
    // clip and returns the name it wrote. My first probe passed (name, payload),
    // so it wrote a different file than the one I stat'd.
    landedName = w.writeClip(payload);
    landed = existsSync(join(dir, landedName)) ? statSync(join(dir, landedName)).size : -1;
    mode = "writeClip";
  }
} catch (e) {
  mode = "THREW: " + e.message;
}
console.log(`mode=${mode}`);
console.log(`landed_name=${landedName}`);
console.log(`after_bytes=${landed}`);
console.log(`BYTES_LANDED=${landed === payload.length ? "YES" : "NO (" + landed + " vs " + payload.length + ")"}`);

// Negative arm 1: a zero-byte payload must be REFUSED, not written.
let zeroRefused = "NOT-REFUSED";
try {
  w.writeClip(Buffer.alloc(0));
  zeroRefused = "NOT-REFUSED";
} catch (e) {
  zeroRefused = "REFUSED: " + e.constructor.name;
}
console.log(`ZERO_BYTE_PAYLOAD=${zeroRefused}`);

// Negative arm 2: abortClip must not leave a playable file behind.
let abortLeft = "n/a";
try {
  const h = w.openClip();
  const nm = h.name;
  writeSync(h.fd, payload);
  w.abortClip(h);
  abortLeft = existsSync(join(dir, nm)) ? statSync(join(dir, nm)).size : -1;
} catch (e) {
  abortLeft = "THREW: " + e.message;
}
console.log(`AFTER_ABORT_bytes=${abortLeft} (${abortLeft === -1 ? "nothing left" : "FILE REMAINS"})`);

rmSync(dir, { recursive: true, force: true });
console.log("PROBE_DONE");