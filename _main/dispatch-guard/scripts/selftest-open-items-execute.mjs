// selftest-open-items-execute.mjs - proves check-open-items-execute can go RED.
//
// A hook that has never refused anything is a decoration. Every arm drives the
// REAL judge() and the REAL main() over a real hook payload, and asserts the real
// exit code and the real decision. No mocks, no reimplementation.
//
// THE ARMS THAT MATTER ARE THE TWO THAT MUST NOT FIRE. B2 and B3 are the anti-noise
// arms, and they are the reason this hook is usable at all: a hook that fires on the
// owner's own decisions is a hook whose instruction cannot be obeyed, and an agent
// that learns to route around such a hook is worse off than with no hook. A selftest
// that only proved "it can fire" would not notice that failure.

import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const HOOK = join(here, "check-open-items-execute.mjs");
const data = mkdtempSync(join(tmpdir(), "open-items-execute-selftest-"));

const ARMS = [
  {
    name: "A1 enumerated AGENT debt, then stopped -> VIOLATION (this is the red arm)",
    message:
      "Landed 4 commits.\n\n## WHAT'S NEXT / WHAT I DID NOT DO\n- commit the remaining 407 tracked modifications\n- push the branch to the remote\n\nDoes your implementation meet the spec? YES.",
    want: "VIOLATION",
    wantDecision: "block",
    expectEcho: ["commit the remaining 407 tracked modifications", "push the branch to the remote"],
  },
  {
    name: "A2 ONLY owner decisions -> COMPLIANT (anti-noise: it must NOT nag)",
    message:
      "Done what I could.\n\n## WHAT'S NEXT / WHAT I DID NOT DO\n" +
      "- PENDENTE-DONO: escolher branch vs merge\n" +
      "- autorizas reiniciar o PC?\n" +
      "- aguardo a tua decisão sobre o áudio\n" +
      "- only the owner can repor o default de saída\n" +
      "- I am waiting on your call for the push target\n\n" +
      "Does your implementation meet the spec? NO - awaiting the push decision.",
    want: "COMPLIANT",
    wantDecision: null,
  },
  {
    name: "A3 owner AND agent items mixed -> VIOLATION, and ONLY the agent item is echoed",
    message:
      "Partial.\n\n## WHAT'S NEXT / WHAT I DID NOT DO\n- owner must decide the merge target\n- re-measure the untracked count on the landing branch\n\nDoes your implementation meet the spec? NO - not pushed.",
    want: "VIOLATION",
    wantDecision: "block",
    expectEcho: ["re-measure the untracked count on the landing branch"],
    rejectEcho: ["owner must decide the merge target"],
  },
  {
    name: "A4 clean report, no section at all -> COMPLIANT",
    message:
      "Landed and pushed.\n\n## OBSERVATIONS\n- claim: green\n  population: 5 gates\n  window: this run\n\nDoes your implementation meet the spec? YES.",
    want: "COMPLIANT",
    wantDecision: null,
  },
  {
    name: "A5 section present but enumerates nothing -> COMPLIANT (nothing to execute)",
    message: "All done.\n\n## WHAT'S NEXT / WHAT I DID NOT DO\n\nNothing outstanding.\n\nDoes your implementation meet the spec? YES.",
    want: "COMPLIANT",
    wantDecision: null,
  },
  {
    name: "A6 numbered items count as items -> VIOLATION",
    message: "Partial.\n\n## WHAT I DID NOT DO\n1. profile E:\\\n2. re-run the census\n",
    want: "VIOLATION",
    wantDecision: "block",
    expectEcho: ["profile E:\\", "re-run the census"],
  },
  {
    name: "A7 'not verified' section alone does NOT trigger",
    message:
      "Report.\n\n## NOT VERIFIED\n- the parser boundary\n\nDoes it meet the spec? YES.",
    want: "COMPLIANT",
    wantDecision: null,
  },
  {
    name: "A8 empty message -> NOVALUE (never a block on absent input)",
    message: "",
    want: "NOVALUE",
    wantDecision: null,
  },
];

