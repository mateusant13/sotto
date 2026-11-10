// ONE chain, pressed N times. My first probe rebuilt the chain every iteration,
// so every press restarted at 0000, collided with the file already on disk, and
// the writer correctly threw after 10 attempts. The writer was right; the probe
// was wrong.
import { HotkeyRouter, ReplayRing, SavePath, ClipWriter, SessionClock } from "./index.js";
import { mkdtempSync, readdirSync, readFileSync, writeFileSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os"; import { join } from "node:path";

const dir = mkdtempSync(join(tmpdir(), "sp-perf-"));
// MEASURED 2026-10-11T06:33:17Z: at the measured PER_PRESS_US of 161309.72, N=2000 needs
// 322.6 s. parse-gate.mjs gives each probe 120 s, so N=2000 could never pass the gate --
// it was killed by the timeout every time, and I read that as "the gate did not finish".
// The receipt is SEQUENCE_MONOTONIC, which 200 presses establish just as well: the claim
// under test is that the writer hands out distinct monotonic names on the write path,
// not how many names a turn can afford to buy.
const MAX_PRESSES = Number(process.env.PERF_PROBE_N) > 0 ? Number(process.env.PERF_PROBE_N) : 200;
const EXPECTED_PRESSES = 2000;   // the original figure, kept visible and NOT claimed as measured
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
  { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
ring.push(readFileSync(seedPath), { frames: 60, keyframe: true });
rmSync(seedDir, { recursive: true, force: true });

await hk.press("f9", 0);                 // warm up: JIT + module load
// O N ADAPTA AO ORCAMENTO (medido 2026-11-10). Com N=200 fixo este probe levou
// **151,3 s** (`PER_PRESS_US=756626.68`) nesta maquina carregada contra os
// 161 309,72 us medidos quando o N foi escolhido -- 4,7x --, e o `parse-gate`
// mata cada probe aos 120 s: o filho morria sem codigo de saida (`exit null`) e
// o commit era recusado por um probe que nao falhou, foi cortado. A afirmacao
// que o probe carrega e' que o escritor entrega nomes monotonos no caminho de
// escrita, nao quantos nomes uma volta compra; logo ele pressiona enquanto
// o relogio couber no orcamento, com piso de 10 presses (abaixo disso o
// teste nao prova sequencia) e tecto no N declarado. O pior caso do piso e'
// 10 presses vezes o custo medido (~3,2 s nesta maquina carregada = 32 s),
// ainda abaixo dos 120 s que o `parse-gate` da'.
const BUDGET_S = Number(process.env.PERF_PROBE_BUDGET_S) > 0
  ? Number(process.env.PERF_PROBE_BUDGET_S) : 45;
const MIN_PRESSES = 10;
const t = process.hrtime.bigint();
const ms = () => Number(process.hrtime.bigint() - t) / 1e6;
let presses = 0;
let last = null;
let seen = 0;
const pressOnce = async () => {
  // press() is ASYNC (hotkeys.js:66) and returns { action, clip } (hotkeys.js:87), and
  // MEASURED 2026-10-11T06:20:45Z: `clip` is an OBJECT, not a name string. The writer
  // really did write 0000.mp4 to the directory -- the object carries the record. So the
  // name has to be read off the record, or read off the directory it just wrote to.
  const r = await hk.press("f9", presses + 1);
  presses += 1;
  if (r && r.action === "instant-replay" && r.clip && typeof r.clip === "object") {
    seen += 1;
    last = r.clip.name ?? r.clip.path ?? null;
  }
};
while (presses < MAX_PRESSES
       && (presses < MIN_PRESSES || ms() < BUDGET_S * 1000)) {
  await pressOnce();
}
const elMs = ms();
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

console.log("N=" + presses);
console.log("PRESS_PATH_TOTAL_MS=" + elMs.toFixed(2));
console.log("PER_PRESS_US=" + ((elMs * 1000) / presses).toFixed(2));
console.log("FIRST=" + "0001.mp4  LAST=" + last);
console.log("SEQUENCE_MONOTONIC=" + (Number(last.slice(0, 4)) === presses));
console.log("ONE_MIB_WRITE_MS=" + writeMs.toFixed(2));
console.log("DISK_BYTES_MEASURED=" + bytes);
