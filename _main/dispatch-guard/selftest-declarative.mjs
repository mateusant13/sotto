// selftest-declarative.mjs - lane/guardfix.
//
// PURPOSE. Prove the mcode-dispatch-guard PreToolUse/task hook distinguishes an
// IMPERATIVE write order from a DECLARATIVE one, BOTH WAYS: the four cases the
// briefing demands, plus the upstream arms that carry the guard's teeth.
//
// WHY A CHILD PROCESS AND NOT AN IMPORT. check-dispatch-role.mjs calls main() at
// module scope, so importing it runs the hook and calls process.exit. Every arm
// therefore drives the hook the way the runtime does - a real PreToolUse/task
// payload on stdin - and asserts the real permissionDecision it emits. That is
// the wire the runtime uses, so it is the stronger claim.
//
// USAGE.
//   node selftest-declarative.mjs [--hook=<dir>] [--mutant=<name>] [--label=<name>]
//
//   --hook=<dir>  directory containing check-dispatch-role.mjs + ledger.mjs.
//                 Default: the patched copy sitting beside this file.
//                 Point it at the LIVE plugin dir to measure the unpatched hook.
//   --mutant=<name>  copy --hook to a temp dir, revert ONE named rule there, and
//                 require the arm that rule protects to go RED. rc=2 if the
//                 mutation did not apply, did not parse, or the named arm held.
//   --label=<name>  printed in the header, so BEFORE and AFTER runs are
//                 distinguishable in a captured log.
//
// EXIT CODES - an rc carries a VERDICT, never a CAUSE.
//   0  PASS      every arm held (and, under --mutant, the named arm went red).
//   1  RED       an arm's decision did not match the wanted decision.
//   2  RED       the mutation did not take effect, did not load, or did not bite.
//   3  NO VERDICT usage error / the hook file is absent.

import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

const USAGE =
  "usage: selftest-declarative.mjs [--hook=<dir>] [--mutant=<name>] [--label=<name>]\n" +
  "  --hook=<dir>    dir holding check-dispatch-role.mjs. default: this file's own dir\n" +
  "  --mutant=<name> mutants: no-declarative-trailing-exempt (reverts to the\n" +
  "                  upstream expression), no-trailing-quantifier, no-obligation-gate\n" +
  "  --label=<name>  header label for the captured log\n" +
  "  --help          this text, rc=0\n" +
  "The live plugin tree is never modified by a mutation.";

// ---------------------------------------------------------------------------
// THE PATCHED EXPRESSION AND ITS ORIGINAL.
//
// PATCHED (lane/guardfix):
//   const trailingNegated = TRAILING.test(after) && !obligation;
//
// ORIGINAL (live plugin):
//   const trailingNegated = imperative && TRAILING.test(after);
//
// The mutant reverts the patched expression to the original in a THROWAWAY COPY.
// ---------------------------------------------------------------------------
const PATCHED_EXPR = "const trailingNegated = TRAILING.test(after) && !obligation;";
const ORIGINAL_EXPR = "const trailingNegated = imperative && TRAILING.test(after);";

