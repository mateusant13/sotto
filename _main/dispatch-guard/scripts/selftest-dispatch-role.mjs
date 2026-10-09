// selftest-dispatch-role.mjs - proves check-dispatch-role can go RED, both ways.
//
// WHY A SEPARATE FILE AND NOT A `--selftest` FLAG. check-dispatch-role.mjs calls
// main() at module scope, so merely importing it runs the hook and calls
// process.exit - an importing process dies at the import. The arms therefore
// drive the hook the way the runtime does: as a CHILD PROCESS with a real
// PreToolUse/task payload on stdin, and they read the real permissionDecision it
// emits. That is the wire the runtime uses, so it is the stronger claim: the
// arms assert the DECISION, not a re-implementation of the rule.
//
// THE FIVE PROBE STRINGS are the ones measured as a live false positive on
// 2026-10-04: four lawful read-only dispatches were denied because
// `produce` was a WRITE_VERB while NEGATION had no form that trails the verb.
// "Produce no artifacts on disk." therefore scored as an unnegated write order.
//
// THE ARMS MUST BE ABLE TO FAIL, so --mutant proves it. Each mutation is
// applied to a THROWAWAY COPY of scripts/ (never the live file) and the arm
// named by the mutation is required to go red. A green selftest on a rule that
// cannot go red is decoration.
//
//   node scripts/selftest-dispatch-role.mjs            # the 8 arms
//   node scripts/selftest-dispatch-role.mjs --mutant=no-trailing-quantifier
//   node scripts/selftest-dispatch-role.mjs --mutant=no-imperative-test
//
// EXIT CODES - an rc carries a VERDICT, never a CAUSE.
//   0  PASS   every arm held, and (under --mutant) the named arm went red.
//   1  RED    an arm's decision did not match the wanted decision.
//   2  RED    a mutation did not take effect, or the throwaway copy failed.
//   3  NO VERDICT  usage error / the hook file is absent.

import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const HOOK = join(here, "check-dispatch-role.mjs");
const USAGE =
  "usage: selftest-dispatch-role.mjs [--mutant=<name>]\n" +
  "  (no flag)     12 payload arms over the real hook process; 0 all held, 1 an arm is red\n" +
  "  --mutant=...  copy scripts/ to a temp dir, break ONE named rule there, and\n" +
  "                require the arm that rule protects to go RED; 0 if it did,\n" +
  "                2 if the mutation did not apply or the copy crashed at runtime.\n" +
  "  mutants: no-trailing-quantifier, no-imperative-test, no-proper-noun-exemption,\n" +
  "           no-capacity-exemption, and 'self-test: crash guard' - the last exists\n" +
  "           only to prove the MUTANT-CRASH guard itself still fires.\n" +
  "  --help        this text, rc=0\n" +
  "The live scripts/ tree is never modified by a mutation.";

