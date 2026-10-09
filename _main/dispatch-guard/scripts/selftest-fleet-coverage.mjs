// selftest-fleet-coverage.mjs - proves check-fleet-coverage can go RED.
//
// EVERY ARM BUILDS ITS OWN DATABASE in a temp dir and points the hook at it with
// MCO_DGUARD_DB. The live 1.63 GB runtime database is never opened by a single
// arm, and never written: the fixture is a few hundred bytes of the same schema,
// so a red is reproducible in a second and cannot be blamed on the host's state.
//
// THE ARMS, and the defect each one pins:
//   F1  2 items, 0 lanes                     -> BLOCK   the law, firing
//   F2  goals table empty                    -> NO-VERDICT  absent data must not block
//   F3  database absent                     -> NO-VERDICT  absent data must not block
//   F4  2 items, 1 subagent lane this turn  -> PASS    the law, satisfied
//   F5  1 item, 0 lanes                     -> PASS    ONE indivisible item is not a
//                                                          parallelism failure (req. 4)
//   F6  2 items, 0 lanes, 300 lifetime lanes-> BLOCK   turn scoping: a lifetime count
//                                                          would be a permanent green
//   F7  2 items, 5 bash background tasks    -> BLOCK   kind filter: background bash is
//                                                          not fleet usage
//   F8  the 61 MB decoy path                -> NO-VERDICT  refused by NAME
//   F9  SubagentStop                        -> PASS    a leaf worker is the fleet working
//   F10 no turn anchor row                  -> NO-VERDICT  unguessable window, no block
//   F11 second Stop, same session           -> PASS    one-shot: a refusal cannot loop
//
// EXIT CODES - an rc carries a VERDICT, never a CAUSE.
//   0  PASS  every arm matched its wanted verdict, rc and ledger record.
//   1  RED   an arm mismatched.
//   2  RED   the fixture could not be built, or the hook file is absent.
//   3  NO VERDICT  usage error.

import { spawnSync } from "node:child_process";
import { DatabaseSync } from "node:sqlite";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const HOOK = join(here, "check-fleet-coverage.mjs");
const USAGE =
  "usage: selftest-fleet-coverage.mjs [--help]\n" +
  "  11 arms over the real hook process, each against its own temp SQLite fixture.\n" +
  "  0 all held, 1 an arm is red, 2 the fixture could not be built, 3 usage.\n" +
  "  The live runtime database is never opened by this file.";

if (process.argv.includes("--help") || process.argv.includes("-h")) {
  process.stdout.write(USAGE + "\n");
  process.exit(0);
}
for (const a of process.argv.slice(2)) {
  process.stderr.write("selftest-fleet-coverage: USAGE ERROR: unknown option '" + a + "'\n" + USAGE + "\n");
  process.exit(3);
}
if (!existsSync(HOOK)) {
  process.stderr.write("selftest-fleet-coverage: HOOK-ABSENT: " + HOOK + "\n");
  process.exit(3);
}

const SESSION = "mvs_selftest_root_session";
const TURN = "turn_current_turn";
const PREV_TURN = "turn_previous_turn";
const T0 = 1_700_000_000_000; // an arbitrary fixed epoch ms, so nothing depends on now()
const TURN_START = T0 + 60_000; // the current turn begins here

/** The subset of the live schema these queries touch, with its two real indexes. */
const SCHEMA = `
CREATE TABLE local_runtime_thread_goals (
  goal_id TEXT PRIMARY KEY, session_id TEXT, objective TEXT, status TEXT,
  created_at_ms INTEGER, updated_at_ms INTEGER);
CREATE INDEX idx_local_runtime_thread_goals_session ON local_runtime_thread_goals(session_id, created_at_ms);
CREATE TABLE local_runtime_background_tasks (
  task_id TEXT PRIMARY KEY, owner_session_id TEXT, kind TEXT, status TEXT,
  created_at_ms INTEGER, updated_at_ms INTEGER, ended_at_ms INTEGER);
CREATE INDEX idx_local_runtime_background_tasks_owner
  ON local_runtime_background_tasks(owner_session_id, created_at_ms, task_id);
CREATE TABLE local_runtime_session_agent_state (
  session_id TEXT, turn_id TEXT, turn_sequence INTEGER, updated_at_ms INTEGER);
CREATE TABLE local_runtime_message_rows (
  id INTEGER PRIMARY KEY, session_id TEXT, turn_id TEXT, created_at_ms INTEGER);
`;

/**
 * Build one fixture. `goals` and `tasks` are lists of
 *   { at, kind }      - created_at_ms relative to T0
 *   { at, kind, turn} - a task in a specific turn (defaults to the current one)
 * `anchor: false` omits the session_agent_state row, which is what makes the
 * turn window underivable.
 */
