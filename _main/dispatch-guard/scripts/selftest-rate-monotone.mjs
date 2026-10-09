// selftest-rate-monotone.mjs - proves check-rate-monotone.mjs can go GREEN and RED.
//
// A guard that cannot refuse is not a guard, and a guard that cannot stay quiet is worse
// than no guard. Every arm below is fired through the REAL script as a child process with
// a REAL stdin payload; nothing is imported, mocked or stubbed for the process arms. A
// second block of arms calls the exported `judge()` directly, because the process can tell
// me THAT it blocked but not WHICH of the four arithmetic rules did it.
//
// STATE. The child gets PLUGIN_DATA_OVERRIDE pointing at a scratch directory and no
// PLUGIN_DATA, so the one-shot markers this run creates cannot land in a real install.
import { spawnSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { judge } from "./check-rate-monotone.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const TARGET = join(here, "check-rate-monotone.mjs");

const SCRATCH = join(tmpdir(), "mcode-dispatch-guard-selftest-rate-monotone");
try {
  rmSync(SCRATCH, { recursive: true, force: true });
  mkdirSync(SCRATCH, { recursive: true });
} catch {
  /* scratch is a convenience; the arms still run without a one-shot marker file */
}

const ENV = { ...process.env, PLUGIN_DATA: undefined, PLUGIN_DATA_OVERRIDE: SCRATCH };

/** Fire the real script with a real payload. */
function fire(message, session) {
  const r = spawnSync(process.execPath, [TARGET], {
    input: JSON.stringify({
      hook_event_name: "Stop",
      session_id: session || "sess",
      last_assistant_message: message,
    }),
    encoding: "utf8",
    env: ENV,
  });
  let reason = null;
  if (r.stdout && r.stdout.trim()) {
    try {
      reason = JSON.parse(r.stdout).reason ?? null;
    } catch {
      reason = "UNPARSEABLE";
    }
  }
  return { rc: r.status, blocked: reason !== null, reason, stderr: (r.stderr || "").slice(-200) };
}

/** Same, with the raw bytes on stdin (malformed-input arms). */
function fireRaw(raw) {
  const r = spawnSync(process.execPath, [TARGET], {
    input: raw,
    encoding: "utf8",
    env: ENV,
  });
  return { rc: r.status, stdout: r.stdout || "", stderr: (r.stderr || "").slice(-200) };
}

const CLOSER = "\n## SELF-AUDIT\nPOPULATION 7 runs, WINDOW 2026-10-06 02:30.\n" +
  "Does your implementation meet the spec? YES - measured.";

// The defect, verbatim, as it appeared in two consecutive closing reports.
const PAIR = `Validation: 2 REDs in 6 runs at 02:00, then 1 RED in 7 runs.${CLOSER}`;

const arms = [
  // ---- RED: the guard must refuse an arithmetically impossible figure set. ----
  {
    name: "red-transcript-pair-numerator-falls-total-grows",
    message: PAIR,
    session: "sess-red-pair",
    want: true,
    rule: "A",
  },
  {
    name: "red-numerator-falls-total-grows-long-form",
    message: `First pass: 3 failures in 12 runs. Second pass: 2 failures in 14 runs.${CLOSER}`,
    session: "sess-red-long",
    want: true,
    rule: "A",
  },
  {
    name: "red-slash-form-same-shape",
    message: `Before: 2 REDs / 6 runs. After: 1 RED / 7 runs.${CLOSER}`,
    session: "sess-red-slash",
    want: true,
    rule: "A",
  },
  {
    name: "red-label-first-colon-form",
    message: `REDs: 2 of 6 runs at 02:00. REDs: 1 of 7 runs after the re-run.${CLOSER}`,
    session: "sess-red-colon",
    want: true,
    rule: "A",
  },
  {
    name: "red-rate-rises-against-its-own-falling-numerator",
    message: `2 REDs in 6 runs (33%), then 1 RED in 7 runs (40%).${CLOSER}`,
    session: "sess-red-rate",
    want: true,
    rule: "C",
  },
  {
    name: "red-figure-disagrees-with-its-own-percentage",
    message: `The gate reports 1 RED in 7 runs (50%).${CLOSER}`,
    session: "sess-red-pct",
    want: true,
    rule: "C",
  },
  {
    name: "red-bad-count-exceeds-its-own-total",
    message: `The lane reported 3 REDs in 2 runs.${CLOSER}`,
    session: "sess-red-over",
    want: true,
    rule: "D",
  },

  // ---- GREEN: a consistent report must never be touched. ----
  {
    name: "green-single-figure-alone",
    message: `## SELF-AUDIT\nPOPULATION 6 runs, WINDOW 2026-10-06 02:30.\n` +
      `2 REDs in 6 runs (33%) is the whole picture.${CLOSER}`,
    session: "sess-green-single",
    want: false,
  },
  {
    name: "green-numerator-flat-total-grows",
    message: `Run 6: 1 RED in 6 runs (17%). Run 7 was green, so 1 RED in 7 runs (14%).${CLOSER}`,
    session: "sess-green-flat",
    want: false,
  },
  {
    name: "green-both-numerator-and-total-grow",
    message: `2 REDs in 6 runs (33%), then 3 REDs in 8 runs (38%).${CLOSER}`,
    session: "sess-green-grow",
    want: false,
  },
  {
    name: "green-two-different-metrics-never-compared",
    message: `Type errors: 0 errors in 6 runs. Gate reds: 2 REDs in 7 runs.${CLOSER}`,
    session: "sess-green-metrics",
    want: false,
  },
  {
    name: "green-narrowed-window-with-a-shrinking-denominator",
    message: `Over the whole run: 4 REDs in 20 runs. In the last 5 runs: 1 RED in 5 runs.${CLOSER}`,
    session: "sess-green-window",
    want: false,
  },
  {
    name: "green-no-figure-at-all",
    message: CLOSER,
    session: "sess-green-none",
    want: false,
  },
  {
    name: "green-empty-message",
    message: "",
    session: "sess-green-empty",
    want: false,
  },
  {
    name: "green-one-shot-guard-second-fire-same-session",
    message: PAIR,
    session: "sess-red-pair", // already blocked above; the continuation must pass
    want: false,
  },
];

let failed = 0;
let redArms = 0;
let greenArms = 0;

for (const arm of arms) {
  if (arm.want) redArms += 1;
  else greenArms += 1;

  const res = fire(arm.message, arm.session);
  const ok = res.blocked === arm.want;
  if (!ok) failed += 1;
  let ruleNote = "";
  if (ok && arm.want) {
    const v = judge(arm.message);
    if (v.rule !== arm.rule) {
      failed += 1;
      ruleNote = ` :: RULE want=${arm.rule} got=${v.rule}`;
    } else {
      ruleNote = ` :: rule=${v.rule}`;
    }
  }
  process.stdout.write(
    `${ok && !ruleNote.includes("want") ? "ok  " : "FAIL"} ${arm.name} :: ` +
      `want_blocked=${arm.want} got=${res.blocked} rc=${res.rc}${ruleNote}` +
      `${res.reason ? ` :: ${res.reason.slice(0, 80).replace(/\n/g, " ")}` : ""}\n`,
  );
  if (res.stderr) process.stdout.write(`     stderr: ${res.stderr}\n`);
}

// Arms that are about the INPUT, not about the figures.
const rawArms = [
  ["raw-malformed-stdin-exits-0-and-silent", "not json at all", 0, ""],
  ["raw-empty-stdin-exits-0-and-silent", "", 0, ""],
  ["raw-wrong-shape-stdin-exits-0-and-silent", JSON.stringify({ hook_event_name: "Stop" }), 0, ""],
];
for (const [name, raw, wantRc, wantOut] of rawArms) {
  const res = fireRaw(raw);
  const ok = res.rc === wantRc && res.stdout === wantOut;
  if (!ok) failed += 1;
  process.stdout.write(`${ok ? "ok  " : "FAIL"} ${name} :: want_rc=${wantRc} got_rc=${res.rc} stdout=${JSON.stringify(res.stdout)}\n`);
}

// The one-shot guard is a REAL behaviour, not a comment: stop_hook_active must silence a
// violation without ever touching PLUGIN_DATA.
const guardPayload = JSON.stringify({
  hook_event_name: "Stop",
  session_id: "sess-guard",
  stop_hook_active: true,
  last_assistant_message: PAIR,
});
const guardRes = spawnSync(process.execPath, [TARGET], { input: guardPayload, encoding: "utf8", env: ENV });
const guardOk = guardRes.status === 0 && !guardRes.stdout.trim();
if (!guardOk) failed += 1;
process.stdout.write(
  `${guardOk ? "ok  " : "FAIL"} green-stop-hook-active-silences-violation :: ` +
    `want_rc=0 want_stdout=empty got_rc=${guardRes.status} stdout=${JSON.stringify(guardRes.stdout || "")}\n`,
);

const armsRun = arms.length + rawArms.length + 1;
const redCount = arms.filter((a) => a.want).length;
const greenCount = armsRun - redCount;

process.stdout.write(
  `SELFTEST ${failed === 0 ? "PASS" : "FAIL"} arms=${armsRun} ` +
    `red_arms=${redCount} green_arms=${greenCount} failures=${failed}\n`,
);
process.exit(failed === 0 ? 0 : 1);

// The scratch dir is left in place on purpose so a failing run can be inspected.