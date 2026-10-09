// selftest-unfinished-no-action.mjs - proves check-unfinished-no-action.mjs can go GREEN and RED.
// A guard that cannot refuse is not a guard. Every arm below is fired through the REAL script,
// as a child process, with a REAL stdin payload on a real pipe. Nothing is imported, mocked, or
// monkeypatched. Each arm also asserts the rc contract, because "fail open" is part of the spec
// and not something the block/silence verdict alone would catch.
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const TARGET = join(here, "check-unfinished-no-action.mjs");

// Scratch dir for the one-shot marker arm only. It is created here and removed at the end; no
// deliverable is written outside the two files this lane owns.
const SCRATCH = mkdtempSync(join(tmpdir(), "mcode-unfinished-no-action-selftest-"));

/**
 * Fires the real hook. `spec` is one of:
 *   string            - last_assistant_message
 *   {payload, env}    - full stdin object, extra env
 *   {raw}             - raw stdin bytes (malformed-input arms)
 *   {payload, env, twice: true} - fire once, then fire the same session again
 */
function fire(spec) {
  const s = typeof spec === "string" ? { payload: { last_assistant_message: spec } } : spec;
  const env = { ...process.env, ...(s.env || {}) };
  const run = () =>
    spawnSync(process.execPath, [TARGET], {
      input: s.raw !== undefined ? s.raw : JSON.stringify({ hook_event_name: "Stop", ...s.payload }),
      encoding: "utf8",
      env,
      timeout: 10000,
    });

  const r = run();
  let decision = null;
  let reason = null;
  let parsed = false;
  if (r.stdout && r.stdout.trim()) {
    try {
      const j = JSON.parse(r.stdout);
      parsed = true;
      decision = j.decision ?? null;
      reason = j.reason ?? null;
    } catch {
      parsed = false;
    }
  }
  const out = {
    rc: r.status,
    blocked: decision === "block" && parsed && reason !== null,
    reason,
    parsed,
    stderr: (r.stderr || "").trim().slice(-160),
  };
  if (s.twice) {
    const second = run();
    out.secondRc = second.status;
    out.secondStdout = (second.stdout || "").trim();
  }
  return out;
}

// --------------------------------------------------------------------------------------------------
// GREEN arms - a compliant report must pass in silence. These are the arms that keep the hook off
// the switch-off list, so they are written as whole realistic reports, not as one-liners.
// --------------------------------------------------------------------------------------------------

const REALISTIC_COMPLIANT = `## RESULT
POPULATION 386 guard files, WINDOW 2026-10-06 02:15:36. The hook runs and blocks the arms.

## SELF-AUDIT
1. Protocols missing: none.
2. Extra verification: node --check plus the selftest, both captured.
3. New checkboxes: none.
4. Review: skipped (orchestrator discretion, law-that-describes-itself).
5. Confidence: high; it would move on a report whose admission is in prose only.
6. What was NOT verified: the hook on a live Stop event.
7. Gate-doubt: gate-melhor: the census arm is one sample wide.

## WHAT'S NEXT / WHAT I DID NOT DO
- Land the PLUGIN_DATA marker on Windows and measure the second-fire rate.
- Blocked: waiting on the owner's decision about the census cadence.

Does your implementation meet the spec? YES - measured on both states.`;

const REALISTIC_NO_SECTION = `## RESULT
POPULATION 386 guard files, WINDOW 2026-10-06 02:15:36. All 4 check arms and all 8 arms pass.

## SELF-AUDIT
1. Protocols missing: none.
2. Extra verification: selftest run end to end, output quoted verbatim.
3. New checkboxes: none.
4. Review: skipped (orchestrator discretion, law-that-describes-itself).
5. Confidence: high on the shape, untested on a live turn.
6. What was NOT verified: behaviour under an oversized stdin.
7. Gate-doubt: none.

Does your implementation meet the spec? YES - the arms that matter both went red.`;

