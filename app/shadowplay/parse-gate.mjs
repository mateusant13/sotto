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
// 2026-10-11T10:23Z. Three probes added today take clip files as arguments and exited 2
// under the gate, which runs every script in its population with no arguments at all. These
// builders give them inputs the same way buildAnnexB() does for _nonidr-probe.
// good.mp4's first keyframe is at pts 0; bad.mp4's is at pts 1.0 because it is cut with
// -copyts, so the keyframe keeps its original timestamp instead of renormalising to zero.
let _gb = null;
function buildGoodBad() {
  if (_gb) return _gb;
  const d = mkdtempSync(join(tmpdir(), "gate-gb-"));
  const good = join(d, "good.mp4"), bad = join(d, "bad.mp4");
  const ff = (a) => { try { spawnSync("ffmpeg", ["-v", "error", "-y", ...a], { timeout: 60000 }); } catch { /* the probe reports what it could not read */ } };
  ff(["-f", "lavfi", "-i", "testsrc=s=640x360:r=30:d=4", "-c:v", "h264_nvenc", "-preset", "p1", "-g", "30", good]);
  ff(["-ss", "1.5", "-i", good, "-c", "copy", "-copyts", "-avoid_negative_ts", "disabled", bad]);
  _gb = existsSync(good) && existsSync(bad) ? [good, bad] : [];
  return _gb;
}
let _busy = null;
function buildBusy() {
  if (_busy) return _busy;
  const d = mkdtempSync(join(tmpdir(), "gate-busy-"));
  const out = join(d, "busy.mp4");
  try {
    spawnSync("ffmpeg", ["-v", "error", "-y", "-f", "lavfi",
      "-i", "testsrc=s=640x360:r=30:d=2", "-c:v", "h264_nvenc", "-preset", "p1", "-g", "60", out], { timeout: 60000 });
  } catch { /* same */ }
  _busy = existsSync(out) ? [out] : [];
  return _busy;
}

