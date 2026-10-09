// run-gates.mjs - the CALLER for the gates in this package.
//
// WHY THIS FILE EXISTS. The gate-melhor written on 2026-10-05
// (check-subagent-limit.mjs) was, on its own, a document: correct, self-tested,
// RED for the right reason, and invoked by nothing. A gate with no caller is
// the exact defect its own README names about `self-audit-lint.sh` - "an oracle
// with no caller is a document, not a gate". This file is the caller.
//
// IT ALSO DISCHARGES THE rc-VERDICT LAW AT THE AGGREGATOR LEVEL, which is the
// non-obvious part. Node exits 1 on an uncaught exception, so a gate that CRASHED
// and a gate that found a RED are both rc=1. A caller that reported the second as
// the first would turn a crash into a false RED and teach everyone to ignore
// REDs. So a non-zero rc is only read as a VERDICT when the child also printed
// one; a child that died is labelled CRASH and never moves the aggregate to 1.
//
// THE FIRST VERSION OF THIS FILE WAS WRONG AND THE LABELS CAUGHT IT. It invoked
// every gate as a plain checker. Four of them are HOOKS: they read a payload from
// stdin, so with no payload they exited 0 having concluded nothing and printed no
// verdict. The SILENT label - "rc=0 but no verdict printed, a green that proves
// nothing" - is why that mistake could not pass unnoticed, and it is the reason
// the label exists. Hooks are now driven with a real payload on stdin and their
// verdict is read from the LEDGER they write, which is the only place it lands.
//
// TWO-SIDED PROBES, and the limit of them. A hook is only called live if it BOTH
// refuses a violating payload AND allows a benign one; refusing everything is
// also a broken gate. That pair is asserted only where a verified fixture exists,
// taken from each hook's own committed self-test - inventing a violating payload
// for a hook I have not measured would be a guess, and a guess in a liveness gate
// is worse than an honest gap. Where no fixture is held, the probe runs the benign
// payload only and the result is labelled SMOKE with the ledger verdict printed
// verbatim: no PASS and no RED is claimed for it. That is a limit, stated, not a
// hole papered over.
//
// BOUNDED, because an aggregator that can hang is worse than no aggregator: each
// child gets GATE_TIMEOUT_MS and is KILLED past it, and a killed child is
// TIMEOUT - never a pass.
//
// AGGREGATE RULE, and why it is not "any failure fails":
//   1  a gate concluded RED. A real red is open and must be visible.
//   2  no RED, but something could not be concluded. NOT a pass: this house's
//      rule is that a check which did not run is not green, so an unmeasurable
//      gate is never averaged into a 0.
//   0  only when every gate actually concluded a pass.
//
// EXIT CODES - an rc carries a VERDICT, never a CAUSE.
//   0  PASS       every gate concluded PASS.
//   1  RED        at least one gate concluded RED.
//   2  NO VERDICT nothing concluded RED, and at least one could not conclude.
//   3  NO VERDICT usage error.

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const GATE_TIMEOUT_MS = 20_000;

// A violating payload is only listed where it is COPIED from that hook's own
// committed self-test. Inventing one would be a guess, and a guess inside a
// liveness gate is worse than an honest gap.
//
// CORRECTION, 2026-10-05: the first version of this file declared
// open-items-execute and fleet-coverage fixture-less and degraded them to SMOKE.
// That was wrong, and wrong in the direction of under-claiming: both fixtures were
// ALREADY COMMITTED in the sibling selftests (open-items-execute arm A1, and this
// package's own fleet-coverage arm F1). I had run both suites green and then did
// not go and read the arms I had written. Both are now supplied verbatim, and
// both probes are two-sided.
const BENIGN = {
  // selftest-open-items.mjs arm A3, verbatim.
  "check-open-items.mjs": "Report.\n\n## OBSERVATIONS\n- claim: x\n  population: 3\n  window: 1h\n\nDoes your implementation meet the spec? YES - measured.",
  // selftest-open-items-execute.mjs arm A4, verbatim.
  "check-open-items-execute.mjs": "All done.\n\n## OBSERVATIONS\n- claim: x\n  population: 3\n  window: 1h\n\nDoes your implementation meet the spec? YES - measured.",
  "check-spec-line.mjs": "Report.\n\n## NOTES\n- measured on this host\n\nDoes your implementation meet the spec? YES - measured.",
  "check-fleet-coverage.mjs": "report body",
};
const VIOLATING = {
  // selftest-open-items.mjs arm A2, verbatim.
  "check-open-items.mjs": "Report.\n\n## NOT VERIFIED\n- several things I could not determine\n\nDoes your implementation meet the spec? YES.",
  // selftest-open-items-execute.mjs arm A1, verbatim - the red arm of that suite.
  "check-open-items-execute.mjs":
    "Landed 4 commits.\n\n## WHAT'S NEXT / WHAT I DID NOT DO\n- commit the remaining 407 tracked modifications\n- push the branch to the remote\n\nDoes your implementation meet the spec? YES.",
  "check-spec-line.mjs": "Report.\n\n## NOTES\n- no spec question anywhere in this report\n",
  // selftest-dispatch-role.mjs arm P2, verbatim - a real imperative order.
  "check-dispatch-role.mjs": "Edit the file at scripts/x.mjs",
  // check-self-audit-block.mjs arm "prose-only": prose that mentions the audit
  // without the field list, so it must still block.
  "check-self-audit-block.mjs": "# receipt\n\nI did self-audit this and it looks fine to me.\n\nDoes your implementation meet the spec? YES.",
  // Built by buildFleetFixture() below from selftest-fleet-coverage.mjs arm F1:
  // two goals in the turn, zero kind='subagent' lanes -> block, rc=1.
  "check-fleet-coverage.mjs": "__FLEET_FIXTURE__",
};