function mk(payload) {
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
    return null;
  }
}

let pass = 0;
let fail = 0;
console.log(`SELFTEST check-open-items-execute   data=${data}\n`);

// The module guards its own auto-run, so importing it cannot fire the hook.
const mod = await import(`${pathToFileURL(HOOK).href}?t=${Date.now()}`);
const { judge, extractItems, classify } = mod;

for (const [i, arm] of ARMS.entries()) {
  const r = mk({ hook_event_name: "Stop", session_id: `selftest-arm-${i}`, last_assistant_message: arm.message });
  const decision = decisionOf(r);
  const reasonText = String(r.stdout || "");
  const pure = judge(arm.message);
  const ok =
    decision === arm.wantDecision &&
    (pure === arm.want || arm.want === "NOVALUE") &&
    (arm.expectEcho ?? []).every((s) => reasonText.includes(s)) &&
    (arm.rejectEcho ?? []).every((s) => !reasonText.includes(s));
  ok ? (pass += 1) : (fail += 1);
  console.log(
    `  ${ok ? "PASS" : "FAIL"}  ${arm.name}\n` +
      `         judge=${pure} decision=${decision ?? "none"} exit=${r.status} ` +
      `items=${extractItems(arm.message).length} agent=${extractItems(arm.message).filter((x) => classify(x) === "AGENT").length}`,
  );
  if (!ok) {
    if (decision !== arm.wantDecision) console.log(`         want decision=${arm.wantDecision ?? "none"}`);
    if (pure !== arm.want && arm.want !== "NOVALUE") console.log(`         want judge=${arm.want}`);
    for (const s of arm.expectEcho ?? []) if (!reasonText.includes(s)) console.log(`         reason MISSING echo: ${s}`);
    for (const s of arm.rejectEcho ?? []) if (reasonText.includes(s)) console.log(`         reason LEAKED: ${s}`);
  }
}

// one-shot guard: the SECOND identical Stop for the same session must pass
console.log("\n  one-shot guard (second Stop for the same session must NOT re-block):");
const bad = ARMS[0].message;
const p1 = { hook_event_name: "Stop", session_id: "selftest-oneshot", last_assistant_message: bad };
const d1 = decisionOf(mk(p1));
const d2 = decisionOf(mk(p1));
const oneshotOk = d1 === "block" && d2 === null;
oneshotOk ? (pass += 1) : (fail += 1);
console.log(`  ${oneshotOk ? "PASS" : "FAIL"}  first=${d1} second=${d2} (want block then none)`);

// stop_hook_active must release it independently of the marker
console.log("\n  stop_hook_active guard (independent of the marker):");
const d3 = decisionOf(mk({ ...p1, session_id: "selftest-stopflag", stop_hook_active: true }));
const flagOk = d3 === null;
flagOk ? (pass += 1) : (fail += 1);
console.log(`  ${flagOk ? "PASS" : "FAIL"}  stop_hook_active=true -> ${d3} (want none)`);

// NAMESPACE ISOLATION. If this hook shared the sibling's marker file, whichever ran
// second would read the first one's marker and pass. Invisible in a per-hook read.
console.log("\n  marker namespace isolation from check-open-items.mjs:");
const sib = join(data, "open-items.continued.selftest-namespace");
const mine = join(data, "open-items-execute.continued.selftest-namespace");
mk({ hook_event_name: "Stop", session_id: "selftest-namespace", last_assistant_message: bad });
const { existsSync } = await import("node:fs");
const nsOk = existsSync(mine) && !existsSync(sib);
nsOk ? (pass += 1) : (fail += 1);
console.log(
  `  ${nsOk ? "PASS" : "FAIL"}  mine=${existsSync(mine)} sibling=${existsSync(sib)} (want mine=true sibling=false)`,
);

console.log(`\nSELFTEST_VERDICT=${fail === 0 ? "PASS" : "FAIL"}  arms_pass=${pass} arms_fail=${fail}`);
try { rmSync(data, { recursive: true, force: true }); } catch { /* scratch */ }
process.exit(fail === 0 ? 0 : 1);