function buildFixture(dir, spec) {
  const path = join(dir, "runtime-state.sqlite"); // the basename is mandatory; see F8
  const db = new DatabaseSync(path);
  db.exec(SCHEMA);
  const anchor = spec.anchor !== false;
  if (anchor) {
    db.prepare("INSERT INTO local_runtime_session_agent_state (session_id,turn_id,updated_at_ms) VALUES (?,?,?)")
      .run(SESSION, TURN, TURN_START + 10_000);
  }
  // Two message rows in the previous turn, then two in the current one, so the
  // reverse scan meets the current turn first and stops on the boundary.
  db.prepare("INSERT INTO local_runtime_message_rows (id,session_id,turn_id,created_at_ms) VALUES (?,?,?,?)")
    .run(1, SESSION, PREV_TURN, T0);
  db.prepare("INSERT INTO local_runtime_message_rows (id,session_id,turn_id,created_at_ms) VALUES (?,?,?,?)")
    .run(2, SESSION, PREV_TURN, T0 + 1_000);
  db.prepare("INSERT INTO local_runtime_message_rows (id,session_id,turn_id,created_at_ms) VALUES (?,?,?,?)")
    .run(3, SESSION, TURN, TURN_START);
  db.prepare("INSERT INTO local_runtime_message_rows (id,session_id,turn_id,created_at_ms) VALUES (?,?,?,?)")
    .run(4, SESSION, TURN, TURN_START + 5_000);
  for (const [i, g] of (spec.goals || []).entries()) {
    db.prepare("INSERT INTO local_runtime_thread_goals (goal_id,session_id,objective,status,created_at_ms,updated_at_ms) VALUES (?,?,?,?,?,?)")
      .run("g" + i, SESSION, "objective " + i, "completed", T0 + g.at, T0 + g.at);
  }
  for (const [i, t] of (spec.tasks || []).entries()) {
    db.prepare("INSERT INTO local_runtime_background_tasks (task_id,owner_session_id,kind,status,created_at_ms,updated_at_ms) VALUES (?,?,?,?,?,?)")
      .run("t" + i, SESSION, t.kind, "succeeded", T0 + t.at, T0 + t.at);
  }
  db.close();
  return path;
}

function readBlock(stdout) {
  const line = String(stdout || "").trim().split("\n").pop();
  if (!line) return null;
  try {
    return JSON.parse(line)?.decision ?? null;
  } catch {
    return "unparseable";
  }
}

function readLedger(dataDir) {
  try {
    const lines = readFileSync(join(dataDir, "invocations.jsonl"), "utf8").trim().split("\n").filter(Boolean);
    if (lines.length === 0) return "no-record";
    return JSON.parse(lines[lines.length - 1]).verdict ?? "no-verdict-field";
  } catch {
    return "no-ledger";
  }
}

/** Drive the real hook process. `dbPath` null means "no database at all". */
function runHook(dbPath, opts = {}) {
  const data = opts.dataDir;
  const payload = {
    hook_event_name: opts.event || "Stop",
    session_id: opts.session || SESSION,
    last_assistant_message: opts.message || "report body",
    ...(opts.stopHookActive ? { stop_hook_active: true } : {}),
  };
  const env = { ...process.env, PLUGIN_DATA: data };
  if (dbPath) env.MCO_DGUARD_DB = dbPath;
  else delete env.MCO_DGUARD_DB;
  const r = spawnSync(process.execPath, [HOOK], { input: JSON.stringify(payload), encoding: "utf8", env });
  return { decision: readBlock(r.stdout), rc: r.status, ledger: readLedger(data), stderr: String(r.stderr || "") };
}

const root = mkdtempSync(join(tmpdir(), "fleet-coverage-selftest-"));
let pass = 0;
let fail = 0;
process.stdout.write(`SELFTEST check-fleet-coverage  fixture root=${root}\n`);
process.stdout.write("  (the live runtime database is never opened by this file)\n\n");

/** One arm: a fresh fixture dir, a fresh ledger dir, one hook process. */
function runArm({ name, spec, want }) {
  const dir = mkdtempSync(join(root, "arm-"));
  const data = join(dir, "data");
  mkdirSync(data, { recursive: true });
  const dbPath = spec.noDb ? null : buildFixture(dir, spec);
  const usePath = spec.decoyPath ? spec.decoyPath : dbPath;
  const r = runHook(usePath, { dataDir: data, event: spec.event, session: spec.session, stopHookActive: spec.stopHookActive });
  const ok = r.decision === want.decision && r.rc === want.rc && r.ledger === want.ledger;
  ok ? (pass += 1) : (fail += 1);
  process.stdout.write(
    `  ${ok ? "PASS" : "FAIL"}  ${name}\n` +
      `         want decision=${want.decision ?? "none"} rc=${want.rc} ledger=${want.ledger}\n` +
      `         got  decision=${r.decision ?? "none"} rc=${r.rc} ledger=${r.ledger}\n`,
  );
  if (!ok) {
    process.stdout.write(`         spec: ${JSON.stringify(spec)}\n`);
    if (r.stderr.trim()) {
      const el = r.stderr.trim().split("\n").slice(0, 6);
      process.stdout.write(`         stderr[${el.length} line(s)]:\n`);
      for (const l of el) process.stdout.write(`           ${l}\n`);
    }
  }
  return r;
}