/**
 * Benign payloads, and the SHAPE each gate actually reads. Three shapes exist
 * because a Stop payload is not a PreToolUse payload: feeding
 * `check-dispatch-role.mjs` a last_assistant_message would make it read a
 * tool_input that was never sent, which is the SILENT trap this file already
 * fell into once.
 */
const SHAPES = {
  // PreToolUse on `task`. The seat is read-only and the brief orders a write.
  pretask: (msg, fx) => ({
    hook_event_name: "PreToolUse",
    tool_name: "task",
    tool_input: { agent_name: "scout", description: "read-only measurement", prompt: msg, run_in_background: false },
    session_id: fx ? fx.session : "rungates-probe",
  }),
  // SubagentStop on a receipt.
  subagent: (msg, fx) => ({ hook_event_name: "SubagentStop", session_id: fx ? fx.session : "rungates-probe", last_assistant_message: msg }),
  // Stop, the default shape.
  stop: (msg, fx) => ({ hook_event_name: "Stop", session_id: fx ? fx.session : "rungates-probe", last_assistant_message: msg }),
};
// Verbatim from check-self-audit-block.mjs's own arm "conforming-en", which is
// the AGENTS.md English spelling its suite says must be equally acceptable.
const CONFORMING_RECEIPT = [
  "## SELF-AUDIT",
  "- Protocols missing: none blocking",
  "- Extra verification: one cheap probe",
  "- New checkboxes: one, named and mechanical",
  "- Review by another subagent: skipped (orchestrator discretion, no second seat)",
  "- Confidence: HIGH on the root cause, LOW in process",
  "- What was NOT verified: the live process, needs a restart",
  "- **Gate-doubt**",
  "  - **verde-de-verdade:** the first green was constructed, not measured",
  "  - **falta-no-gate:** a cache that hides a route flip still passes",
  "  - **gate-melhor:** invert the gate rather than delete it",
].join("\n");

/**
 * The fleet fixture, built here with the same schema and rows as the F1 arm of
 * selftest-fleet-coverage.mjs, because the hook only fires when its database says
 * so. Built rather than borrowed: the committed suite builds its own, and a
 * caller that pointed at a live database would be asserting a RED about the
 * owner's real sessions.
 */
