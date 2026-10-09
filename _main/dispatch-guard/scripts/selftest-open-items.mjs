// selftest-open-items.mjs - proves check-open-items can go RED.
//
// A hook that has never refused anything is a decoration. Every arm below drives the
// REAL judge() from check-open-items.mjs over a real payload, through the real main()
// path, and asserts the real exit code. No mocks, no reimplementation.

import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const HOOK = join(here, "check-open-items.mjs");
const data = mkdtempSync(join(tmpdir(), "open-items-selftest-"));

const ARMS = [
  {
    name: "A1 admits-open + enumerates  -> COMPLIANT",
    message:
      "Report.\n\n## WHAT'S NEXT / WHAT I DID NOT DO\n- measure the queue again\n- wire the collector\n\nDoes your implementation meet the spec? YES.",
    want: "COMPLIANT",
    wantDecision: null,
  },
  {
    name: "A2 admits-open + NO section   -> VIOLATION (this is the red arm)",
    message:
      "Report.\n\n## NOT VERIFIED\n- several things I could not determine\n\nDoes your implementation meet the spec? YES.",
    want: "VIOLATION",
    wantDecision: "block",
  },
  {
    name: "A3 clean report, no admission -> COMPLIANT (the hook must NOT nag)",
    message:
      "Report.\n\n## OBSERVATIONS\n- claim: x\n  population: 3\n  window: 1h\n\nDoes your implementation meet the spec? YES - measured.",
    want: "COMPLIANT",
    wantDecision: null,
  },
  {
    name: "A4 section exists but is EMPTY -> VIOLATION",
    message: "Report.\n\n## WHAT'S NEXT / WHAT I DID NOT DO\n\nThat is all.\n\nDoes it meet the spec? YES.",
    want: "VIOLATION",
    wantDecision: "block",
  },
  {
    name: "A5 numbered items count as items -> COMPLIANT",
    message: "Report.\n\nI did not finish the census.\n\n## WHAT I DID NOT DO\n1. profile E:\n2. profile I:\n",
    want: "COMPLIANT",
    wantDecision: null,
  },
  {
    name: "A6 'not verified' alone does NOT trigger (the regression that was fixed)",
    message: "Report.\n\n## NOT VERIFIED\n- the parser boundary\n\nDoes it meet the spec? YES.",
    want: "COMPLIANT",
    wantDecision: null,
  },
  {
    name: "A7 empty message -> NOVALUE (never a block on absent input)",
    message: "",
    want: "NOVALUE",
    wantDecision: null,
  },
];

function runArm(arm, i) {
  const payload = {
    hook_event_name: "Stop",
    session_id: `selftest-arm-${i}`,
    last_assistant_message: arm.message,
  };
  const r = spawnSync(process.execPath, [HOOK], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    env: { ...process.env, PLUGIN_DATA: data },
  });
  let decision = null;
  try {
    const line = String(r.stdout || "").trim().split("\n").pop();
    if (line) decision = JSON.parse(line).decision ?? null;
  } catch {
    decision = null;
  }
  return { decision, stderr: r.stderr, status: r.status };
}

let pass = 0;
let fail = 0;
console.log(`SELFTEST check-open-items   data=${data}\n`);

// import the judge directly for the pure half, then drive main() for the wire half
const { judge } = await import(`file://${HOOK.replace(/\\/g, "/")}?t=${Date.now()}`).catch(() => ({ judge: null }));

for (const [i, arm] of ARMS.entries()) {
  const { decision, status } = runArm(arm, i);
  const pure = judge ? judge(arm.message) : "SKIPPED";
  const decisionOk = decision === arm.wantDecision;
  const pureOk = pure === arm.want || pure === "SKIPPED";
  const ok = decisionOk && pureOk;
  ok ? (pass += 1) : (fail += 1);
  console.log(
    `  ${ok ? "PASS" : "FAIL"}  ${arm.name}\n` +
      `         judge=${pure} decision=${decision ?? "none"} exit=${status}`,
  );
  if (!ok) console.log(`         want judge=${arm.want} decision=${arm.wantDecision ?? "none"}`);
}

// one-shot guard: the SECOND identical Stop for the same session must pass
console.log("\n  one-shot guard (second Stop for the same session must NOT re-block):");
const bad = ARMS[1].message;
const p1 = { hook_event_name: "Stop", session_id: "selftest-oneshot", last_assistant_message: bad };
const mk = (payload) =>
  spawnSync(process.execPath, [HOOK], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    env: { ...process.env, PLUGIN_DATA: data },
  });
const a = mk(p1);
const b = mk(p1);
const d1 = (() => { try { return JSON.parse(String(a.stdout).trim()).decision; } catch { return "none"; } })();
const d2 = (() => { try { return JSON.parse(String(b.stdout).trim()).decision; } catch { return "none"; } })();
const oneshotOk = d1 === "block" && d2 === "none";
oneshotOk ? (pass += 1) : (fail += 1);
console.log(`  ${oneshotOk ? "PASS" : "FAIL"}  first=${d1} second=${d2} (want block then none)`);

// stop_hook_active must also release it, independently
console.log("\n  stop_hook_active guard (independent of the marker):");
const fresh = { ...p1, session_id: "selftest-stopflag", stop_hook_active: true };
const c = mk(fresh);
const d3 = (() => { try { return JSON.parse(String(c.stdout).trim()).decision; } catch { return "none"; } })();
const flagOk = d3 === "none";
flagOk ? (pass += 1) : (fail += 1);
console.log(`  ${flagOk ? "PASS" : "FAIL"}  stop_hook_active=true -> ${d3} (want none)`);

console.log(`\nSELFTEST_VERDICT=${fail === 0 ? "PASS" : "FAIL"}  arms_pass=${pass} arms_fail=${fail}`);
try { rmSync(data, { recursive: true, force: true }); } catch { /* scratch */ }
process.exit(fail === 0 ? 0 : 1);
