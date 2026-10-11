// A PARSE GATE for the probe scripts, and the RED arm that proves the gate can fail.
//
// WHY THIS EXISTS. WINDOW_UTC 2026-10-11T06:03:50Z I measured three probe scripts:
//   compose-probe.mjs  18775 ms  exit 0
//   cw-probe.mjs          110 ms  exit 0
//   perf-probe.mjs         135 ms  exit 1
// and I reported that last one as failing. It was not failing for the reason anyone
// would assume. Its stack was ERR_INVALID_ARG_TYPE at perf-probe.mjs:22 -- `join(dir, last)`
// with `last === undefined`, because line 19 reads `hk.press("f9", i+1).clip` and press()
// no longer returns a `.clip`. The probe is STALE, not broken, and it had been stale
// long enough that its exit code looked like a verdict on the code under it.
//
// A script that exits 0 because it silently measured nothing is worse than one that
// exits 1 loudly. Neither is distinguishable from "the thing works" if all you read is
// the exit code. So this gate separates FOUR outcomes and refuses to pass on three.
//
//   exit 0 AND it printed its own receipt keys   -> PASS
//   exit 0 AND it printed nothing recognisable    -> SILENT, refused: measured nothing
//   exit 1 for a TypeError/ReferenceError/NameError -> STALE API, refused: the script
//       is talking to a signature that no longer exists
//   exit 1 for anything else                      -> REFUSED, and the reason is printed
//
// THE ARM THAT MUST FAIL. A gate that cannot say NO is decoration. The deliberately broken
// file below is written to disk, run, and MUST be refused -- and if it is ever accepted,
// this gate reports GATE_BROKEN and exits non-zero itself. That is checked on every run,
// not once.