function buildFleetFixture(dir, goals) {
  const path = join(dir, "runtime-state.sqlite");
  const db = new DatabaseSync(path);
  db.exec(`
CREATE TABLE local_runtime_thread_goals (goal_id TEXT PRIMARY KEY, session_id TEXT, objective TEXT, status TEXT, created_at_ms INTEGER, updated_at_ms INTEGER);
CREATE INDEX idx_local_runtime_thread_goals_session ON local_runtime_thread_goals(session_id, created_at_ms);
CREATE TABLE local_runtime_background_tasks (task_id TEXT PRIMARY KEY, owner_session_id TEXT, kind TEXT, status TEXT, created_at_ms INTEGER, updated_at_ms INTEGER, ended_at_ms INTEGER);
CREATE INDEX idx_local_runtime_background_tasks_owner ON local_runtime_background_tasks(owner_session_id, created_at_ms, task_id);
CREATE TABLE local_runtime_session_agent_state (session_id TEXT, turn_id TEXT, turn_sequence INTEGER, updated_at_ms INTEGER);
CREATE TABLE local_runtime_message_rows (id INTEGER PRIMARY KEY, session_id TEXT, turn_id TEXT, created_at_ms INTEGER);
`);
  const S = "rungates-fleet-fixture", T = "turn_current", P = "turn_previous";
  const T0 = 1_700_000_000_000, START = T0 + 60_000;
  db.prepare("INSERT INTO local_runtime_session_agent_state (session_id,turn_id,updated_at_ms) VALUES (?,?,?)").run(S, T, START + 10_000);
  const msg = db.prepare("INSERT INTO local_runtime_message_rows (id,session_id,turn_id,created_at_ms) VALUES (?,?,?,?)");
  msg.run(1, S, P, T0); msg.run(2, S, P, T0 + 1_000); msg.run(3, S, T, START); msg.run(4, S, T, START + 5_000);
  const goal = db.prepare("INSERT INTO local_runtime_thread_goals (goal_id,session_id,objective,status,created_at_ms,updated_at_ms) VALUES (?,?,?,?,?,?)");
  for (let i = 0; i < goals; i += 1) {
    goal.run("g" + i, S, "objective " + i, "completed", START + 1_000 + i * 1_000, START + 1_000 + i * 1_000);
  }
  db.close();
  return { dbPath: path, session: S };
}

const GATES = [
  { file: "check-subagent-limit.mjs", kind: "checker", law: "the configured subagent ceiling is reachable, wired and named" },
  { file: "check-fleet-coverage.mjs", kind: "hook", law: "a turn with 2+ items and zero subagent lanes is refused" },
  { file: "check-open-items.mjs", kind: "hook", law: "an admitted debt is enumerated" },
  { file: "check-open-items-execute.mjs", kind: "hook", law: "a WHAT'S NEXT item is actually executed" },
  { file: "check-spec-line.mjs", kind: "hook", law: "the report closes with the spec question answered" },
  { file: "check-dispatch-role.mjs", kind: "hook", shape: "pretask", law: "a read-only seat is never handed a file to write" },
  { file: "check-self-audit-block.mjs", kind: "hook", shape: "subagent", law: "a receipt closes with a conforming SELF-AUDIT field list" },
];

/**
 * Every `check-*.mjs` in this directory must be either a GATE or listed here with
 * a reason. The file this comment lives in shipped for two turns claiming to run
 * "every checker in this package" while silently omitting the PreToolUse deny and
 * the self-audit block - the two most consequential gates in the package. A gate
 * nobody runs is a document, and a gate that is forgotten by the caller is
 * exactly that, invisibly. The assertion below turns a future omission into a
 * visible NO-VERDICT instead of a quiet gap.
 */
const NOT_GATES = {};

const USAGE =
  "usage: run-gates.mjs [--help] [--only <substring>]\n" +
  "  Runs every checker and hook in this package; returns one rc for the package.\n" +
  "  0 all concluded PASS | 1 a real RED is open | 2 something could not be\n" +
  "  concluded | 3 usage. A child that dies or overruns is CRASH / TIMEOUT and\n" +
  "  never becomes a RED, because node exits 1 on an uncaught exception.";

const PASS_VERDICTS = new Set(["COMPLIANT", "CLEAN", "PASS"]);
const RED_VERDICTS = new Set([
  "VIOLATION",
  // check-self-audit-block.mjs names its reds rather than sharing VIOLATION.
  "SELF-AUDIT-MISSING", "SELF-AUDIT-FIELDS-MISSING", "GATE-DOUBT-MISSING", "GATE-DOUBT-SHALLOW",
]);
const UNDECIDED = new Set(["NOVALUE", "NO-VERDICT", "EXEMPT", "SELF-AUDIT-NO-VERDICT", "SELF-AUDIT-SCAN-UNREADABLE", ""]);

/** The last ledger record a hook wrote, or null. Hooks put their verdict here. */
function lastLedgerVerdict(dataDir) {
  try {
    const lines = readFileSync(join(dataDir, "invocations.jsonl"), "utf8").trim().split("\n").filter(Boolean);
    if (lines.length === 0) return null;
    return JSON.parse(lines[lines.length - 1]).verdict ?? null;
  } catch {
    return null;
  }
}