// DENY is permissionDecision:"deny"; ALLOW is the ABSENCE of a decision.
const ARMS = [
  // ---- the four cases the briefing demands, verbatim -----------------------
  {
    id: "a",
    name: "(a) verifier + imperative `Create <file>`        -> MUST BLOCK",
    seat: "verifier",
    brief: "Create the report at _main/verdict.md, then report the totals.",
    want: "DENY",
    why: "THE PROTECTIVE ARM. A read-only seat handed a file to write is the exact bug the hook exists to stop.",
  },
  {
    id: "b",
    name: "(b) verifier + \"Produce no artifacts.\"           -> MUST PASS",
    seat: "verifier",
    brief: "Produce no artifacts on disk.",
    want: "ALLOW",
    why: "already passing before the fix (imperative + trailing quantifier). Must not regress.",
  },
  {
    id: "c",
    name: "(c) verifier + \"You create no files.\"            -> MUST PASS after fix",
    seat: "verifier",
    brief: "You create no files, you edit nothing, you commit nothing.",
    want: "ALLOW",
    why: "THE MEASURED FALSE POSITIVE. A declarative NEGATION read as an order; RED before the fix.",
  },
  {
    id: "d",
    name: "(d) worker  + `Create <file>`                    -> MUST PASS",
    seat: "worker",
    brief: "Create the report at _main/verdict.md, then report the totals.",
    want: "ALLOW",
    why: "a write-capable seat may be ordered to write; the hook must stay quiet here.",
  },

  // ---- upstream arms carried over: the guard's teeth -----------------------
  {
    id: "R1",
    name: "R1 imperative order, no quantifier                -> DENY",
    seat: "verifier",
    brief: "Produce a census of every file under G:/ and report the totals.",
    want: "DENY",
    why: "upstream D7. The trailing rule must not neuter a real order.",
  },
  {
    id: "R2",
    name: "R2 imperative `Edit the file`                    -> DENY",
    seat: "scout",
    brief: "Edit the file at scripts/x.mjs",
    want: "DENY",
    why: "upstream P2. Acceptance pair for the proper-noun exemption.",
  },
  {
    id: "R3",
    name: "R3 DEONTIC declarative order, no quantifier      -> DENY",
    seat: "verifier",
    brief: "The lane must write the receipt before it closes.",
    want: "DENY",
    why: "upstream P4. THE reason the fix must NOT exempt declarative clauses wholesale: a modal of obligation is still an order.",
  },
  {
    id: "R4",
    name: "R4 imperative order, then a negated clause       -> DENY",
    seat: "verifier",
    brief: "Produce the census. Produce no artifacts on disk.",
    want: "DENY",
    why: "upstream D8. One unnegated order anywhere keeps the whole brief an order.",
  },
  {
    id: "R5",
    name: "R5 deontic question-free order                   -> DENY",
    seat: "verifier",
    brief: "The verifier must produce a written verdict before closing.",
    want: "DENY",
    why: "A modal of obligation with NO trailing quantifier. The second half of R3's protection.",
  },
  {
    id: "R6",
    name: "R6 proper-noun use of `Edit`                     -> ALLOW",
    seat: "scout",
    brief: "C Edit Contract is implemented at proof-harness/src/models/edit_contract.rs",
    want: "ALLOW",
    why: "upstream P1. The pre-existing proper-noun exemption must not regress.",
  },
  {
    id: "R7",
    name: "R7 capacity modal `can produce`                  -> ALLOW",
    seat: "scout",
    brief: "A red is the most valuable output this cron can produce",
    want: "ALLOW",
    why: "upstream P3. The pre-existing capacity exemption must not regress.",
  },
  {
    id: "R8",
    name: "R8 backward negation `Do not produce`            -> ALLOW",
    seat: "verifier",
    brief: "Do not produce any artifacts on disk.",
    want: "ALLOW",
    why: "upstream D3. The pre-existing backward negation must not regress.",
  },
  {
    id: "R9",
    name: "R9 coordinated imperative, trailing `none`      -> ALLOW",
    seat: "verifier",
    brief: "Write no files and create none.",
    want: "ALLOW",
    why: "upstream D6. The coordinated-imperative path must not regress.",
  },
  {
    id: "R10",
    name: "R10 read-only seat, no write order at all        -> ALLOW",
    seat: "verifier",
    brief: "SEAT: read-only measurement. You have no mandate to change anything on this host. Your only output channel is your final message.",
    want: "ALLOW",
    why: "upstream D5. The lawful brief must pass.",
  },

  // ---- the observed blocks this patch does NOT fix, recorded so the suite
  // ---- states them instead of leaving them to be rediscovered ---------------
  {
    id: "R11",
    name: "R11 OBLIGATION + comparative quantifier          -> DENY",
    seat: "verifier",
    brief: "You must produce no fewer than three ledgers per cycle.",
    want: "DENY",
    why: "THE ARM THE OBLIGATION GATE PROTECTS. A comparative 'no fewer than' is a real order wearing a negative quantifier's clothes; without the gate the fix would allow it.",
  },
  {
    id: "K1",
    name: "K1 observed block 3: tool enumeration             -> DENY (KNOWN, still open)",
    seat: "verifier",
    brief: "Use the read, grep and write tools.",
    want: "DENY",
    why: "classified meta-reference but STILL a deny by design; this patch does not touch that class.",
  },
  {
    id: "K2",
    name: "K2 observed block 2: verb inside a question       -> DENY (KNOWN, still open)",
    seat: "verifier",
    brief: "Should the seat produce a written verdict, or reply in chat?",
    want: "DENY",
    why: "a question is not an order, but the hook has no interrogative rule; this patch does not add one.",
  },
  {
    id: "K3",
    name: "K3 observed block 1: `write` verb, real order     -> DENY (CORRECT)",
    seat: "verifier",
    brief: "Write the verification report to disk before you close.",
    want: "DENY",
    why: "the briefing calls this a genuine seat mismatch; it must keep denying.",
  },
  {
    id: "K4",
    name: "K4 observed block 4: numbered imperative step     -> DENY (CORRECT)",
    seat: "verifier",
    brief: "3. Create _main/review.md with your findings.",
    want: "DENY",
    why: "the briefing calls this a genuine seat mismatch; it must keep denying.",
  },
];

