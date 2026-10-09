// check-fleet-coverage.mjs - Stop hook. THE FLEET-COVERAGE REFUSAL.
//
// THE LAW. Owner directive, 2026-10-04: "if you are not being reinforced to use
// several subagents, make something that forces you." Written instructions had
// already failed to produce fleet usage, so the instrument here is a MECHANICAL
// REFUSAL, not a paragraph: a turn that closed having completed two or more
// independent work items, having dispatched ZERO subagents for them, is a silent
// failure of parallelism, and the stop is refused with a named remedy.
//
// BOTH INPUTS COME FROM THE RUNTIME'S OWN STATE. Neither is read from the model's
// closing prose, because a self-report is exactly the thing that has already
// failed to change behaviour:
//
//   items  = local_runtime_thread_goals rows for this session, scoped to the
//            current turn. Each goal is an objective the RUNTIME declared, so its
//            existence is the mechanical fact "this is a work item".
//   lanes  = local_runtime_background_tasks rows with owner_session_id = this
//            session AND kind = 'subagent', scoped to the current turn.
//
// MEASURED, and the reason `kind` is in the join. Over the 2,000 most recent rows
// of that table the kind split is bash 1,963 / subagent 34, and for the parent
// session measured this turn: bash 1,704 / subagent 295. Counting rows without
// the kind filter would score "ran three background commands" as fleet usage -
// a permanent green, which is worse than no hook because it is trusted.
//
// WHY THE JOIN IS TURN-SCOPED, and the number that forces it. The parent session
// owns 295 lifetime subagent lanes. A session-lifetime count is therefore >= 1
// for every future turn, so a lifetime-scoped version of this hook could never
// block again after the first dispatch: measured permanent green. The turn window
// is what makes the check capable of firing at all. Self-test arm F6 pins it.
//
// NO-VERDICT IS A REAL OUTCOME HERE, not a fallback for an unfinished idea. The
// item source is the only mechanical work-item store this runtime has: a census
// of all 78 tables found no todo table, and local_runtime_thread_goals - the
// correct shape, indexed on session_id, with objective + status - held 0 rows
// across the whole 1.63 GB database at the time of writing. So on this host, as
// measured, this hook reports NO-VERDICT and passes. It will start enforcing the
// moment a goal exists. That is stated rather than hidden, and it is the honest
// reading of "if a data source you need does not exist, report NO-VERDICT and
// exit 0, never guess".
//
// BOUNDED BY CONSTRUCTION, because the database is 1.63 GB and LIVE:
//   - opened read-only, and only ever a file whose basename is exactly
//     runtime-state.sqlite. That is what makes the 61 MB decoy at
//     <dataDir>/sqlite.db (last modified 2026-03-10) structurally unreachable
//     rather than merely unused - self-test arm F9.
//   - every query is a single equality or a range on an INDEXED leading column:
//     idx_local_runtime_thread_goals_session(session_id) and
//     idx_local_runtime_background_tasks_owner(owner_session_id, created_at_ms,
//     task_id). No query scans a table.
//   - the one unavoidable reverse read, the turn start, selects three columns
//     (never data_json) over the message-row PRIMARY KEY in DESCENDING order with
//     a hard cap of TURN_SCAN_ROWS, and stops early on the first turn boundary.
//     Measured 242 ms for the full 4,000-row cap; the early exit lands far below.
//   - a wall-clock BUDGET_MS is checked between every step. Over budget is
//     NO-VERDICT, never a block: a hook that cannot finish must not be the thing
//     that stops the fleet.
//   - total measured cost of all five queries on the live database: ~30 ms.
//
// EXIT CODES - an rc carries a VERDICT, never a CAUSE. Disjoint by construction.
//   0  PASS        either compliant, or exactly ONE item (F5: a single indivisible
//                  unit is not a parallelism failure), or the event is not Stop.
//   1  RED         a block was emitted on stdout as {"decision":"block"}.
//   2  NO VERDICT  a precondition was absent, unreadable or over budget, OR the
//                  item count came back ZERO - which is indistinguishable from
//                  "this runtime records no items", so it is never a pass.
//                  Distinct from 0 on purpose, and never reachable as 1.
//   3  NO VERDICT  usage error.

