// Detector library with the sentinel protocol BUILT IN.
// WINDOW_UTC 2026-10-11T05:05Z. Born because two detectors of mine produced false
// verdicts in consecutive windows, both by testing a precondition they did not have:
//
//   1. a token detector fed its OWN formatted display text ("5\n" after I replaced
//      newlines with the two characters \n), and reported "5" as non-numeric.
//   2. an L301 detector tested "stdout empty" but not "exit code zero", and reported
//      an ffmpeg ERROR exit as the trigger. runTool rejects on rc != 0, so that path
//      can never reach the guard.
//
// RULE encoded here: every predicate below ships with the case that must be TRUE and
// the case that must be FALSE. `node detectors.mjs` runs them. A detector whose
// sentinel fails is not usable, and the library refuses to say anything else.

// --- predicates ---------------------------------------------------------

// Extract the RESULT line. Case-sensitive AND anchored on purpose: PowerShell's
// -match is case-insensitive, and "#getJobFromResolveResult" contains "Result",
// which made three consecutive runs read a loader stack trace as a test result.
export function extractResult(output) {
  const line = String(output)
    .split(/\r?\n/)
    .find((l) => /^\s*RESULT\b/.test(l));
  return line ? line.replace(/\s+/g, " ").trim() : null;
}

// True only for a token that parseFrameCount's /^\d+$/ would REJECT.
// Takes the raw token. Never takes formatted or decorated text.
export function isNonNumericToken(raw) {
  const s = String(raw);
  if (s.includes("\\n") || s.includes("\n")) return false; // refuse display text
  return s.length > 0 && !/^\d+$/.test(s);
}

// The L301 trigger needs BOTH halves: ffmpeg must exit 0 AND emit no hash lines.
// Half a precondition is the exact defect that produced a false positive.
export function isEmptyHashStreamTrigger(rc, hashLineCount) {
  return rc === 0 && hashLineCount === 0;
}

// A mutation arm is only reportable if the mutant PARSES. An arm that does not
// parse can never be RED -- it is INVALID, and reporting it as RED is a lie.
export function classifyArm(parses, resultLine, greenPattern) {
  if (!parses) return "INVALID-parse";
  if (!resultLine) return "INVALID-noresult";
  return greenPattern.test(resultLine) ? "GREEN" : "RED";
}

// --- sentinels ---------------------------------------------------------

// Sentinel suite. Guarded so that importing this module does NOT re-run it --
// discovered at WINDOW_UTC 2026-10-11T05:04:41Z, where a classification script
// imported these predicates and silently re-executed all sixteen sentinels
// instead of returning a verdict. Export the predicate; run the suite on demand.
export function runSentinels() {
  const sentinels = [
  // extractResult: must take a real line, must reject the loader stack trace
  ["extractResult takes a real RESULT line",
   extractResult("  PASS x\n  RESULT 19 passed, 1 failed\n") !== null],
  ["extractResult REJECTS '#getJobFromResolveResult' (the defect that burned me)",
   extractResult("    at #getJobFromResolveResult (node:internal/modules/esm/loader:354:34)") === null],
  ["extractResult rejects an empty output",
   extractResult("") === null],

  // isNonNumericToken: must accept what the guard rejects, reject what it accepts
  ["isNonNumericToken TRUE for 'N/A'", isNonNumericToken("N/A") === true],
  ["isNonNumericToken FALSE for '5'", isNonNumericToken("5") === false],
  ["isNonNumericToken FALSE for '0' (zero is a real value here)",
   isNonNumericToken("0") === false],
  ["isNonNumericToken REFUSES display text '5\\n' (defect #1)",
   isNonNumericToken("5\\n") === false],
  ["isNonNumericToken FALSE for '' (empty is a different guard, L232)",
   isNonNumericToken("") === false],

  // isEmptyHashStreamTrigger: both halves, and the negative control
  ["isEmptyHashStreamTrigger TRUE only for rc=0 AND 0 lines",
   isEmptyHashStreamTrigger(0, 0) === true],
  ["isEmptyHashStreamTrigger FALSE for rc=-22 AND 0 lines (defect #2)",
   isEmptyHashStreamTrigger(-22, 0) === false],
  ["isEmptyHashStreamTrigger FALSE for rc=0 AND 11 lines",
   isEmptyHashStreamTrigger(0, 11) === false],
  ["isEmptyHashStreamTrigger FALSE for rc=0 AND 1 line",
   isEmptyHashStreamTrigger(0, 1) === false],

  // classifyArm: an unparsable mutant must never be RED
  ["classifyArm INVALID when the mutant does not parse",
   classifyArm(false, "RESULT 19 passed, 1 failed", /, 0 failed/) === "INVALID-parse"],
  ["classifyArm INVALID when there is no RESULT line",
   classifyArm(true, null, /, 0 failed/) === "INVALID-noresult"],
  ["classifyArm RED when a result line shows a failure",
   classifyArm(true, "RESULT 19 passed, 1 failed", /, 0 failed/) === "RED"],
  ["classifyArm GREEN on the clean line",
   classifyArm(true, "RESULT 20 passed, 0 failed", /, 0 failed/) === "GREEN"],
];
  return sentinels;
}

// Only self-test when executed directly, never on import.
const isMain = process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/").split("/").pop());
if (isMain) {
  const sentinels = runSentinels();
  let failed = 0;
  for (const [name, ok] of sentinels) {
    console.log((ok ? "  ok   " : "  FAIL ") + name);
    if (!ok) failed++;
  }
  console.log(`SENTINELS ${sentinels.length - failed} passed, ${failed} failed`);
  console.log(`RESULT_SENTINELS ${sentinels.length - failed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
}