const ARGV_FOR = {
  "_nonidr-probe.mjs": [buildAnnexB()],
  "clip-not-keyframed-probe.mjs": buildGoodBad(),
  "stored-keyframe-arm-probe.mjs": buildGoodBad(),
  "still-screen-probe.mjs": buildBusy(),
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
  // The five probes added on 2026-10-11 joined the population by filename convention
  // (POPULATION is a readdirSync filter on "-probe.mjs", not a hand-kept list) while every
  // commit was bypassing the gate with SOTTO_SKIP_RUN_ALL=1. MEASURED 10:18:17Z, POPULATION
  // 9 probes: RESULT 4 passed, 5 refused, GATE_EXIT 1 -- three of the five exiting 2 because
  // the gate passed no arguments, and two declaring no receipts at all. Declared here.
  "keyframe-shape-probe.mjs": [
    "CAPTURED_FRAMES ", "FIRST_IDR_SEC ", "RING_SEGMENTS ", "LONGEST_UNIQUE_RUN ",
    "EXPECTED_FRAMES ", "CONTENT_SUFFICIENT ", "THREW ", "DONE",
  ],
  "loaded-module-probe.mjs": [
    "RESOLVED_BY_RUNTIME ", "SHA_RUNTIME_FILE ", "SHA_EDITED_FILE ", "SAME_BYTES ",
    "EXPORTED_FROM_INDEX ", "DONE",
  ],
  "still-screen-probe.mjs": [
    "FILE ", "DELIVERED_FRAMES ", "DISTINCT_FRAMES ", "LONGEST_UNIQUE_RUN ",
    "EXPECTED_FRAMES ", "CONTENT_SUFFICIENT ", "DONE",
  ],
  "clip-not-keyframed-probe.mjs": [
    "TOLERANCE_SEC ", "FIRST_IDR_SEC ", "GUARD_WOULD_REFUSE ", "DONE",
  ],
  "stored-keyframe-arm-probe.mjs": ["ARM ", "OUTCOME ", "FILES_LEFT_AFTER ", "DONE"],
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
// MEASURED 2026-10-11T08:43:58Z / 08:44:25Z, POPULACAO = the exact output of each
// probe run twice today (cw and perf at 08:43:58Z, _nonidr at 08:44:25Z against the
// same ffmpeg-built 14526 B annex-B stream). These are the keys whose value carries a
// TRUTH, so their value is asserted, not merely their presence:
//   cw-probe      BYTES_LANDED=YES             -- the whole point of the probe: if the
//                  ClipWriter stops landing bytes, this flips to NO and the gate refuses.
//   perf-probe    SEQUENCE_MONOTONIC=true      -- session-clock names must sort
//                  chronologically; a clock that reissued a value would print false.
//   _nonidr-probe NEGATIVE_ARM_REACHABLE: false -- a stream whose first picture is not
//                  an IDR is undecodable BY CONSTRUCTION, so the negative arm cannot be
//                  reached. Stable across two runs 2h05m apart; if the stripper ever
//                  made it reachable, this flips to true and the gate refuses.
// compose-probe was already here: PRODUCT_LANDS_A_NONEMPTY_CLIP=YES.
const VALUED = {
  "compose-probe.mjs": { "PRODUCT_LANDS_A_NONEMPTY_CLIP=": "YES" },
  "cw-probe.mjs": { "BYTES_LANDED=": "YES" },
  "perf-probe.mjs": { "SEQUENCE_MONOTONIC=": "true" },
  "_nonidr-probe.mjs": { "NEGATIVE_ARM_REACHABLE: ": "false" },
  // Added 2026-10-11T10:23Z for the five probes admitted that day. Three of them have a
  // deterministic boolean once the gate supplies their inputs, and those are asserted here
  // rather than merely counted as printed. MEASURED on the clean run at 10:23:11Z, over
  // POPULATION 9.
  //   keyframe-shape-probe  a busy desktop gives CONTENT_SUFFICIENT true and FIRST_IDR 0
  //   loaded-module-probe   the runtime's resolved file and the file by path hash alike
  //   still-screen-probe    the moving clip covers its clock
  // clip-not-keyframed-probe and stored-keyframe-arm-probe used to be ABSENT from VALUED,
  // on grounds this file itself recorded: each prints true and false across its two arms, so
  // "no single expected value can describe them and pinning one would make the gate pass on
  // half of what it sees". MEASURED 2026-10-11T10:49:43Z, POPULATION 9: 7 probes compared a
  // truth, 2 compared presence only.
  //
  // That reasoning is correct about the ARM-WISE keys and wrong about the claim. The claim is
  // not "the good arm printed false" -- it is "the arms DISAGREE", which is single-valued.
  // MEASURED 2026-10-11T10:51:30Z: both probes now emit one derived boolean each, built from
  // the values they measured, and the arm-wise lines stay free to print whatever is true.
  // Pinning ARMS_DISAGREE cannot pass on half the output: it is true only when the two arms
  // differ, so a probe whose arms collapsed to the same value prints false and this gate
  // refuses. That is the arm a gate that cannot say NO would not have.
  "clip-not-keyframed-probe.mjs": { "ARMS_DISAGREE ": "true" },
  "stored-keyframe-arm-probe.mjs": {
    "ARMS_DISAGREE ": "true",
    "NEGATIVE_ARM_REFUSED ": "true",
    "NEGATIVE_ARM_LEFT_NO_FILE ": "true",
  },
  "keyframe-shape-probe.mjs": { "CONTENT_SUFFICIENT ": "true", "FIRST_IDR_SEC ": "0" },
  "loaded-module-probe.mjs": { "SAME_BYTES ": "true" },
  "still-screen-probe.mjs": { "CONTENT_SUFFICIENT ": "true" },
};

// O ORCAMENTO POR PROBE, MEDIDO. O timeout era 120 s para TODOS, e o
// `perf-probe.mjs` faz 200 pressoes -- MEDIDO 2026-10-19 a 1 156 ms cada
// numa maquina carregada, ou seja 231 s. Um probe que passa por 120 s nao e'
// "um probe que falhou": e' um probe que o ORCAMENTO matou, e o gate dizia
// "perf-probe.mjs FAILED exit null" sem dizer porquê.
//
// E o proprio autor deste gate ja tinha escrito o sintoma, na nota do
// `--repeat`: *"the same tree gave 3 passed / 1 refused on one commit and 4
// passed / 0 refused six minutes later, with no change in between"*. O que
// variava era a CARGA, e o que estou a medir agora e' o mesmo fenomeno
// pelo outro lado: o probe e' legitimo, o orcamento e' que nao acompanha.
//
// A mudanca NAO e' afrouxar o gate: o probe continua a ter de imprimir as
// chaves de recibo e a sair com 0. O que muda e' o orcamento, que passa a ser
// medido por probe em vez de um numero unico que nao serve para nenhum.
const PROBE_TIMEOUT_MS = 120000;
const PROBE_TIMEOUT_MS_OVERRIDE = {
  // MEDIDO 2026-10-19: 231 s isolado (200 pressoes x 1 156 ms), com a maquina
  // a 93 % de carga. 600 s da folga sobre isso -- com 2,6x, para o dia em que
  // a maquina estiver mais carregada ainda.
  "perf-probe.mjs": 600000,
};

function classify(script) {
  const r = spawnSync(process.execPath, [join(HERE, script), ...(ARGV_FOR[script] || [])], {
    cwd: HERE, encoding: "utf8",
    timeout: PROBE_TIMEOUT_MS_OVERRIDE[script] || PROBE_TIMEOUT_MS,
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
    // HARDENED 2026-10-11T08:56Z. This used to be `!out.includes(k + want)`, which asks
    // "does the wanted value appear SOMEWHERE", not "is every value the wanted one".
    // MEASURED 2026-10-11T08:49:37Z, POPULACAO = 1 probe, the real counterexample: I
    // injected console.log("SEQUENCE_MONOTONIC=false") into perf-probe.mjs at the COMMENT
    // line 13 instead of the print at line 76, so the probe printed false AND true. The
    // old check found `SEQUENCE_MONOTONIC=true` somewhere and returned PASS. The probe
    // was self-contradictory and the gate called it clean.
    //
    // Now: collect EVERY value this key was printed with, and require that the key was
    // printed at least once and that every single occurrence equals the wanted value. A
    // probe that contradicts itself once can no longer pass.
    const wrong = Object.entries(valued).filter(([k, want]) => {
      const re = new RegExp(k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "([^\\r\\n]*)", "g");
      const seen = [...out.matchAll(re)].map((m) => m[1].trim());
      if (seen.length === 0) return true;               // never printed -> not a receipt
      return seen.some((v) => v !== want);              // any contradicting copy -> RED
    });
    if (wrong.length > 0) {
      // Show the DISTINCT values the key actually carried, not the first match.
      // MEASURED 2026-10-11T08:56:01Z: the probe printed YES, NO and YES again, and this
      // receipt used to print only the first occurrence -- "BYTES_LANDED=YES" -- which
      // reads as "the value was wrong" when the value was fine and the problem was the
      // extra NO beside it. A receipt that misdescribes its own reason is worse than none.
      const got = wrong.map(([k, want]) => {
        const re = new RegExp(k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(\\S*)", "g");
        const distinct = [...new Set([...out.matchAll(re)].map((m) => m[1]))];
        return `${k}${distinct.join(" | ")} (wanted ${want})`;
      });
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

// DURABLE RECORD, added 2026-10-11T09:06Z. The refusal of 07:14 is unrecoverable because
// nothing here kept the output: the verdict went to a terminal that had scrolled away, and
// the commit that triggered it never happened, so there was no second record either. A
// gate that cannot say WHY it said NO last time is a gate that will be re-diagnosed from
// scratch every time one refuses. Every run now appends its whole verdict, dated.
import { mkdirSync as _gateMk, appendFileSync as _gateAppend } from "node:fs";
try {
  const _logDir = join(HERE, "state", "gate");
  _gateMk(_logDir, { recursive: true });
  _gateAppend(join(_logDir, "gate-log.txt"), [
    `GATE_RUN ${new Date().toISOString()}`,
    `  POPULATION ${POPULATION.length} probe scripts`,
    `  RED_ARM refused=${arm.refused}`,
    ...rows.map(([s, v, why]) => `  ${s.padEnd(20)} ${v.padEnd(10)} ${why}`),
    `  RESULT ${passed} passed, ${refused} refused`,
    `  GATE_EXIT ${refused === 0 ? 0 : 1}`,
    "",
  ].join("\n") + "\n");
} catch { /* recording evidence must never change the verdict */ }

process.exit(refused === 0 ? 0 : 1);