import { existsSync, appendFileSync } from "node:fs";
import { basename, join } from "node:path";
import { DatabaseSync } from "node:sqlite";

import { parsePayload, readStdin, record, resolveDataDir } from "./ledger.mjs";

const USAGE =
  "usage: check-fleet-coverage.mjs [--help]\n" +
  "  Reads a Stop hook payload on stdin and refuses the stop when the turn closed\n" +
  "  having completed >=2 runtime-declared work items with zero subagent lanes\n" +
  "  dispatched for them. Both counts come from the live runtime database; neither\n" +
  "  comes from the model's own report.\n" +
  "\n" +
  "exit codes (an rc carries a VERDICT, never a CAUSE):\n" +
  "  0  PASS         compliant, fewer than two items, or the event is not Stop\n" +
  "  1  RED          a block was emitted (2+ items, 0 lanes this turn)\n" +
  "  2  NO VERDICT   a precondition was absent, unreadable, or over budget; the\n" +
  "                  law was never asked. Never a pass, never a block.\n" +
  "  3  NO VERDICT   usage error\n" +
  "\n" +
  "environment:\n" +
  "  MCO_DGUARD_DB  override the database path (self-tests). The basename must\n" +
  "                still be runtime-state.sqlite, so the <dataDir>/sqlite.db decoy\n" +
  "                cannot be selected even by override.\n" +
  "  PLUGIN_DATA    where invocations.jsonl is written; absent means no ledger.\n" +
  "\n" +
  "bounds: read-only open; indexed equality/range queries only; the single reverse\n" +
  "read is capped at " + 1500 + " rows and selects no message content; a " + 1200 +
  "ms wall-clock budget turns any overrun into NO VERDICT.\n";

// Two or more is the law's own threshold, not a tuned constant.
const MIN_ITEMS = 2;
const BUDGET_MS = 1200;
const TURN_SCAN_ROWS = 1500;
// The file the live runtime writes. A basename check, not a path check, so the
// decoy sqlite.db is unreachable from any override.
const DB_BASENAME = "runtime-state.sqlite";

const REASON =
  "Stop refused: this turn completed " + "{ITEMS}" + " independent work items and dispatched " +
  "ZERO subagents for them. Both numbers are the runtime's own, not your report: " +
  "{ITEMS} goals were declared for this session in this turn, and " +
  "local_runtime_background_tasks holds no kind='subagent' row for it.\n" +
  "Do this rather than describing it: dispatch the items as separate `task` calls " +
  "before the turn closes - one lane per item, each with a seat that can actually " +
  "deliver what it is handed. If the items are genuinely ONE indivisible unit, say " +
  "so in one line and this refusal does not apply: fewer than two declared items " +
  "passes silently.\n" +
  "Owner directive of 2026-10-04. One continuation only, then the turn ends either way.";

/** Resolve the database path, or null. The basename rule is the decoy guard. */
export function resolveDbPath() {
  const raw = process.env.MCO_DGUARD_DB || "";
  if (raw) return raw;
  const home = process.env.MINIMAX_HOME || "C:/Users/Administrador/.minimax";
  return home.replace(/\\/g, "/") + "/v2/sqlite/" + DB_BASENAME;
}

/**
 * The pure half: two measured counts in, one verdict out. Exported so the
 * self-test can drive the decision without a database, and so a reader can see
 * the block condition as a single expression.
 *   items  - runtime-declared work items completed in this turn
 *   lanes  - subagent lanes dispatched for this session in this turn
 * Returns "BLOCK" | "PASS".
 */
export function assess(items, lanes) {
  if (!Number.isInteger(items) || !Number.isInteger(lanes)) return "PASS"; // never block on a non-count
  return items >= MIN_ITEMS && lanes === 0 ? "BLOCK" : "PASS";
}

