// Execute the composition root and measure a REAL artifact on disk.
// POPULATION = 1 composition, 1 clip. WINDOW = stdout header.
import { composeShadowplay } from "./index.js";
import { existsSync, statSync, readdirSync, rmSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const WINDOW = new Date().toISOString().replace(/\.\d+Z$/, "Z");
console.log(`WINDOW_UTC: ${WINDOW}`);

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

for (const key of proto) {
  if (key === "constructor") continue;
  const fn = app[key];
  if (typeof fn !== "function") continue;
  let outcome;
  try {
    // CORRECTED: these methods are async. My first probe called them
    // synchronously, so capture() returned a Promise which I rendered as {},
    // and the ring was empty because the work had not resolved yet.
    const r = await fn.call(app, key === "deliver" ? ["f9"] : []);
    outcome = `returned ${typeof r === "object" ? JSON.stringify(r)?.slice(0, 200) : String(r)}`;
  } catch (e) {
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
console.log(`PRODUCT_LANDS_A_NONEMPTY_CLIP=${landed ? "YES" : "NO"}`);
console.log(`VERDICT_DIR=${dir}`);

rmSync(dir, { recursive: true, force: true });
console.log("DONE");
process.exit(landed ? 0 : 1);