function spawnGate(gate, payload, extraEnv) {
  const dataDir = mkdtempSync(join(tmpdir(), "rungates-"));
  const r = spawnSync(process.execPath, [join(HERE, gate.file)], {
    encoding: "utf8",
    input: gate.kind === "hook" ? JSON.stringify(payload) : undefined,
    env: { ...process.env, PLUGIN_DATA: dataDir, ...(extraEnv || {}) },
    timeout: GATE_TIMEOUT_MS,
    killSignal: "SIGKILL",
  });
  const verdict = gate.kind === "hook" ? lastLedgerVerdict(dataDir) : readPrintedVerdict(r.stdout);
  try { rmSync(dataDir, { recursive: true, force: true }); } catch { /* scratch */ }
  return { rc: r.status, verdict, stderr: String(r.stderr || ""), stdout: String(r.stdout || "") };
}

function readPrintedVerdict(stdout) {
  const m = /(?:^|\n)\s*verdict:\s*(.+?)\s*(?:\n|$)/.exec(String(stdout || ""));
  return m ? m[1].trim() : null;
}

/** Turn one spawn into a label. A missing verdict with a non-zero rc is a CRASH. */
function label(r) {
  if (r.stderr.includes("ETIMEDOUT")) return "TIMEOUT";
  const v = r.verdict;
  if (v === null) {
    return r.rc === 0 ? "SILENT" : "CRASH";
  }
  if (PASS_VERDICTS.has(v)) return r.rc === 0 ? "PASS" : "RED";
  if (RED_VERDICTS.has(v)) return "RED";
  if (UNDECIDED.has(v)) return "NO-VERDICT";
  return "RED";
}

function probe(gate) {
  const scratch = mkdtempSync(join(tmpdir(), "rungates-fixture-"));
  const fleet = gate.file === "check-fleet-coverage.mjs";
  // SQLite will not create a missing DIRECTORY, and the benign fixture needs a
  // second one. The first version of this line crashed the whole caller with
  // ERR_SQLITE_ERROR on exactly that omission.
  const benignDir = scratch + "-benign";
  mkdirSync(benignDir, { recursive: true });
  // The fleet gate reads a DATABASE, so both of its probes get a fixture and the
  // caller's verdict never depends on the owner's live sessions. goals=2 is arm
  // F1 (must refuse); goals=1 is arm F5 (must allow). No lane rows either way.
  const violFixture = fleet ? buildFleetFixture(scratch, 2) : null;
  const benFixture = fleet ? buildFleetFixture(benignDir, 1) : null;
  const payload = (msg, fx) => (SHAPES[gate.shape || "stop"])(msg, fx);
  const env = (fx) => (fx ? { MCO_DGUARD_DB: fx.dbPath } : {});

  const benignMsg = gate.file === "check-self-audit-block.mjs" ? CONFORMING_RECEIPT : (BENIGN[gate.file] || "report body");
  const benign = spawnGate(gate, payload(benignMsg, benFixture), env(benFixture));
  const bLabel = label(benign);

  const vMsg = VIOLATING[gate.file];
  if (vMsg === null || vMsg === undefined) {
    return {
      label: bLabel === "PASS" || bLabel === "RED" ? "SMOKE" : bLabel,
      detail: "no verified violating fixture held, so no RED claim is made",
      rc: benign.rc, verdict: null,
      probes: { benign: `${bLabel} (ledger=${benign.verdict})` },
    };
  }
  const viol = spawnGate(gate, payload(vMsg, violFixture), env(violFixture));
  const vLabel = label(viol);
  const ok = vLabel === "RED" && bLabel === "PASS";
  try { rmSync(scratch, { recursive: true, force: true }); } catch { /* scratch */ }
  try { rmSync(benignDir, { recursive: true, force: true }); } catch { /* scratch */ }
  return {
    label: ok ? "PASS" : "RED",
    detail: ok
      ? "refuses the violating payload and allows the benign one - two-sided, so it is neither dead nor a nuisance"
      : "two-sided FAILED - a gate that refuses everything is as broken as one that refuses nothing",
    rc: viol.rc, verdict: null,
    probes: { violating: `${vLabel} (ledger=${viol.verdict})`, benign: `${bLabel} (ledger=${benign.verdict})` },
  };
}