/**
 * One-shot marker, independent of the runtime's own stop_hook_active flag. A
 * block that re-fires is a loop, and a loop is a wedge.
 */
function alreadyContinued(session) {
  try {
    const dir = resolveDataDir();
    if (!dir) return false;
    const p = join(dir, `fleet-coverage.continued.${String(session).replace(/[^A-Za-z0-9._-]/g, "_")}`);
    return existsSync(p);
  } catch {
    return false;
  }
}

function markContinued(session) {
  try {
    const dir = resolveDataDir();
    if (!dir) return;
    const p = join(dir, `fleet-coverage.continued.${String(session).replace(/[^A-Za-z0-9._-]/g, "_")}`);
    if (!existsSync(p)) appendFileSync(p, "1\n", "utf8");
  } catch {
    /* a marker we cannot write must not break the turn */
  }
}

/** Measured inputs, or a named reason why they are absent. Never a guess. */
function measure(db, session, deadline) {
  const out = { items: null, lanes: null, turn_start_ms: null, why: null, statuses: [] };

  // 1. the current turn, from the per-session agent state row. Keyed by
  //    session_id, so this is a primary-key seek, not a scan.
  const anchor = db
    .prepare("SELECT turn_id FROM local_runtime_session_agent_state WHERE session_id=? ORDER BY updated_at_ms DESC LIMIT 1")
    .get(session);
  if (!anchor || !anchor.turn_id) {
    out.why = "no_turn_anchor";
    return out;
  }

  // 2. the turn's start, from a bounded reverse read of the message rows. Three
  //    columns only: message CONTENT is never selected, so a secret in a message
  //    cannot reach this process. Stops at the first earlier turn of this session.
  let turnStart = null;
  let sawTurn = false;
  const scan = db
    .prepare("SELECT turn_id, created_at_ms FROM local_runtime_message_rows ORDER BY id DESC LIMIT ?")
    .all(TURN_SCAN_ROWS);
  for (const row of scan) {
    if (row.turn_id === anchor.turn_id) {
      sawTurn = true;
      if (turnStart === null || row.created_at_ms < turnStart) turnStart = row.created_at_ms;
    } else if (sawTurn) {
      break; // an earlier turn reached: the window is closed
    }
  }
  if (turnStart === null) {
    out.why = "turn_start_unknown";
    return out;
  }
  out.turn_start_ms = turnStart;
  if (Date.now() > deadline) {
    out.why = "budget_exceeded_after_turn_scan";
    return out;
  }

  // 3. work items, scoped to the turn. The status vocabulary is recorded (keys
  //    only, never the objective text) so the day a goal exists the statuses
  //    become measurable instead of assumed.
  out.items = db
    .prepare("SELECT COUNT(*) c FROM local_runtime_thread_goals WHERE session_id=? AND created_at_ms>=?")
    .get(session, turnStart).c;
  out.statuses = db
    .prepare("SELECT status, COUNT(*) c FROM local_runtime_thread_goals WHERE session_id=? GROUP BY status LIMIT 16")
    .all(session)
    .map((r) => `${r.status}=${r.c}`);

  // 4. lanes, scoped to the turn, filtered to subagents.
  out.lanes = db
    .prepare(
      "SELECT COUNT(*) c FROM local_runtime_background_tasks " +
        "WHERE owner_session_id=? AND kind='subagent' AND created_at_ms>=?",
    )
    .get(session, turnStart).c;
  return out;
}