// The probe strings, exactly as measured. `want` is the permissionDecision the
// runtime must see. DENY is `permissionDecision:"deny"`; ALLOW is no decision.
const ARMS = [
  {
    name: "D1 unnegated order in a declarative clause -> DENY",
    brief: "You write NO files. Do NOT write, edit or create any file anywhere.",
    want: "DENY",
    why: "the first clause carries no negation BEFORE its verb; the trailing quantifier must not rescue it",
  },
  {
    name: "D2 trailing quantifier on an imperative    -> ALLOW (the measured false positive)",
    brief: "Produce no artifacts on disk.",
    want: "ALLOW",
    why: "'produce no X' is a negative quantity, not an order to produce",
  },
  {
    name: "D3 backward negation                     -> ALLOW",
    brief: "Do not produce any artifacts on disk.",
    want: "ALLOW",
    why: "the pre-existing form must not regress",
  },
  {
    name: "D4 backward negation, emphatic          -> ALLOW",
    brief: "Never produce artifacts on disk.",
    want: "ALLOW",
    why: "same rule, different quantifier",
  },
  {
    name: "D5 read-only seat, no write order       -> ALLOW",
    brief:
      "SEAT: read-only measurement. You have no mandate to change anything on this host. " +
      "Your only output channel is your final message.",
    want: "ALLOW",
    why: "the lawful brief from the 2026-10-04 session that was denied",
  },
  {
    name: "D6 trailing quantifier, plural object    -> ALLOW",
    brief: "Write no files and create none.",
    want: "ALLOW",
    why: "'none' is the second trailing form; both verbs are negated",
  },
  {
    name: "D7 imperative order, no quantifier      -> DENY",
    brief: "Produce a census of every file under G:/ and report the totals.",
    want: "DENY",
    why: "the trailing rule must not neuter a real order",
  },
  {
    name: "D8 trailing quantifier on a later clause -> DENY",
    brief: "Produce the census. Produce no artifacts on disk.",
    want: "DENY",
    why: "one unnegated order anywhere keeps the whole brief an order",
  },
  {
    name: "P1 verb inside a proper noun      -> ALLOW (acceptance pair, measured 2nd pass)",
    brief: "C Edit Contract is implemented at proof-harness/src/models/edit_contract.rs",
    want: "ALLOW",
    why: "the only hit is `Edit` inside the abstraction's NAME; the brief ordered nothing",
  },
  {
    name: "P2 the same verb as an order      -> DENY (acceptance pair)",
    brief: "Edit the file at scripts/x.mjs",
    want: "DENY",
    why: "if this arm ever flips, the proper-noun exemption has eaten real orders",
  },
  {
    name: "P3 capacity modal                -> ALLOW (measured, house rule text)",
    brief: "A red is the most valuable output this cron can produce",
    want: "ALLOW",
    why: "`can produce` states capacity; it is not an order to the seat",
  },
  {
    name: "P4 lowercase declarative order    -> DENY (exemption must not over-fire)",
    brief: "The lane must write the receipt before it closes.",
    want: "DENY",
    why: "no capital, no capacity modal: still an order",
  },
];

function readDecision(stdout) {
  const line = String(stdout || "").trim().split("\n").pop();
  if (!line) return "none";
  try {
    return JSON.parse(line)?.hookSpecificOutput?.permissionDecision ?? "none";
  } catch {
    return "unparseable";
  }
}

function readLedgerVerdict(dataDir) {
  try {
    const p = join(dataDir, "invocations.jsonl");
    const lines = readFileSync(p, "utf8").trim().split("\n").filter(Boolean);
    if (lines.length === 0) return "no-record";
    return JSON.parse(lines[lines.length - 1]).verdict ?? "no-verdict-field";
  } catch {
    return "no-ledger";
  }
}

/** One arm: a real PreToolUse/task payload into the real hook process. */
function runArm(hookPath, arm, i, dataDir) {
  const payload = {
    hook_event_name: "PreToolUse",
    tool_name: "task",
    tool_input: {
      agent_name: "scout",
      description: "read-only measurement",
      prompt: arm.brief,
      run_in_background: false,
    },
    session_id: `selftest-dispatch-role-${i}`,
  };
  const r = spawnSync(process.execPath, [hookPath], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    env: { ...process.env, PLUGIN_DATA: dataDir },
  });
  return { got: readDecision(r.stdout), status: r.status, ledger: readLedgerVerdict(dataDir), stderr: String(r.stderr || "") };
}

/**
 * Each mutation targets ONE rule and names the arm that rule protects. A rule
 * with no mutation has no proof that its arm could ever fail.
 *
 * RE-ANCHORED 2026-10-05, after a refactor moved the decision into
 * findWriteOrder(). The previous anchors deleted the DECLARATION LINES of
 * `imperative` / `after`, which left `imperative` undefined further down: the
 * module still parsed, so `node --check` passed, and the arm then read ALLOW by
 * ABSENCE of a decision - which the harness reported as "DID NOT go red, the
 * rule is untested". That was wrong twice over: the mutation had a large
 * behavioural effect, and it produced a CRASH, not a verdict. Every mutation
 * below is now a pure VALUE substitution that keeps the surrounding code valid,
 * so a red is always behavioural and never a crash wearing a red's clothes.
 */