// Each mutation reverts ONE rule and names the arm that rule protects.
const MUTANTS = {
  "no-declarative-trailing-exempt": {
    re: PATCHED_EXPR,
    to: ORIGINAL_EXPR,
    arm: 2, // (c) - the declarative negation the patch rescues
    mustFlip: "ALLOW",
  },
  "no-trailing-quantifier": {
    re: PATCHED_EXPR,
    to: "const trailingNegated = false;",
    arm: 1, // (b) - the imperative trailing quantifier
    mustFlip: "ALLOW",
  },
  "no-obligation-gate": {
    re: PATCHED_EXPR,
    to: "const trailingNegated = TRAILING.test(after);",
    arm: 14, // R11 - the deontic order the gate protects
    mustFlip: "ALLOW",
  },
  // NO `no-imperative-test` MUTANT, DELIBERATELY. After the fix the decision is
  // `TRAILING && !obligation`, which is algebraically independent of
  // `isImperative`: forcing `imperative = true` changes no arm. The upstream
  // mutant targeted D1, which this patch retires. Shipping a mutant that cannot
  // go red would be a guard that reports "the rule is untested" for a rule that
  // simply moved. `imperative` is now DIAGNOSTIC-ONLY: it labels the `kind` field
  // and nothing else.
};

function readDecision(stdout) {
  const line = String(stdout || "").trim().split("\n").pop();
  if (!line) return "none";
  try {
    return JSON.parse(line)?.hookSpecificOutput?.permissionDecision ?? "none";
  } catch {
    return "unparseable";
  }
}

/** One arm: a real PreToolUse/task payload into the real hook process. */
function runArm(hookPath, arm, i, dataDir) {
  const payload = {
    hook_event_name: "PreToolUse",
    tool_name: "task",
    tool_input: {
      agent_name: arm.seat,
      description: "read-only measurement",
      prompt: arm.brief,
      run_in_background: false,
    },
    session_id: `selftest-declarative-${i}`,
  };
  const r = spawnSync(process.execPath, [hookPath], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    env: { ...process.env, PLUGIN_DATA: dataDir },
  });
  return {
    got: readDecision(r.stdout),
    status: r.status,
    stderr: String(r.stderr || ""),
  };
}

const argv = process.argv.slice(2);
if (argv.includes("--help") || argv.includes("-h")) {
  process.stdout.write(USAGE + "\n");
  process.exit(0);
}
const arg = (name, fallback) => {
  const hit = argv.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.slice(name.length + 3) : fallback;
};

const label = arg("label", "unlabelled");
const hookDir = arg("hook", here);
const mutant = arg("mutant", null);
if (mutant && !Object.prototype.hasOwnProperty.call(MUTANTS, mutant)) {
  process.stderr.write(`selftest-declarative: UNKNOWN-MUTANT: ${mutant}\n` + USAGE + "\n");
  process.exit(3);
}

let hookPath = join(hookDir, "check-dispatch-role.mjs");
if (!existsSync(hookPath)) {
  process.stderr.write(`selftest-declarative: HOOK-ABSENT: ${hookPath}\n`);
  process.exit(3);
}