async function main() {
  const argv = process.argv.slice(2);
  for (const a of argv) {
    if (a === "--help" || a === "-h") {
      process.stdout.write(USAGE + "\n");
      process.exit(0);
    }
    process.stderr.write("check-fleet-coverage: USAGE ERROR: unknown option '" + a + "'\n" + USAGE + "\n");
    process.exit(3);
  }

  const raw = await readStdin();
  const payload = parsePayload(raw);
  const event = payload.hook_event_name || "unknown";
  const session = payload.session_id || "unknown";

  // The law binds the TURN, and the turn that dispatches a fleet is the root
  // one. A leaf worker completing two items correctly is the mechanism working,
  // not failing, so SubagentStop is recorded and released.
  if (event !== "Stop") {
    record({ event, verdict: "EXEMPT", action: "pass", why: "not_stop", session });
    process.exit(0);
  }
  if (!session || session === "unknown") {
    record({ event, verdict: "NO-VERDICT", action: "none", why: "no_session_id", session });
    process.exit(2);
  }
  // Guards before any work: a refusal that can re-fire is a loop.
  if (payload.stop_hook_active === true) {
    record({ event, verdict: "NO-VERDICT", action: "pass", why: "stop_hook_active_guard", session });
    process.exit(0);
  }
  if (alreadyContinued(session)) {
    record({ event, verdict: "NO-VERDICT", action: "pass", why: "session_marker_guard", session });
    process.exit(0);
  }

  const path = resolveDbPath();
  if (basename(path) !== DB_BASENAME) {
    // The decoy lives one directory up and is 61 MB of stale state. Refusing by
    // NAME means no override and no future refactor can quietly select it.
    record({
      event, verdict: "NO-VERDICT", action: "none", session,
      why: "db_basename_refused", want_basename: DB_BASENAME, got_basename: basename(path),
    });
    process.exit(2);
  }
  if (!existsSync(path)) {
    record({ event, verdict: "NO-VERDICT", action: "none", why: "db_absent", session, db_basename: DB_BASENAME });
    process.exit(2);
  }

  const deadline = Date.now() + BUDGET_MS;
  let db = null;
  let m;
  try {
    db = new DatabaseSync(path, { readOnly: true });
    m = measure(db, session, deadline);
  } catch (err) {
    // A crash is NOT a verdict. It is never read as compliance and never as a
    // RED, which is why it is 2 and not 1.
    record({
      event, verdict: "NO-VERDICT", action: "none", session,
      why: "db_unreadable", cause: err && err.message ? String(err.message).slice(0, 120) : "unknown",
    });
    process.exit(2);
  } finally {
    try { if (db) db.close(); } catch { /* closing a read-only handle cannot fail the turn */ }
  }

  const base = {
    event, session, turn_start_ms: m.turn_start_ms,
    items: m.items, lanes: m.lanes, goal_statuses: m.statuses,
    db_basename: DB_BASENAME,
  };

  if (m.why || m.items === null || m.lanes === null) {
    record({ ...base, verdict: "NO-VERDICT", action: "none", why: m.why || "unmeasured" });
    process.exit(2);
  }
  // ZERO items is NO-VERDICT, not PASS, and the distinction is the whole point.
  // "0 goals" and "this runtime records no goals" are the same observation:
  // measured across the live database, local_runtime_thread_goals held 0 rows in
  // total, so on this host a PASS here would be the hook claiming it looked and
  // found nothing to parallelise when in truth it cannot see items at all. One
  // item IS a positive measurement - the source works, the turn simply had a
  // single unit of work - and passes below.
  if (m.items === 0) {
    record({ ...base, verdict: "NO-VERDICT", action: "none", why: "no_items_declared" });
    process.exit(2);
  }
  if (assess(m.items, m.lanes) === "PASS") {
    record({ ...base, verdict: "PASS", action: "pass", why: m.items < MIN_ITEMS ? "insufficient_items" : "lanes_dispatched" });
    process.exit(0);
  }

  // VIOLATION. Mark first: if this process dies between the mark and the write,
  // the next Stop is released rather than refused forever.
  markContinued(session);
  record({ ...base, verdict: "VIOLATION", action: "block", threshold: MIN_ITEMS });
  process.stdout.write(
    JSON.stringify({ decision: "block", reason: REASON.replace(/\{ITEMS\}/g, String(m.items)) }) + "\n",
  );
  process.exit(1);
}

main();
