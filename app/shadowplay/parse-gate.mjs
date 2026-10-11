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
const RECEIPTS = {
  "perf-probe.mjs": ["N=", "PRESS_PATH_TOTAL_MS=", "PER_PRESS_US=", "SEQUENCE_MONOTONIC="],
};

const STALE_API = [
  /ERR_INVALID_ARG_TYPE/, /is not a function/, /is not defined/,
  /ReferenceError/, /TypeError \[ERR_/, /Cannot read propert/,
];

function classify(script) {
  const r = spawnSync(process.execPath, [join(HERE, script)], {
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
    if (printed.length === keys.length) return { verdict: "PASS", why: `exit 0 and all ${keys.length} receipt keys printed`, printed };
    return { verdict: "SILENT", why: `exit 0 but ${printed.length}/${keys.length} receipt keys printed -- it measured nothing recognisable`, printed };
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

const WINDOW = new Date().toISOString().replace(/\.\d+Z$/, "Z");
console.log(`PARSE GATE  WINDOW_UTC ${WINDOW}  POPULATION = ${POPULATION.length} probe scripts`);

const arm = redArm();
console.log(`  RED ARM (deliberately stale script, ${arm.bytes} B): exit=${arm.status} refused=${arm.refused}`);
if (!arm.refused) {
  console.log("  GATE_BROKEN: the red arm was accepted. This gate cannot say NO and proves nothing.");
  process.exit(2);
}

let refused = 0, passed = 0;
const rows = [];
for (const s of POPULATION) {
  if (!existsSync(join(HERE, s))) { rows.push([s, "MISSING", "not on disk"]); refused++; continue; }
  const c = classify(s);
  rows.push([s, c.verdict, c.why]);
  if (c.verdict === "PASS") passed++; else refused++;
  console.log(`  ${s.padEnd(20)} ${c.verdict.padEnd(10)} ${c.why}`);
}
console.log(`  RESULT ${passed} passed, ${refused} refused`);
// The gate's own exit code is its verdict: any refused script fails the gate.
process.exit(refused === 0 ? 0 : 1);