const MUTANTS = {
  "no-trailing-quantifier": {
    // Kill the forward negation while leaving `imperative` and `after` defined.
    re: "const trailingNegated = imperative && TRAILING.test(after);",
    to: "const trailingNegated = false;",
    arm: 1,
  },
  "no-imperative-test": {
    // Treat every clause as an imperative, so a trailing quantifier rescues a
    // declarative one. This is the mutation that must turn D1 red.
    re: "const imperative = isImperative(flat, m.index);",
    to: "const imperative = true;",
    arm: 0,
  },
  "no-proper-noun-exemption": {
    re: "\n    if (isProperNounUse(flat, m)) continue;",
    to: "",
    arm: 8,
  },
  "no-capacity-exemption": {
    re: "\n    if (isCapacityStatement(flat, m)) continue;",
    to: "",
    arm: 10,
  },
  "self-test: crash guard": {
    // Deliberately structural: deletes the DECLARATION of `imperative`, so the
    // module still parses (node --check passes) and then throws at runtime. This
    // exists only to prove the MUTANT-CRASH guard can fire; a guard that has
    // never fired is a comment.
    re: "const imperative = isImperative(flat, m.index);",
    to: "",
    arm: 1,
  },
};

/**
 * Copy the whole scripts/ tree so a mutation cannot touch the live plugin, and
 * return the copied hook path. Copying the DIRECTORY (not one file) is what
 * keeps the relative `import "./ledger.mjs"` working in the copy.
 */
function throwawayCopy(mutant) {
  const dir = mkdtempSync(join(tmpdir(), "dispatch-role-mutant-"));
  cpSync(here, join(dir, "scripts"), { recursive: true });
  const copy = join(dir, "scripts", "check-dispatch-role.mjs");
  const src = readFileSync(copy, "utf8");
  const m = MUTANTS[mutant];
  if (!m) return { dir, copy: null, applied: false };
  const out = typeof m.re === "string" ? src.replace(m.re, m.to) : src.replace(m.re, m.to);
  if (out === src) return { dir, copy, applied: false };
  writeFileSync(copy, out, "utf8");
  return { dir, copy, applied: true };
}

const argv = process.argv.slice(2);
if (argv.includes("--help") || argv.includes("-h")) {
  process.stdout.write(USAGE + "\n");
  process.exit(0);
}
const mutantArg = argv.find((a) => a.startsWith("--mutant="));
const mutant = mutantArg ? mutantArg.slice("--mutant=".length) : null;
if (argv.some((a) => a.startsWith("--mutant=")) && !Object.prototype.hasOwnProperty.call(MUTANTS, mutant)) {
  process.stderr.write("selftest-dispatch-role: UNKNOWN-MUTANT: " + mutant + "\n" + USAGE + "\n");
  process.exit(3);
}
if (!existsSync(HOOK)) {
  process.stderr.write("selftest-dispatch-role: HOOK-ABSENT: " + HOOK + "\n");
  process.exit(3);
}

const data = mkdtempSync(join(tmpdir(), "dispatch-role-selftest-"));
let hookPath = HOOK;
let exit = 0;

if (mutant) {
  const m = throwawayCopy(mutant);
  if (!m.applied) {
    process.stderr.write(
      "selftest-dispatch-role: MUTATION-NOT-APPLIED: the text this mutation targets is gone or renamed in " +
        "check-dispatch-role.mjs, so the mutant proved nothing. Population: 1 file, window: the current source.\n",
    );
    try { rmSync(m.dir, { recursive: true, force: true }); } catch { /* scratch */ }
    process.exit(2);
  }
  hookPath = m.copy;
  // A mutant that does not LOAD proves nothing. A syntax error in the copy makes
  // every arm "red" for a reason that has nothing to do with the rule under test
  // - the same defect as an arm that cannot fail, and silent, so it is checked
  // BEFORE any arm runs rather than inferred from the red.
  const chk = spawnSync(process.execPath, ["--check", hookPath], { encoding: "utf8" });
  if (chk.status !== 0) {
    process.stderr.write(
      "selftest-dispatch-role: MUTANT-UNLOADABLE: the mutated copy does not parse, so its red arms " +
        "would prove nothing. node --check rc=" + chk.status + "\n" +
        String(chk.stderr || "").split("\n").slice(0, 6).join("\n") + "\n",
    );
    try { rmSync(m.dir, { recursive: true, force: true }); } catch { /* scratch */ }
    process.exit(2);
  }
  process.stdout.write(`MUTANT ${mutant} applied to a throwaway copy (live tree untouched: ${readdirSync(here).length} entries)\n\n`);
}

