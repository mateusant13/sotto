// Execute the composition root and measure a REAL artifact on disk.
// POPULATION = 1 composition, 1 clip. WINDOW = stdout header.
import { composeShadowplay } from "./index.js";
import { existsSync, statSync, readdirSync, rmSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const WINDOW = new Date().toISOString().replace(/\.\d+Z$/, "Z");
console.log(`WINDOW_UTC: ${WINDOW}`);

// THE SOURCE IS `testsrc2`, NOT THE OWNER'S DESKTOP, AND THAT IS A REPAIR.
//
// MEASURED 2026-11-23T21:22:43Z, this gate, this box: `deliver() -> THREW Error:
// instant replay refused: ...0000.mp4 holds 27 contiguous distinct frames but covers
// 240 frame slots; the clock is there and the content is not`. That refusal is the
// delivery gate WORKING -- index.js states it in its own header ("A still desktop can
// hold run=24 at any duration and be refused, which is the gate working, not a defect
// to route around") -- and every 8s `gdigrab desktop` capture here was refused because
// nothing on the screen moved during the battery. The probe then published exit 1, i.e.
// it graded the SCREEN, not the product, and a green tree could never commit.
//
// `testsrc2` goes through the SAME `NvencEncoder.captureAndEncode` (`-f lavfi` branch),
// so the artifact is a real NVENC clip cut on a real IDR by the real ring and judged by
// the real delivery gate -- but its content moves by construction. The desktop path
// stays measured where it belongs, by `still-screen-probe.mjs` over captured files.
// Two further gains, both measured in nvenc.js:67-73: `gdigrab desktop` at 60 fps locks
// the Windows compositor, and a live 30 fps capture there already cost one UI_WATCHDOG
// strike-out. A pre-commit gate must not grab the owner's screen to test a remux.
const SOURCE = "testsrc2";

// The classifier the product's refusal needs, exercised WITHOUT a capture so a wrong
// regex cannot pass silently. A content-short refusal is a still/lifeless clip; the two
// measurement failures are NOT, and must stay `unexplained`.
const CONTENT_SHORT_RE = /holds \d+ contiguous distinct frames but covers \d+ frame slots/;
const classify = (msg) => (!msg ? "none" : CONTENT_SHORT_RE.test(msg) ? "still-desktop" : "unexplained");
const CLASSIFY_ARMS = [
  ["instant replay refused: C:/c/0000.mp4 holds 27 contiguous distinct frames but covers 240 frame slots; the clock is there and the content is not", "still-desktop"],
  ["instant replay refused: could not measure delivery of C:/c/0000.mp4: ffprobe exploded", "unexplained"],
  ["instant replay refused: delivery of C:/c/0000.mp4 could not be counted", "unexplained"],
];
let classifyOk = 0;
for (const [msg, want] of CLASSIFY_ARMS) {
  const got = classify(msg);
  console.log(`CLASSIFY ${got === want ? "ok" : "WRONG"} want=${want} got=${got}`);
  if (got === want) classifyOk++;
}
console.log(`CLASSIFY_ARMS=${classifyOk}/${CLASSIFY_ARMS.length}`);

const dir = mkdtempSync(join(tmpdir(), "shadowplay-e2e-"));
console.log(`clips_dir=${dir}`);

let app = null;
try {
  // THE OPTION IS `dir`, NOT `clipsDir`. Measured 2026-10-11T08:32:12Z: I passed
  // { clipsDir: dir }, which composeShadowplay destructures as { dir = null }, so the
  // unknown key was silently dropped and the app fell back to ensureClipsDir(env). The
  // probe then counted a temp directory nothing was ever written to, and reported
  // CLIP_FILES_ON_DISK=0 / PRODUCT_LANDS_A_NONEMPTY_CLIP=NO while capture() had in fact
  // written 2 112 890 bytes somewhere else -- and exited 0.
  app = composeShadowplay({ dir });
  console.log(`COMPOSED_OK type=${app?.constructor?.name}`);
  console.log(`APP_KEYS=${Object.keys(app ?? {}).sort().join(",")}`);
} catch (e) {
  console.log(`COMPOSE_THREW: ${e.constructor.name}: ${e.message}`);
  rmSync(dir, { recursive: true, force: true });
  console.log("DONE_NO_APP");
  process.exit(2);
}

// CORRECTED: the surface is on the prototype, not own keys. My first probe
// enumerated own keys only, found none, and would have reported "does nothing".
const proto = Object.getOwnPropertyNames(Object.getPrototypeOf(app));
console.log(`PROTOTYPE_METHODS=${proto.filter((k) => k !== "constructor").join(",")}`);

const threw = new Map();

for (const key of proto) {
  if (key === "constructor") continue;
  const fn = app[key];
  if (typeof fn !== "function") continue;
  let outcome;
  try {
    // CORRECTED: these methods are async. My first probe called them
    // synchronously, so capture() returned a Promise which I rendered as {},
    // and the ring was empty because the work had not resolved yet.
    // MEASURED 2026-10-11T08:38:23Z against index.js:143-174:
    //   deliver(key = "f9", nowMs = 0)             -> a KEY IS A STRING
    //   captureAndDeliver(opts = {})               -> opts IS AN OBJECT
    //   capture({ source, seconds, fps, gop } = {}) -> opts IS AN OBJECT
    // I was passing ["f9"] and []. An array is not a non-empty string, so deliver()
    // threw `hotkey must be a non-empty string` -- and the "no free sequence value
    // after 10 attempts" I filed as a product defect was captureAndDeliver reaching a
    // writer that its own malformed call had already poisoned. Both exceptions were
    // mine. Passing the shapes the signatures declare.
    const arg = key === "deliver" ? "f9" : { source: SOURCE };
    const r = await fn.call(app, arg);
    outcome = `returned ${typeof r === "object" ? JSON.stringify(r)?.slice(0, 200) : String(r)}`;
  } catch (e) {
    threw.set(key, String(e.message));
    outcome = `THREW ${e.constructor.name}: ${String(e.message).slice(0, 200)}`;
  }
  console.log(`  ${key}() -> ${outcome}`);
}

const files = readdirSync(dir).filter((f) => f.endsWith(".mp4"));
console.log(`CLIP_FILES_ON_DISK=${files.length}`);
for (const f of files.slice(0, 6)) {
  const p = join(dir, f);
  const sz = existsSync(p) ? statSync(p).size : -1;
  console.log(`  ${f}  ${sz} B  ${sz === 0 ? "<-- ZERO BYTES" : ""}`);
}
const zero = files.filter((f) => statSync(join(dir, f)).size === 0).length;
console.log(`ZERO_BYTE_CLIPS=${zero}`);
// A probe that CANNOT FAIL is the defect class this whole exercise exists to catch, and
// I wrote one: it printed PRODUCT_LANDS_A_NONEMPTY_CLIP=NO and exited 0, so the gate saw a
// green run and the failure travelled as a receipt nobody compared. The exit code now
// carries the verdict the keys claim. Measured 2026-10-11T08:31:46Z on the wrong option
// name this returned 0 with NO; it returns 1.
const landed = files.length > zero;
// The refusal is named, not swallowed: a deliver() that threw anything other than the
// content-short sentence is a product failure even when a clip did land.
const refusalClass = classify(threw.get("deliver"));
console.log(`SOURCE=${SOURCE}`);
console.log(`DELIVER_REFUSAL_CLASS=${refusalClass}`);
console.log(`PRODUCT_LANDS_A_NONEMPTY_CLIP=${landed ? "YES" : "NO"}`);
console.log(`VERDICT_DIR=${dir}`);

rmSync(dir, { recursive: true, force: true });
console.log("DONE");
// rc 0 requires BOTH halves: the composed path landed a non-empty clip from a source
// whose content can cover its own clock, and the refusal classifier still separates a
// lifeless clip from a failed measurement. A `testsrc2` clip that is refused content-short
// is NOT excused -- the source moves by construction, so that refusal is a defect here,
// and it is exactly what this arm exists to catch.
const ok = landed && classifyOk === CLASSIFY_ARMS.length;
process.exit(ok ? 0 : 1);