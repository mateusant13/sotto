// ONE chain, pressed N times. My first probe rebuilt the chain every iteration,
// so every press restarted at 0000, collided with the file already on disk, and
// the writer correctly threw after 10 attempts. The writer was right; the probe
// was wrong.
import { HotkeyRouter, ReplayRing, SavePath, ClipWriter, SessionClock } from "./index.js";
import { mkdtempSync, readdirSync, readFileSync, writeFileSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os"; import { join } from "node:path";

const dir = mkdtempSync(join(tmpdir(), "sp-perf-"));
const N = 2000;
// ClipWriter needs a dir. Constructed with only { exists } it holds no directory, so the
// first writeClip throws "this ClipWriter has no directory" from clip-writer.js:116. The
// probe was written against an older constructor; the product is right.
const writer = new ClipWriter({ dir, exists: (n) => readdirSync(dir).includes(n) });
const path = new SavePath({ writer });
const ring = new ReplayRing({ minutes: 10, fps: 60, gopSize: 60, savePath: path });
const hk = new HotkeyRouter({ ring, debounceMs: 0 });

// The ring must hold something before instantReplay can cut. An EMPTY ring is refused
// by the product -- correctly, with a named RangeError from replay-ring.js:213 -- and a
// probe that dies on that refusal was measuring nothing about performance. Seed it with
// one real IDR-aligned clip, the same fixture replay-ring.test.mjs:26 builds.
import { execFileSync, spawnSync } from "node:child_process";
const seedDir = mkdtempSync(join(tmpdir(), "sp-seed-"));
const seedPath = join(seedDir, "seed.mp4");
execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
  "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "30", seedPath],
  { stdio: ["ignore", "pipe", "pipe"] });
ring.push(readFileSync(seedPath), { frames: 60, keyframe: true });
rmSync(seedDir, { recursive: true, force: true });

await hk.press("f9", 0);                 // warm up: JIT + module load
const t = process.hrtime.bigint();
let last = null;
let seen = 0;
for (let i = 0; i < N; i++) {
  // press() is ASYNC (hotkeys.js:66) and returns { action, clip } (hotkeys.js:87), and
  // MEASURED 2026-10-11T06:20:45Z: `clip` is an OBJECT, not a name string. The writer
  // really did write 0000.mp4 to the directory -- the object carries the record. So the
  // name has to be read off the record, or read off the directory it just wrote to.
  const r = await hk.press("f9", i + 1);
  if (r && r.action === "instant-replay" && r.clip && typeof r.clip === "object") {
    seen += 1;
    last = r.clip.name ?? r.clip.path ?? null;
  }
}
const elMs = Number(process.hrtime.bigint() - t) / 1e6;
// The receipt is what the directory holds, not what the return value claimed.
const written = readdirSync(dir).filter((n) => /^\d{4}\.mp4$/.test(n));
last = written.sort().at(-1) ?? null;
if (last === null) {
  console.error("perf-probe: no press() wrote a clip name -- the measurement below would be meaningless");
  process.exit(3);
}

writeFileSync(join(dir, last), Buffer.alloc(1024 * 1024));   // 1 MiB real write
const tWrite = process.hrtime.bigint();
writeFileSync(join(dir, "perf-last.mp4"), Buffer.alloc(1024 * 1024));
const writeMs = Number(process.hrtime.bigint() - tWrite) / 1e6;

const bytes = readdirSync(dir).reduce((a, n) => a + statSync(join(dir, n)).size, 0);
rmSync(dir, { recursive: true, force: true });

console.log("N=" + N);
console.log("PRESS_PATH_TOTAL_MS=" + elMs.toFixed(2));
console.log("PER_PRESS_US=" + ((elMs * 1000) / N).toFixed(2));
console.log("FIRST=" + "0001.mp4  LAST=" + last);
console.log("SEQUENCE_MONOTONIC=" + (Number(last.slice(0, 4)) === N));
console.log("ONE_MIB_WRITE_MS=" + writeMs.toFixed(2));
console.log("DISK_BYTES_MEASURED=" + bytes);