process.stdout.write(`SELFTEST check-dispatch-role  hook=${hookPath === HOOK ? "live" : "throwaway-copy"}  data=${data}\n\n`);

let pass = 0;
let fail = 0;
const GOT = [];
const CRASHED_ARMS = [];
for (const [i, arm] of ARMS.entries()) {
  const r = runArm(hookPath, arm, i, data);
  const got = r.got.toUpperCase() === "DENY" ? "DENY" : "ALLOW";
  GOT[i] = got;
  // A non-zero exit is a CRASH, not a verdict. Recorded here because a crashed
  // hook emits NO decision, and an arm that expects ALLOW then reads ALLOW by
  // absence - which is indistinguishable from the rule working. Without this the
  // harness can call a crashing mutant "untested" when it is in fact broken.
  if (r.status !== 0) CRASHED_ARMS.push({ arm: arm.name, status: r.status, firstErr: r.stderr.trim().split("\n")[0] || "" });
  const ok = got === arm.want && r.status === 0;
  ok ? (pass += 1) : (fail += 1);
  process.stdout.write(
    `  ${ok ? "PASS" : "FAIL"}  ${arm.name}\n` +
      `         want=${arm.want} got=${got} exit=${r.status} ledger=${r.ledger}\n`,
  );
  if (!ok) process.stdout.write(`         why: ${arm.why}\n`);
  // Full stderr, not its first line: a one-line summary of a crash names the
  // file and line but not the CAUSE, and classifying a failure from the frame
  // alone is how a syntax error gets mistaken for a behavioural red.
  if (r.stderr.trim()) {
    const errLines = r.stderr.trim().split("\n").slice(0, 8);
    process.stdout.write(`         stderr[${errLines.length} line(s), first frame only is not evidence]:\n`);
    for (const el of errLines) process.stdout.write(`           ${el}\n`);
  }
}

process.stdout.write(`\narms_pass=${pass} arms_fail=${fail}\n`);

if (mutant) {
  // A mutant whose child CRASHES proves nothing, and must not be reported as
  // "the rule is untested": the mutation had an enormous behavioural effect, it
  // just was not a behavioural one. `node --check` above only catches a file that
  // does not PARSE; a file that parses and then throws at runtime slips through
  // it, and an arm that expects ALLOW reads ALLOW by the ABSENCE of any decision.
  if (CRASHED_ARMS.length > 0) {
    process.stderr.write(
      "selftest-dispatch-role: MUTANT-CRASH: " + CRASHED_ARMS.length + " arm(s) exited non-zero, so the " +
        "mutated copy threw at runtime rather than changing behaviour. A crash is not a verdict and not a red.\n",
    );
    for (const c of CRASHED_ARMS.slice(0, 3)) {
      process.stderr.write("  " + c.arm + " rc=" + c.status + " | " + c.firstErr.slice(0, 110) + "\n");
    }
    process.exit(2);
  }
  // The named arm is the one that proves the rule has teeth. Exit 0 = "the arm
  // went red as designed". The copy's loadability was already proven above, so a
  // red here is behavioural rather than a parse failure.
  const idx = MUTANTS[mutant].arm;
  const named = ARMS[idx];
  const namedRed = GOT[idx] !== named.want;
  process.stdout.write(
    `\nMUTANT VERDICT: arm ${idx + 1} (${named.name}) ` +
      `${namedRed ? "went RED as required" : "DID NOT go red - the rule is untested"}\n` +
      `  suite: ${pass} pass / ${fail} fail\n`,
  );
  if (!namedRed) exit = 2;
  process.exit(exit);
}

process.stdout.write(`SELFTEST_VERDICT=${fail === 0 ? "PASS" : "FAIL"}\n`);
try { rmSync(data, { recursive: true, force: true }); } catch { /* scratch */ }
process.exit(fail === 0 ? 0 : 1);