let scratch = null;
if (mutant) {
  scratch = mkdtempSync(join(tmpdir(), "guardfix-mutant-"));
  cpSync(hookDir, join(scratch, "scripts"), { recursive: true });
  const copy = join(scratch, "scripts", "check-dispatch-role.mjs");
  const src = readFileSync(copy, "utf8");
  const m = MUTANTS[mutant];
  const out = src.replace(m.re, m.to);
  if (out === src) {
    process.stderr.write(
      `selftest-declarative: MUTATION-NOT-APPLIED: the text "${m.re}" is gone or renamed in ` +
        `${copy}, so the mutant proved nothing.\n`,
    );
    try { rmSync(scratch, { recursive: true, force: true }); } catch { /* scratch */ }
    process.exit(2);
  }
  writeFileSync(copy, out, "utf8");
  hookPath = copy;
  const chk = spawnSync(process.execPath, ["--check", hookPath], { encoding: "utf8" });
  if (chk.status !== 0) {
    process.stderr.write(
      `selftest-declarative: MUTANT-UNLOADABLE: the mutated copy does not parse, so its red arms ` +
        `would prove nothing. node --check rc=${chk.status}\n` +
        String(chk.stderr || "").split("\n").slice(0, 6).join("\n") + "\n",
    );
    try { rmSync(scratch, { recursive: true, force: true }); } catch { /* scratch */ }
    process.exit(2);
  }
}

const data = mkdtempSync(join(tmpdir(), "guardfix-selftest-"));
process.stdout.write(
  `SELFTEST declarative/imperative  label=${label}  hook=${hookPath === join(hookDir, "check-dispatch-role.mjs") ? hookDir : "throwaway-copy"}\n\n`,
);

let pass = 0;
let fail = 0;
const GOT = [];
const CRASHED = [];
for (const [i, arm] of ARMS.entries()) {
  const r = runArm(hookPath, arm, i, data);
  const got = r.got.toUpperCase() === "DENY" ? "DENY" : "ALLOW";
  GOT[i] = got;
  if (r.status !== 0) CRASHED.push({ arm: arm.name, status: r.status, firstErr: r.stderr.trim().split("\n")[0] || "" });
  const ok = got === arm.want && r.status === 0;
  ok ? (pass += 1) : (fail += 1);
  process.stdout.write(
    `  ${ok ? "PASS" : "FAIL"}  ${arm.name}\n` +
      `         seat=${arm.seat} want=${arm.want} got=${got} exit=${r.status}\n`,
  );
  if (!ok) process.stdout.write(`         why: ${arm.why}\n`);
  if (r.stderr.trim()) {
    for (const el of r.stderr.trim().split("\n").slice(0, 8)) process.stdout.write(`           ${el}\n`);
  }
}

process.stdout.write(`\narms_pass=${pass} arms_fail=${fail}\n`);

if (mutant) {
  if (CRASHED.length > 0) {
    process.stderr.write(
      `selftest-declarative: MUTANT-CRASH: ${CRASHED.length} arm(s) exited non-zero. A crash is not a verdict and not a red.\n`,
    );
    for (const c of CRASHED.slice(0, 3)) {
      process.stderr.write(`  ${c.arm} rc=${c.status} | ${c.firstErr.slice(0, 110)}\n`);
    }
    process.exit(2);
  }
  const m = MUTANTS[mutant];
  const named = ARMS[m.arm];
  const flipped = GOT[m.arm] !== named.want;
  process.stdout.write(
    `\nMUTANT VERDICT: arm ${m.arm} (${named.name}) ${flipped ? "went RED as required" : "DID NOT go red - the rule is untested"}\n` +
      `  suite: ${pass} pass / ${fail} fail\n`,
  );
  try { rmSync(scratch, { recursive: true, force: true }); } catch { /* scratch */ }
  try { rmSync(data, { recursive: true, force: true }); } catch { /* scratch */ }
  process.exit(flipped ? 0 : 2);
}

process.stdout.write(`SELFTEST_VERDICT=${fail === 0 ? "PASS" : "FAIL"}\n`);
try { rmSync(data, { recursive: true, force: true }); } catch { /* scratch */ }
process.exit(fail === 0 ? 0 : 1);