const arms = [
  // ---- GREEN: silent ----
  ["green-imperative-verb-plus-target",
    "## WHAT'S NEXT / WHAT I DID NOT DO\n- Land the CRT gate on the healer.", false],
  ["green-next-clause-is-a-commitment",
    "## WHAT'S NEXT / WHAT I DID NOT DO\n- next: measure the census over G:/repos", false],
  ["green-deferral-that-names-its-blocker",
    "## WHAT I DID NOT DO\n- Blocked: waiting on the owner's pricing decision.", false],
  ["green-owner-item-cannot-be-executed",
    "## WHAT I DID NOT DO\n- PENDENTE-DONO: definir o preço do plano.", false],
  ["green-none-is-a-claim-not-an-admission",
    "## WHAT I DID NOT DO\n- none", false],
  ["green-realistic-compliant-report",
    REALISTIC_COMPLIANT, false],
  ["green-realistic-report-with-no-section",
    REALISTIC_NO_SECTION, false],

  // ---- Corpus regression arms. Each line below is VERBATIM from a real receipt under
  // I:\!manager\runs that the FIRST implementation of this hook blocked, and each one is a
  // false positive. They exist so the failure cannot come back silently. ----
  ["green-corpus-prohibition-not-a-debt",
    "## WHAT'S NEXT / WHAT I DID NOT DO\n" +
    "- Do not commit anything in `I:\\!manager`.\n" +
    "- Do not kill, start, or restart MiniMax Code.", false],
  ["green-corpus-selfaudit-rubric-fields",
    "## O QUE NAO FOI VERIFICADO\n" +
    "- gate-doubt:\n" +
    "- verde-de-verdade:\n" +
    "- nao verificado**:", false],
  ["green-corpus-imperatives-outside-any-verb-list",
    "## WHAT'S NEXT / WHAT I DID NOT DO\n" +
    "- Arm the OMP reaper and decide `ManagerCronWake`.** Target: the reaper task.\n" +
    "- Free disk on the three volumes under 2.3%.\n" +
    "- Re-read the Defender exclusions and publish the diff as the receipt.", false],
  ["green-empty-message", "", false],
  ["green-whitespace-message", "   \n\n  ", false],

  // ---- RED: block. Each of these is an admission with no action attached. ----
  ["red-bare-noun-phrase-under-the-heading",
    "## WHAT'S NEXT / WHAT I DID NOT DO\n- the retro file for the fleet-coverage lane", true],
  ["red-admission-in-past-tense-with-no-commitment",
    "## WHAT'S NEXT / WHAT I DID NOT DO\n- I didn't land the fix.", true],
  ["red-bare-deferral-with-no-blocker",
    "## WHAT I DID NOT DO\n- That one is deferred.", true],
  ["red-label-line-with-no-continuation",
    "**What I did NOT do:** the census over G:/repos", true],
  ["red-one-inert-item-among-compliant-ones",
    "## WHAT'S NEXT / WHAT I DID NOT DO\n" +
    "- Land the PLUGIN_DATA marker.\n" +
    "- Waiting on the owner for the price.\n" +
    "- things", true],
  ["red-portuguese-inert-admission",
    "## O QUE NAO FIZ\n- o hook nao foi ligado no hooks.json", true],
  ["red-corpus-admission-pt-with-a-rationale-but-no-action",
    "## O QUE NAO FIZ\n- Nenhum recibo foi escrito do zero. Os 28 receipts existem e descrevem o trabalho real.", true],
  ["red-corpus-unverified-claim-flagged-as-belief",
    "## WHAT WAS NOT VERIFIED\n- As 4 linhas com `par_provado: false` que eu **acho** que sao `true`.", true],
  ["red-corpus-nothing-compares-the-two-files",
    "## WHAT WAS NOT VERIFIED\n- nothing compares `survival-plane.json` against the Startup folder for renamed siblings", true],

  // ---- Contract arms: malformed stdin, missing field, loop guards. ----
  ["contract-malformed-stdin-exits-0", { raw: "{not json at all" }, false],
  ["contract-empty-stdin-exits-0", { raw: "" }, false],
  ["contract-json-scalar-stdin-exits-0", { raw: '"just a string"' }, false],
  ["contract-missing-last-assistant-message-exits-0", { payload: { session_id: "s-contract" } }, false],
  ["contract-null-last-assistant-message-exits-0", { payload: { last_assistant_message: null } }, false],
  ["contract-stop-hook-active-suppresses-second-block",
    { payload: {
        hook_event_name: "Stop",
        stop_hook_active: true,
        session_id: "s-active",
        last_assistant_message: "## WHAT I DID NOT DO\n- the retro file",
      } }, false],
  ["contract-session-marker-blocks-only-once",
    { env: { PLUGIN_DATA: SCRATCH },
      twice: true,
      payload: {
        hook_event_name: "Stop",
        session_id: "s-marker-once",
        last_assistant_message: "## WHAT I DID NOT DO\n- the retro file",
      } }, true],
];

let failed = 0;
let redCount = 0;
let greenCount = 0;

function report(name, ok, detail) {
  if (!ok) failed += 1;
  process.stdout.write(`${ok ? "ok  " : "FAIL"} ${name} :: ${detail}\n`);
}

for (const [name, spec, wantBlocked] of arms) {
  const res = fire(spec);
  const ok = res.blocked === wantBlocked && res.rc === (wantBlocked ? 1 : 0);
  if (wantBlocked) redCount += 1;
  else greenCount += 1;
  report(
    name,
    ok,
    `want_blocked=${wantBlocked} got=${res.blocked} rc=${res.rc} json_ok=${res.parsed}` +
      (res.reason ? ` :: ${res.reason.slice(0, 80).replace(/\n/g, " ")}` : "") +
      (res.stderr ? ` :: stderr ${res.stderr}` : ""),
  );
  // The one-shot marker must actually have stopped the SECOND fire, in the same session.
  if (spec && typeof spec === "object" && spec.twice) {
    const ok2 = res.secondRc === 0 && res.secondStdout === "";
    report(`${name} :: second-fire-is-silent`, ok2, `second_rc=${res.secondRc} second_stdout=${JSON.stringify(res.secondStdout)}`);
  }
}

try {
  rmSync(SCRATCH, { recursive: true, force: true });
} catch {
  /* leaving a temp dir behind must not fail the selftest */
}

process.stdout.write(
  `SELFTEST ${failed === 0 ? "PASS" : "FAIL"} arms=${arms.length} ` +
    `expect_block=${redCount} expect_silent=${greenCount} failures=${failed}\n`,
);
process.exit(failed === 0 ? 0 : 1);