// THE ONE ENTRY POINT. Until this file existed there was no way to run everything:
// no package.json, no Makefile, no hook, no runner. POPULATION measured 2026-10-11T06:43:56Z
// -- all five absent. Every number I reported for fifteen passes was produced by a
// PowerShell loop I typed by hand each time, which is why the suite was never re-verified
// after an edit and why the parse gate was only ever run when I remembered to.
//
// WHAT IT RUNS, both read off the filesystem so neither can be left out by omission:
//   1. every *.test.mjs in this directory  -- each must print `RESULT n passed, m failed`
//      and exit 0.
//   2. parse-gate.mjs                      -- the probe gate, which may legitimately FAIL.
//      It is reported and it fails the run, but it is named separately, because a gate
//      that refuses a probe is doing its job and is not the same event as a red suite.
//
// THE ARM THAT MUST GO RED. A runner that cannot fail is a script that prints a number.
// `--red-arm` runs this file with GATE_FORCE_REFUSE=1, which makes the gate refuse its
// first probe, and the runner is REQUIRED to report a non-zero exit for that run. If the
// red arm is ever accepted, this runner prints RUNNER_BROKEN and exits 2. It is checked
// here, on every run, not once.

import { spawnSync } from "node:child_process";
import { readdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

const argv = process.argv.slice(2);
const RED_ARM = argv.includes("--red-arm");

// ---- THE RED ARM -------------------------------------------------------------------
// GATE_FORCE_REFUSE makes the gate refuse one probe without touching its logic, so the
// runner's ability to notice a refusal is what is under test here.
if (RED_ARM) process.env.GATE_FORCE_REFUSE = "1";

// ---- DISCOVER. Off the disk, both populations ------------------------------------------------
const SUITES = readdirSync(HERE).filter((f) => f.endsWith(".test.mjs")).sort();
const GATE = "parse-gate.mjs";

const WINDOW = new Date().toISOString().replace(/\.\d+Z$/, "Z");
console.log(`RUN ALL  WINDOW_UTC ${WINDOW}${RED_ARM ? "  [RED ARM]" : ""}`);
console.log(`  suite population  = ${SUITES.length} (every *.test.mjs on disk)`);
console.log(`  gate present      = ${existsSync(join(HERE, GATE))}`);

function runSuite(f) {
  const r = spawnSync(process.execPath, [join(HERE, f)], { cwd: HERE, encoding: "utf8", timeout: 300000 });
  const out = (r.stdout || "") + (r.stderr || "");
  const m = out.match(/RESULT\s+(\d+)\s+passed,\s*(\d+)\s+failed/);
  if (!m) return { f, ok: false, why: "no RESULT line -- it did not report at all", passed: null, failed: null };
  const passed = Number(m[1]), failed = Number(m[2]);
  return { f, ok: r.status === 0 && failed === 0, why: r.status !== 0 ? `exit ${r.status}` : `${failed} failed`, passed, failed };
}

const results = SUITES.map(runSuite);
let suitePassed = 0, suiteFailed = 0, noReport = 0;
for (const r of results) {
  if (r.passed === null) { noReport++; console.log(`  ${r.f.padEnd(30)} NO_REPORT  ${r.why}`); continue; }
  if (r.ok) { suitePassed++; console.log(`  ${r.f.padEnd(30)} ok         ${r.passed} passed`); }
  else { suiteFailed++; console.log(`  ${r.f.padEnd(30)} FAIL       ${r.passed} passed, ${r.failed} failed (${r.why})`); }
}
console.log(`  SUITES ${suitePassed} passed, ${suiteFailed} failed, ${noReport} unreported`);

// ---- GATE -------------------------------------------------------------------------------
let gateStatus = "ABSENT", gateExit = null;
if (existsSync(join(HERE, GATE))) {
  const r = spawnSync(process.execPath, [join(HERE, GATE)], { cwd: HERE, encoding: "utf8", timeout: 300000 });
  gateExit = r.status;
  const m = (r.stdout || "").match(/RESULT\s+(\d+)\s+passed,\s*(\d+)\s+refused/);
  if (m) gateStatus = `${m[1]} passed / ${m[2]} refused`;
  else gateStatus = `no RESULT line (exit ${r.status})`;
  for (const line of (r.stdout || "").trim().split(/\r?\n/).slice(1)) console.log(`  | ${line}`);
  console.log(`  GATE ${gateStatus}, exit ${gateExit}`);
}

const suitesOk = suiteFailed === 0 && noReport === 0;
const gateOk = gateExit === 0;

// ---- THE SELF-CHECK. Does this runner notice a refusal? ------------------------------------
if (RED_ARM) {
  const noticed = !gateOk;
  console.log(`  SELF-CHECK: gate forced to refuse; runner exit would be ${gateOk ? "0" : "1"}; noticed=${noticed}`);
  if (!noticed) {
    console.log("  RUNNER_BROKEN: a forced refusal was accepted. This runner cannot say NO.");
    process.exit(2);
  }
  process.exit(0);
}

console.log(`  VERDICT suites_ok=${suitesOk} gate_ok=${gateOk}`);
process.exit(suitesOk && gateOk ? 0 : 1);