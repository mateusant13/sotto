// selftest-count-population.mjs - proves check-count-population.mjs can go RED.
//
// A guard that has never refused anything is a decoration. Every arm fires the REAL
// script as a child process with a REAL stdin payload, and asserts the REAL exit code
// and the REAL decision. Nothing is imported to produce a verdict; the only import is
// of `judge()` for a display column, exactly as the sibling selftests do.
//
// THE ARMS THAT MATTER MOST ARE THE ONES THAT MUST NOT FIRE.
// A first-time measurement with no population (G1) and ordinary prose numbers (G3-G6)
// are the arms that keep this hook from duplicating check-report-binding.mjs. A
// selftest that only proved "it can block" would not notice that duplication.

import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const HOOK = join(here, "check-count-population.mjs");
const data = mkdtempSync(join(tmpdir(), "count-population-selftest-"));

const ARMS = [
  // ---------------------------------------------------------------- RED arms.
  {
    name: "R1 observed instance 1: '5 tarballs (not 4 - my earlier count came from a truncated listing)'",
    message:
      "Result: 5 tarballs (not 4 - my earlier count came from a truncated listing).\n" +
      "The earlier figure was wrong because the listing was cut short.",
    want: "VIOLATION",
    wantExit: 1,
    wantDecision: "block",
    expectReason: ["POPULATION", "WINDOW"],
  },
  {
    name: "R2 observed instance 2: '7 `adsnames-*` directories survive'",
    message: "Cleanup: 7 `adsnames-*` directories survive under the worktree.",
    want: "VIOLATION",
    wantExit: 1,
    wantDecision: "block",
    expectReason: ["POPULATION"],
  },
  {
    name: "R3 explicit correction marker, count and noun on one line",
    message: "Correcao: the census found 23 lanes, actually 27 lanes after the respawn.",
    want: "VIOLATION",
    wantExit: 1,
    wantDecision: "block",
    expectReason: ["WINDOW"],
  },
  {
    name: "R4 revision phrasing: revised count, no population, no window",
    message: "Revised count: 14 modules were touched. That supersedes the number I gave earlier.",
    want: "VIOLATION",
    wantExit: 1,
    wantDecision: "block",
    expectReason: ["POPULATION"],
  },
  {
    name: "R5 survival phrasing on the adjacent line (window slip) - only WINDOW missing",
    message: "Re-ran after the prune. 9 tarballs remain.\nDone.",
    want: "VIOLATION",
    wantExit: 1,
    wantDecision: "block",
    expectReason: ["WINDOW"],
  },
  {
    name: "R6 population present, WINDOW absent -> still VIOLATION",
    message: "out of 386 guards, 3 hooks failed the census. Correcting my earlier count.",
    want: "VIOLATION",
    wantExit: 1,
    wantDecision: "block",
    expectReason: ["WINDOW"],
  },

  // ------------------------------------------------------------- GREEN arms.
  {
    name: "G1 NON-DUPLICATION: first-time count, no correction marker, no population -> SILENT",
    message: "The census found 42 hooks in the tree and I am reporting that as-is.",
    want: "COMPLIANT",
    wantExit: 0,
    wantDecision: null,
  },
  {
    name: "G2 restated count WITH population and window -> SILENT (the intended escape)",
    message:
      "POPULATION 386 guards under G:\\superharness\\scripts, WINDOW 2026-10-06 05:40.\n" +
      "Correction to my earlier count: 5 hooks remain unclassified.",
    want: "COMPLIANT",
    wantExit: 0,
    wantDecision: null,
  },
  {
    name: "G3 ordinary prose numbers: date, version, duration, percentage -> SILENT",
    message: "Ran on 2026-10-06 with node v20.11.1; the suite took 42.5s and passed at 98%.",
    want: "COMPLIANT",
    wantExit: 0,
    wantDecision: null,
  },
  {
    name: "G4 dates and versions are not counts even beside a restatement word -> SILENT",
    message: "The run of 2026-10-06 actually used release 2026.10.1 and stayed under 30s.",
    want: "COMPLIANT",
    wantExit: 0,
    wantDecision: null,
  },
  {
    name: "G5 restatement word with NO count on the line -> SILENT",
    message: "I was wrong about the earlier figure; the correct approach is to re-measure the tree.",
    want: "COMPLIANT",
    wantExit: 0,
    wantDecision: null,
  },
  {
    name: "G6 durations beside count nouns are prose -> SILENT",
    message: "Actually the 3 hooks each took 15 minutes, so the timeout of 30s never mattered.",
    want: "COMPLIANT",
    wantExit: 0,
    wantDecision: null,
  },
  {
    name: "G7 clean ordinary report, no counts at all -> SILENT",
    message: "All gates are green and the selftest passes. Nothing outstanding.",
    want: "COMPLIANT",
    wantExit: 0,
    wantDecision: null,
  },
  {
    name: "G8 empty message -> NOVALUE (never a block on absent input)",
    message: "",
    want: "NOVALUE",
    wantExit: 0,
    wantDecision: null,
  },
];

function fire(payload) {
  return spawnSync(process.execPath, [HOOK], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    env: { ...process.env, PLUGIN_DATA: data },
  });
}

function decisionOf(r) {
  try {
    const line = String(r.stdout || "").trim().split("\n").pop();
    return line ? (JSON.parse(line).decision ?? null) : null;
  } catch {
    return "UNPARSEABLE";
  }
}