// IN = inside the current turn (after TURN_START); BEFORE = before it, which the
// turn-scoped lane query must NOT count. The kind defaults to subagent because
// that is the only kind the hook counts.
const IN = (ms, kind = "subagent") => ({ at: 60_000 + ms, kind });
const BEFORE = (ms, kind = "subagent") => ({ at: ms, kind });

const ARMS = [
  {
    name: "F1  2 items, 0 lanes -> BLOCK (the law firing)",
    spec: { goals: [IN(1_000), IN(2_000)], tasks: [] },
    want: { decision: "block", rc: 1, ledger: "VIOLATION" },
  },
  {
    name: "F2  goals table empty -> NO-VERDICT (absent data must not block)",
    spec: { goals: [], tasks: [] },
    want: { decision: null, rc: 2, ledger: "NO-VERDICT" },
  },
  {
    name: "F3  database absent -> NO-VERDICT",
    spec: { noDb: true },
    want: { decision: null, rc: 2, ledger: "NO-VERDICT" },
  },
  {
    name: "F4  2 items, 1 subagent lane this turn -> PASS",
    spec: { goals: [IN(1_000), IN(2_000)], tasks: [IN(3_000, "subagent")] },
    want: { decision: null, rc: 0, ledger: "PASS" },
  },
  {
    name: "F5  1 item, 0 lanes -> PASS (one indivisible item is not a failure)",
    spec: { goals: [IN(1_000)], tasks: [] },
    want: { decision: null, rc: 0, ledger: "PASS" },
  },
  {
    name: "F6  2 items, 0 in-turn lanes, 300 lifetime lanes -> BLOCK (turn scoping)",
    spec: {
      goals: [IN(1_000), IN(2_000)],
      tasks: Array.from({ length: 300 }, (_, i) => BEFORE(1_000 + i)),
    },
    want: { decision: "block", rc: 1, ledger: "VIOLATION" },
  },
  {
    name: "F7  2 items, 5 in-turn BASH tasks -> BLOCK (background bash is not a lane)",
    spec: {
      goals: [IN(1_000), IN(2_000)],
      tasks: [IN(3_000, "bash"), IN(4_000, "bash"), IN(5_000, "bash"), IN(6_000, "bash"), IN(7_000, "bash")],
    },
    want: { decision: "block", rc: 1, ledger: "VIOLATION" },
  },
  {
    name: "F8  the 61 MB decoy path -> NO-VERDICT (refused by NAME)",
    spec: { goals: [IN(1_000), IN(2_000)], decoyPath: "C:/Users/Administrador/.minimax/sqlite.db" },
    want: { decision: null, rc: 2, ledger: "NO-VERDICT" },
  },
  {
    name: "F9  SubagentStop -> PASS (a leaf worker is the fleet working)",
    spec: { goals: [IN(1_000), IN(2_000)], tasks: [], event: "SubagentStop" },
    want: { decision: null, rc: 0, ledger: "EXEMPT" },
  },
  {
    name: "F10 no turn anchor -> NO-VERDICT (window underivable, never guessed)",
    spec: { goals: [IN(1_000), IN(2_000)], tasks: [], anchor: false },
    want: { decision: null, rc: 2, ledger: "NO-VERDICT" },
  },
];

for (const a of ARMS) runArm(a);

// F11: the one-shot guard. Same session, same payload, twice: the SECOND stop
// must be released even though the first was refused.
process.stdout.write("\n  F11 one-shot guard (a refusal must not loop):");
{
  const dir = mkdtempSync(join(root, "arm-oneshot-"));
  const data = join(dir, "data");
  mkdirSync(data, { recursive: true });
  const dbPath = buildFixture(dir, { goals: [IN(1_000), IN(2_000)], tasks: [] });
  const first = runHook(dbPath, { dataDir: data });
  const second = runHook(dbPath, { dataDir: data });
  const ok = first.decision === "block" && second.decision === null;
  ok ? (pass += 1) : (fail += 1);
  process.stdout.write(
    `\n  ${ok ? "PASS" : "FAIL"}  first=${first.decision} second=${second.decision ?? "none"} ` +
      `(want block then none; second ledger=${second.ledger})\n`,
  );
}

process.stdout.write(`\narms_pass=${pass} arms_fail=${fail}\n`);
process.stdout.write(`SELFTEST_VERDICT=${fail === 0 ? "PASS" : "FAIL"}\n`);
try { rmSync(root, { recursive: true, force: true }); } catch { /* scratch */ }
process.exit(fail === 0 ? 0 : 1);