function main() {
  const argv = process.argv.slice(2);
  if (argv.includes("--help") || argv.includes("-h")) { process.stdout.write(USAGE + "\n"); process.exit(0); }
  const onlyIdx = argv.findIndex((a) => a === "--only" || a.startsWith("--only="));
  if (onlyIdx >= 0 && !argv[onlyIdx].includes("=") && !argv[onlyIdx + 1]) {
    process.stderr.write("run-gates: USAGE ERROR: --only needs a substring\n" + USAGE + "\n");
    process.exit(3);
  }
  // The value that FOLLOWS `--only` must be consumed, or it is rejected as an
  // unknown option. Measured defect, found by using the tool: `--only subagent`
  // returned rc=3 "unknown option 'subagent'".
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--only") { i += 1; continue; }
    if (a.startsWith("--only=")) continue;
    process.stderr.write("run-gates: USAGE ERROR: unknown option '" + a + "'\n" + USAGE + "\n");
    process.exit(3);
  }
  const only = onlyIdx >= 0
    ? (argv[onlyIdx].includes("=") ? argv[onlyIdx].split("=").slice(1).join("=") : argv[onlyIdx + 1])
    : "";
  const gates = only ? GATES.filter((g) => g.file.includes(only)) : GATES;
  if (gates.length === 0) {
    process.stderr.write("run-gates: USAGE ERROR: --only '" + only + "' matched no gate\n" + USAGE + "\n");
    process.exit(3);
  }

  process.stdout.write(`run-gates: ${gates.length} gate(s) in ${HERE}\n\n`);

  // COVERAGE ASSERTION. Any check-*.mjs that is neither a GATE nor declared in
  // NOT_GATES is an unrun law. It cannot be allowed to pass quietly.
  const onDisk = readdirSync(HERE).filter((f) => /^check-.*\.mjs$/.test(f)).sort();
  const unaccounted = onDisk.filter((f) => !GATES.some((g) => g.file === f) && !(f in NOT_GATES));
  if (unaccounted.length > 0) {
    for (const f of unaccounted) {
      process.stdout.write(`  NO-VERDICT  ${f}\n             present but neither probed nor declared in NOT_GATES - an unrun law\n`);
    }
  }

  let sawRed = false;
  let unresolved = unaccounted.length;
  for (const g of gates) {
    if (!existsSync(join(HERE, g.file))) {
      unresolved += 1;
      process.stdout.write(`  NO-VERDICT  ${g.file}\n             not installed; the law was never asked\n`);
      continue;
    }
    // A gate that THROWS must be labelled CRASH, not be allowed to take the
    // process down: the whole point of this file is that a broken gate can never
    // be mistaken for a caught violation, and a crash that kills the caller
    // reports nothing at all - the reader is left with a half-printed table and
    // whatever rc the shell saw.
    let p;
    try {
      p = g.kind === "checker"
        ? (() => { const r = spawnGate(g, null, null); const l = label(r); return { label: l, detail: l === "SILENT" ? "rc=0 with no verdict line" : "", rc: r.rc, verdict: r.verdict }; })()
        : probe(g);
    } catch (err) {
      const m = err && err.message ? String(err.message).slice(0, 120) : "unknown";
      p = { label: "CRASH", detail: "the probe itself threw: " + m + " - reported as a crash, never as a RED", rc: 1, verdict: null };
    }
    if (p.label === "RED") sawRed = true;
    if (p.label !== "PASS" && p.label !== "RED") unresolved += 1;
    // For a two-sided PASS the rc shown is the VIOLATING probe's rc, which is 1
    // because the gate correctly refused. Printing that under a bare "rc=" beside
    // a PASS label reads like a contradiction, so it is named for what it is.
    const rcLabel = p.label === "PASS" && g.kind === "hook" ? "violating_probe_rc" : "rc";
    process.stdout.write(`  ${p.label.padEnd(10)} ${g.file}  ${rcLabel}=${p.rc}\n`);
    process.stdout.write(`             law: ${g.law}\n`);
    if (p.probes) {
      // Both verdicts, always named. Printing a single "verdict:" line beside a
      // PASS label is ambiguous when that verdict came from the violating probe -
      // and an ambiguous line in a gate a human reads to decide is a defect.
      for (const [k, v] of Object.entries(p.probes)) {
        process.stdout.write(`             probe ${k}: ${v}\n`);
      }
    } else if (p.verdict) {
      process.stdout.write(`             verdict: ${p.verdict}\n`);
    }
    if (p.detail) process.stdout.write(`             ${p.detail}\n`);
  }
  const agg = sawRed ? 1 : unresolved > 0 ? 2 : 0;
  const why = agg === 1 ? "at least one gate concluded RED" :
    agg === 2 ? `no RED, but ${unresolved} gate/probe could not conclude` :
    "every gate concluded PASS";
  process.stdout.write(`\naggregate: rc=${agg} (${why})\n`);
  process.stdout.write("note: CRASH and TIMEOUT are not REDs - a dead gate is never allowed to look like a caught violation.\n");
  process.exit(agg);
}

main();