let pass = 0;
let fail = 0;
const check = (ok, label, detail) => {
  ok ? (pass += 1) : (fail += 1);
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${ok || !detail ? "" : `\n         ${detail}`}`);
};

console.log(`SELFTEST check-count-population   data=${data}\n`);

// The module guards its own auto-run, so importing it cannot fire the hook.
const mod = await import(`${pathToFileURL(HOOK).href}?t=${Date.now()}`);
const { judge } = mod;

console.log("  ARMS");
for (const [i, arm] of ARMS.entries()) {
  const r = fire({
    hook_event_name: i % 2 === 0 ? "Stop" : "SubagentStop",
    session_id: `selftest-arm-${i}`,
    last_assistant_message: arm.message,
  });
  const decision = decisionOf(r);
  const pure = judge(arm.message);
  const stdout = String(r.stdout || "");
  const want = arm.wantDecision;
  const got = want === "block" ? stdout : stdout;
  const decisionsOk = decision === want;
  const exitOk = r.status === arm.wantExit;
  const pureOk = arm.want === "NOVALUE" ? true : pure === arm.want;
  const reasonOk = (arm.expectReason ?? []).every((s) => stdout.includes(s));
  const silentOk = want === null ? stdout.trim() === "" : true;
  const ok = decisionsOk && exitOk && pureOk && reasonOk && silentOk;
  ok ? (pass += 1) : (fail += 1);
  console.log(
    `  ${ok ? "PASS" : "FAIL"}  ${arm.name}\n` +
      `         judge=${pure} decision=${decision ?? "none"} exit=${r.status} (want judge=${arm.want} decision=${want ?? "none"} exit=${arm.wantExit})`,
  );
  if (!ok) {
    if (!decisionsOk) console.log(`         want decision=${want ?? "none"}`);
    if (!exitOk) console.log(`         want exit=${arm.wantExit}`);
    if (!pureOk) console.log(`         want judge=${arm.want} got=${pure}`);
    for (const s of arm.expectReason ?? []) if (!stdout.includes(s)) console.log(`         reason MISSING: ${s}`);
    if (!silentOk) console.log(`         expected silence but stdout=${JSON.stringify(stdout.slice(0, 120))}`);
  }
  void got;
}

// Loop safety, same two independent guards the contract requires (:212-213).
console.log("\n  GUARDS");
const bad = ARMS[0].message;
const oneShotPayload = {
  hook_event_name: "Stop",
  session_id: "selftest-oneshot",
  last_assistant_message: bad,
};
const first = decisionOf(fire(oneShotPayload));
const second = decisionOf(fire(oneShotPayload));
check(first === "block" && second === null, `one-shot marker: first=${first} second=${second} (want block then none)`);

const flagged = decisionOf(fire({ ...oneShotPayload, session_id: "selftest-stopflag", stop_hook_active: true }));
check(flagged === null, `stop_hook_active=true -> ${flagged} (want none)`);

const namespaced = existsSync(join(data, "count-population.continued.selftest-namespace"));
const sibling = existsSync(join(data, "report-binding.continued.selftest-namespace")) ||
  existsSync(join(data, "open-items.continued.selftest-namespace")) ||
  existsSync(join(data, "open-items-execute.continued.selftest-namespace"));
fire({ hook_event_name: "Stop", session_id: "selftest-namespace", last_assistant_message: bad });
const nsMine = existsSync(join(data, "count-population.continued.selftest-namespace"));
check(nsMine && !sibling, `marker namespace isolated: mine=${nsMine} siblingMarkerPresent=${sibling} (want true/false)`);

// Never crash into a verdict: malformed stdin, empty stdin, a JSON array, a
// non-string message. All must exit 0 in silence.
console.log("\n  DEGRADED INPUT (must be rc=0, silent)");
for (const [label, raw] of [
  ["empty stdin", ""],
  ["not JSON at all", "this is not json {{{"],
  ["JSON array not object", "[1,2,3]"],
  ["object without the message", '{"hook_event_name":"Stop"}'],
  ["null message", '{"hook_event_name":"Stop","last_assistant_message":null}'],
  ["numeric message", '{"hook_event_name":"Stop","last_assistant_message":12345}'],
  ["truncated JSON", '{"last_assistant_message":"5 tarballs (not 4'],
]) {
  const r = spawnSync(process.execPath, [HOOK], {
    input: raw,
    encoding: "utf8",
    env: { ...process.env, PLUGIN_DATA: data },
  });
  check(r.status === 0 && String(r.stdout || "").trim() === "", `${label} -> rc=${r.status} stdout=${JSON.stringify(String(r.stdout || "").slice(0, 40))} (want rc=0 silent)`);
}

// No credential can reach stdout: the reason is built only from count+noun tokens
// taken from the message. Feed it a message containing a secret-looking token and
// assert it does not appear in the block output.
const secretish = "Result: 5 tarballs (not 4 - my earlier count came from a truncated listing). token=sk-ABCDEFGHIJKLMNOPQRSTUVWX";
const secretOut = String(fire({ hook_event_name: "Stop", session_id: "selftest-secret", last_assistant_message: secretish }).stdout || "");
check(secretOut.includes('"decision":"block"') && !secretOut.includes("sk-ABCDEFGHIJKLMNOPQRSTUVWX"),
  `reason echoes counts, never the secret token (blocked=${secretOut.includes('"decision":"block"')} leaked=${secretOut.includes("sk-ABC")})`);

const redArms = ARMS.filter((a) => a.wantDecision === "block").length;
const greenArms = ARMS.filter((a) => a.wantDecision === null).length;
console.log(`\nARMS red_expect_block=${redArms} green_expect_silence=${greenArms}`);
check(redArms >= 4 && greenArms >= 4, `arm budget met: red=${redArms} green=${greenArms} (want >=4 each)`);

console.log(`\nSELFTEST ${fail === 0 ? "PASS" : "FAIL"} arms=${ARMS.length} checks_pass=${pass} checks_fail=${fail}`);
try {
  rmSync(data, { recursive: true, force: true });
} catch {
  /* scratch */
}
process.exit(fail === 0 ? 0 : 1);