import { spawnSync } from "node:child_process";
import { writeFileSync, mkdtempSync, rmSync, existsSync, statSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

// POPULATION = every probe script in this tree, READ OFF THE FILESYSTEM.
// MEASURED 2026-10-11T06:08:03Z: a hand-written list gave the same 3 names, but a
// hand-written list is a claim that stops being true when a probe is added, and the
// gate would keep passing while missing it. So the directory decides, and this file
// only decides which FILES are probes. `*.test.mjs` is excluded because a test suite
// reports its own RESULT line and is governed by the suite runner, not by this gate.
const POPULATION = readdirSync(HERE)
  .filter((f) => f.endsWith("-probe.mjs") && !f.endsWith(".test.mjs"))
  .sort();

// What each probe is supposed to print. A script that emits none of its keys is SILENT.
// Declared per probe because a probe's receipt is its own contract; an empty list means
// "this probe declares no receipt", and that is reported as NO_CONTRACT rather than PASS,
// because "exit 0 and I did not check" is not evidence and must never read as one.
// ARGV. A probe is a program, not a script: some take an input file and cannot run
// without one. Calling those with no arguments reports ERR_INVALID_ARG_TYPE, which my
// STALE_API pattern happily matched -- so a correct probe read as obsolete.
//
// MEASURED 2026-10-11T06:37:46Z: _nonidr-probe.mjs reads process.argv[2] and dies on
// undefined. That is not a stale API call. It is an invocation the gate failed to make.
// Population of annex-B streams on this host: 0, so the gate BUILDS the input with
// ffmpeg rather than looking for one.
const ARGV_FOR = {
  "_nonidr-probe.mjs": [buildAnnexB()],
};

function buildAnnexB() {
  const d = mkdtempSync(join(tmpdir(), "annexb-"));
  const p = join(d, "in.h264");
  try {
    spawnSync("ffmpeg", ["-v", "error", "-y", "-f", "lavfi",
      "-i", "testsrc=s=320x240:rate=30:duration=2", "-c:v", "libx264",
      "-pix_fmt", "yuv420p", "-g", "30", "-bsf:v", "h264_mp4toannexb", "-f", "h264", p],
      { encoding: "utf8", timeout: 60000 });
    return existsSync(p) ? p : null;
  } catch { return null; } finally { /* the probe owns the dir; nothing to clean here */ }
}

// MEASURED 2026-10-11T06:31:44Z by reading the console.log calls out of each probe.
// Before this, both probes were NO_CONTRACT -- the gate refused them for being unproven,
// which was correct and useless: a receipt nobody declares can never be checked.
//
// compose-probe's contract is the falsifying pair ZERO_BYTE_CLIPS / PRODUCT_LANDS_A_NONEMPTY_CLIP:
// if the writer ever produces a zero-byte clip the second key flips to NO. That is the
// whole point of that probe and the gate now watches it.
// cw-probe's contract is BYTES_LANDED, plus AFTER_ABORT_bytes which is the refusal arm.
const RECEIPTS = {
  "compose-probe.mjs": [
    "WINDOW_UTC:", "COMPOSED_OK", "CLIP_FILES_ON_DISK=",
    "ZERO_BYTE_CLIPS=", "PRODUCT_LANDS_A_NONEMPTY_CLIP=", "DONE",
  ],
  "cw-probe.mjs": ["WINDOW_UTC:", "BYTES_LANDED=", "ZERO_BYTE_PAYLOAD=", "AFTER_ABORT_bytes=", "PROBE_DONE"],
  "perf-probe.mjs": ["N=", "PRESS_PATH_TOTAL_MS=", "PER_PRESS_US=", "SEQUENCE_MONOTONIC="],
  // MEASURED 2026-10-11T06:33:44Z. This probe rejoined the population when I restored the
  // eight deleted _*.mjs files from HEAD, and the gate found it STALE_API on its first
  // sight of it. That verdict was WRONG and the reason is the useful part: the probe
  // reads process.argv[2] and the gate was calling it with no arguments at all.
  //   Measured 06:39:24Z with a real 14526 B annex-B stream built by ffmpeg:
  //     NAL_UNITS_PARSED 65, IDR_COUNT 2, STRIPPED_BYTES 7946 of 14526,
  //     PAYLOAD_RETAINED_PCT 54.7, DECODABLE_FRAMES_NO_IDR 0,
  //     DECODABLE_FRAMES_WITH_IDR_CONTROL 60,
  //     NON_IDR_FIRST_STREAM_IS_UNDECODABLE true, NEGATIVE_ARM_REACHABLE false.
  //   The last key is the answer: a stream whose first picture is not an IDR is not
  //   decodable, so the negative arm for the IDR gate is unreachable BY CONSTRUCTION.
  //   That is a finding, not a defect, and it is why this probe earns a receipt.
  "_nonidr-probe.mjs": [
    "NAL_UNITS_PARSED:", "IDR_COUNT:", "STRIPPED_BYTES:", "PAYLOAD_RETAINED_PCT:",
    "DECODABLE_FRAMES_WITH_IDR_CONTROL:", "NEGATIVE_ARM_REACHABLE:",
  ],
};

const STALE_API = [
  /ERR_INVALID_ARG_TYPE/, /is not a function/, /is not defined/,
  /ReferenceError/, /TypeError \[ERR_/, /Cannot read propert/,
];

// A receipt key whose value is NO is not a receipt. MEASURED 2026-10-11T08:27:12Z:
// compose-probe prints PRODUCT_LANDS_A_NONEMPTY_CLIP=NO, CLIP_FILES_ON_DISK=0 and exits 0,
// and this gate reported PASS because it only asked whether the key PRINTED. Every "4/4
// clean" in the ledger until now was evidence that keys appeared, not that the product
// did what they claim. Keys whose value can be YES/NO are COMPARED below.
const VALUED = {
  "compose-probe.mjs": { "PRODUCT_LANDS_A_NONEMPTY_CLIP=": "YES" },
};

function classify(script) {
  const r = spawnSync(process.execPath, [join(HERE, script), ...(ARGV_FOR[script] || [])], {
    cwd: HERE, encoding: "utf8", timeout: 120000,
  });
  const out = (r.stdout || "") + (r.stderr || "");
  const keys = RECEIPTS[script] || [];
  const printed = keys.filter((k) => out.includes(k));
  const errorLine = (out.split(/\r?\n/).find((l) => /Error|error:/.test(l)) || "").trim();

  if (r.status === 0) {
    if (keys.length === 0) {
      // Exit 0 with no declared receipt is UNKNOWN, not a pass. Reporting it as PASS
      // would make the gate agree with any script that prints nothing, which is the
      // failure this whole file exists to prevent.
      return { verdict: "NO_CONTRACT", why: "exit 0 but this probe declares no receipt keys, so there is nothing to check -- unproven, not proven", printed: [] };
    }
    if (printed.length < keys.length) {
      return { verdict: "SILENT", why: `exit 0 but ${printed.length}/${keys.length} receipt keys printed -- it measured nothing recognisable`, printed };
    }
    // Every key printed. NOW compare the ones that carry a truth value.
    const valued = VALUED[script] || {};
    const wrong = Object.entries(valued).filter(([k, want]) => !out.includes(k + want));
    if (wrong.length > 0) {
      const got = wrong.map(([k]) => (out.match(new RegExp(k.replace(/[=]/g, "\\=") + "\\S*")) || ["?"])[0]);
      return { verdict: "RECEIPT_FALSE", why: `all keys printed but ${got.join(", ")} -- the probe reported a failure and still exited 0`, printed };
    }
    return { verdict: "PASS", why: `exit 0, all ${keys.length} receipt keys printed${Object.keys(valued).length ? ", and " + Object.keys(valued).length + " truth-valued key(s) compared" : ""}`, printed };
  }
  if (STALE_API.some((re) => re.test(out))) {
    return { verdict: "STALE_API", why: `exit ${r.status} on a signature that no longer exists: ${errorLine.slice(0, 110)}`, printed };
  }
  return { verdict: "FAILED", why: `exit ${r.status}: ${errorLine.slice(0, 110)}`, printed };
}

// ---- THE RED ARM. Written to a temp dir, run, and MUST be refused. --------------------
function redArm() {
  const d = mkdtempSync(join(tmpdir(), "parse-gate-red-"));
  try {
    // Deliberately stale: calls a method the product does not have.
    const broken = join(d, "broken-probe.mjs");
    writeFileSync(broken, [
      'import { HotkeyRouter } from "file:///' + HERE.replace(/\\/g, "/") + '/index.js";',
      'const hk = new HotkeyRouter({});',
      'hk.pressThisDoesNotExist("f9");',
      'console.log("RECEIPT=pretend");',
    ].join("\n"), "utf8");

    const r = spawnSync(process.execPath, [broken], { encoding: "utf8", timeout: 60000 });
    const out = (r.stdout || "") + (r.stderr || "");
    const detected = STALE_API.some((re) => re.test(out));
    return { refused: r.status !== 0 && detected, status: r.status, bytes: statSync(broken).size };
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
}

// --repeat N runs the whole gate N times and reports the DISTRIBUTION, because a single
// run is a sample of size one. MEASURED 2026-10-11T07:14Z vs 07:20Z: the same tree gave
// 3 passed / 1 refused on one commit and 4 passed / 0 refused six minutes later, with no
// change in between. One 4/4 in a report is therefore not evidence of stability, it is
// one observation wearing the grammar of a guarantee.
// MEASURED 2026-10-11T07:32:58Z: the first version of this block sat ABOVE the `const
// WINDOW` declaration and every --repeat run died with ReferenceError: Cannot access
// 'WINDOW' before initialization, after spending minutes running all the probes first.
// The failure came last and the work before it was wasted, because the printout is the
// thing that makes the distribution legible. Declared here, before anything uses it.
const WINDOW = new Date().toISOString().replace(/\.\d+Z$/, "Z");

const argvAll = process.argv.slice(2);
const ri = argvAll.indexOf("--repeat");
const REPEAT = ri >= 0 ? Math.max(1, Number(argvAll[ri + 1]) || 1) : 1;

function verdictOnce() {
  let refused = 0, passed = 0;
  const detail = [];
  const forceRefuse = process.env.GATE_FORCE_REFUSE === "1";
  let first = true;
  for (const s of POPULATION) {
    if (!existsSync(join(HERE, s))) { detail.push(`${s}=MISSING`); refused++; continue; }
    const c = classify(s);
    if (forceRefuse && first) { first = false; detail.push(`${s}=FORCED`); refused++; continue; }
    first = false;
    detail.push(`${s}=${c.verdict}`);
    if (c.verdict === "PASS") passed++; else { refused++; detail.push(`${s}:${c.why}`); }
  }
  return { passed, refused, detail, exit: refused === 0 ? 0 : 1 };
}

if (REPEAT > 1) {
  const results = [];
  for (let i = 0; i < REPEAT; i++) results.push(verdictOnce());
  const clean = results.filter((r) => r.refused === 0).length;
  console.log(`PARSE GATE REPEAT  WINDOW_UTC ${WINDOW}  runs=${REPEAT}  population=${POPULATION.length}`);
  results.forEach((r, i) => console.log(`  run ${i + 1}: ${r.passed} passed, ${r.refused} refused${r.refused ? "  -> " + r.detail.filter((d) => d.includes(":")).join(" | ").slice(0, 150) : ""}`));
  console.log(`  DISTRIBUTION clean=${clean}/${REPEAT}  dirty=${REPEAT - clean}/${REPEAT}`);
  // A gate that is not stable is not a gate; report the instability as the failure.
  process.exit(clean === REPEAT ? 0 : 1);
}

console.log(`PARSE GATE  WINDOW_UTC ${WINDOW}  POPULATION = ${POPULATION.length} probe scripts`);

const arm = redArm();
console.log(`  RED ARM (deliberately stale script, ${arm.bytes} B): exit=${arm.status} refused=${arm.refused}`);
if (!arm.refused) {
  console.log("  GATE_BROKEN: the red arm was accepted. This gate cannot say NO and proves nothing.");
  process.exit(2);
}

let refused = 0, passed = 0;
const rows = [];
// GATE_FORCE_REFUSE exists for run-all.mjs --red-arm. It makes the gate refuse its first
// probe without touching the classification logic, so what is under test there is the
// RUNNER's ability to notice a refusal, not the gate's ability to produce one.
const forceRefuse = process.env.GATE_FORCE_REFUSE === "1";
let first = true;
for (const s of POPULATION) {
  if (!existsSync(join(HERE, s))) { rows.push([s, "MISSING", "not on disk"]); refused++; continue; }
  const c = classify(s);
  if (forceRefuse && first) {
    first = false;
    rows.push([s, "FORCED", "GATE_FORCE_REFUSE=1 -- this refusal is manufactured by run-all.mjs"]);
    refused++;
    console.log(`  ${s.padEnd(20)} ${"FORCED".padEnd(10)} manufactured refusal, run-all.mjs --red-arm`);
    continue;
  }
  first = false;
  rows.push([s, c.verdict, c.why]);
  if (c.verdict === "PASS") passed++; else refused++;
  console.log(`  ${s.padEnd(20)} ${c.verdict.padEnd(10)} ${c.why}`);
}
console.log(`  RESULT ${passed} passed, ${refused} refused`);
// The gate's own exit code is its verdict: any refused script fails the gate.
process.exit(refused === 0 ? 0 : 1);