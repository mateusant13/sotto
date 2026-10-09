// check-count-population.mjs - Stop / SubagentStop hook.
//
// THE DEFECT, MEASURED, NOT HYPOTHESISED. A review of the agent's own closing report
// found two published counts, verbatim:
//
//   "5 tarballs (not 4 - my earlier count came from a truncated listing)"
//   "7 `adsnames-*` directories survive"
//
// Both are RESTATED or CORRECTED counts: each supersedes a number the agent had
// already said, or reports what is left of a set after a filter. Both name neither
// the search ROOT nor the time WINDOW. A reader cannot tell whether 5 is everything
// under the worktree or a filtered subset, and "not 4" invites the reader to
// reconcile two numbers that are both unavailable. The law, measured 2026-09-25: a
// DERIVED number may not be published without its POPULATION and its WINDOW. A
// count without them is not a narrower claim; it is a different claim whose meaning
// is a free parameter.
//
// NON-DUPLICATION - READ THIS BEFORE CHANGING THE TRIGGER.
// check-report-binding.mjs, in the same event group, ALREADY blocks a success claim
// missing POPULATION/WINDOW/P0. This hook is not a second copy of it and must never
// become one. The dividing line:
//
//   check-report-binding.mjs  -> a FIRST-TIME measurement that happens to lack a
//                                population. Not mine. That hook's business.
//   check-count-population.mjs -> a number the agent CORRECTED, RESTATED, SURVIVED
//                                 or REMAINED. The second number in the sentence is
//                                 the trigger. A first-time measurement with no
//                                 correction marker is SILENT HERE BY DESIGN, even
//                                 when it carries no population whatsoever.
//
// Arm G1 of the selftest pins that division with a first-time, population-free,
// correction-free count: it must stay silent. If you widen this trigger until it
// fires on any count lacking a population, it duplicates its sibling and both hooks
// become noise. A hook that always fires is a hook that gets disabled.
//
// NARROWNESS, as the two conjuncts the trigger actually requires:
//   1. a COUNT - an integer adjacent (0-2 qualifier words) to a countable noun, so
//      dates, versions, durations and percentages can never match;
//   2. a RESTATEMENT marker on the count's line or one adjacent line - correction,
//      revision, "not 4", "my earlier count", "survives", "remaining", "from 4 to 5";
// and then the missing-evidence test, over the whole message: no POPULATION and no
// WINDOW anywhere.
//
// Anti-noise is deliberate, not accidental: `correct`, `actually` and `remaining` are
// ordinary English, so each one is ANDed with a real count on a real noun. None of
// them alone can fire this hook, and a date, a version, a duration or a percentage
// can never reach the count pattern in the first place.
//
// EVIDENCE FOR, not against. POPULATION is satisfied by an explicit marker, a
// denominator ("of 386", "3 of 12"), or a stated root (a path). WINDOW is satisfied
// by an explicit marker, an ISO date, "as of / since / on <date>", a clock time, or
// "today / yesterday / this run". A backticked FILTER (`adsnames-*`) deliberately
// does NOT satisfy POPULATION: it names what was excluded, not what was searched,
// which is the whole reason the second observed instance fired. The consequence,
// stated rather than hidden: a report that establishes its population anywhere in the
// body passes every restated count in that body. This hook refuses the unbound
// report, not the locally wrong sentence; refining that would need per-count scoping
// and would multiply false positives on multi-measurement reports.
//
// LOOP SAFETY. Two independent one-shot guards: the runtime's `stop_hook_active`
// flag, and a session-keyed marker in PLUGIN_DATA. The marker lives in its OWN
// namespace (`count-population.continued.*`) and must stay there: if it shared a
// sibling's marker file, whichever hook ran second would read the first one's marker
// and silently pass. That coupling is invisible in a per-hook read.
//
// rc contract: 0 = silent (including every internal error), 1 = block with a reason
// on stdout. This hook never emits 2: an `rc` carries a VERDICT, never a CAUSE, and a
// crash here must stay indistinguishable from "nothing to say" rather than from a
// real RED.
import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { fingerprint, parsePayload, readStdin, record, resolveDataDir } from "./ledger.mjs";

/**
 * Countable nouns. A number only counts when it modifies one of these, which is
 * what keeps "2026-10-06", "v1.2.3", "120 s" and "40%" out of scope by construction
 * rather than by a later filter.
 */
export const COUNT_NOUNS = [
  "files?",
  "director(?:y|ies)",
  "dirs?",
  "folders?",
  "tarballs?",
  "lanes?",
  "agents?",
  "sub-?agents?",
  "tasks?",
  "commits?",
  "pull requests?",
  "prs?",
  "hooks?",
  "guards?",
  "tests?",
  "arms?",
  "gates?",
  "scripts?",
  "modules?",
  "cards?",
  "entries",
  "rows?",
  "items?",
  "findings?",
  "errors?",
  "warnings?",
  "blocks?",
  "names?",
  "receipts?",
  "workers?",
  "repos?",
  "branches?",
  "tools?",
  "servers?",
  "nodes?",
  "seats?",
  "packages?",
  "cases?",
  "failures?",
  "issues?",
  "diffs?",
  "hunks?",
  "transcripts?",
  "sessions?",
  "plugins?",
];

/** Up to two qualifier words, or one backticked pattern: "7 `adsnames-*` directories". */
const QUALIFIER = "(?:[A-Za-z][\\w.*?-]*|`[^`]{1,40}`)";

/**
 * The COUNT pattern. Markdown emphasis around the number is tolerated because these
 * reports bold their numbers: "- **7** `adsnames-*` directories survive".
 */
export function countRe() {
  return new RegExp(`\\b(\\d{1,7})[*_]{0,3}\\s+(?:${QUALIFIER}\\s+){0,2}(?:${COUNT_NOUNS.join("|")})\\b`, "gi");
}

/**
 * The RESTATEMENT markers. None of these alone can fire the hook; see NARROWNESS.
 *
 * TUNED BY A RED ARM, not by taste. G6 in the selftest is the prose sentence
 * "Actually the 3 hooks each took 15 minutes..." and a bare `\bactually\b` fired on
 * it: `actually` is a discourse connective, not a correction marker, and it makes
 * this hook fire on ordinary narrative. The marker is therefore bound to what
 * actually follows it - a digit, or an explicit count claim - which keeps the real
 * case ("actually 27 lanes") and drops the connective. The same binding was applied
 * to `in fact`, and bare `correct`/`turns out` were dropped for the same reason:
 * `correcting`, `corrected` and `correction` carry the meaning without the noise.
 */
export const RESTATEMENT = [
  "\\bnot\\s+(?:\\d|my\\b|one\\b|two\\b|three\\b|four\\b|five\\b)",
  "\\bcorrections?\\b",
  "\\bcorrect(?:ing|ed)\\b",
  "\\brevised\\b",
  "\\brestated\\b",
  "\\bmy\\s+(?:earlier|previous|prior|last|first|original|former)\\s+(?:count|number|figure|tally|total)\\b",
  "\\b(?:earlier|previous|prior|last|original)\\s+(?:count|number|figure|tally)\\b",
  "\\bactually\\s+(?:\\d|there\\s+(?:are|were|is|was))",
  "\\bin\\s+fact\\s+(?:\\d|there\\s+(?:are|were|is|was))",
  "\\bi\\s+(?:said|counted|reported|mis-?counted)\\s+\\d",
  "\\bi\\s+was\\s+(?:wrong|off\\s+by\\s+\\d)",
  "\\boff\\s+by\\s+(?:one|\\d)",
  "\\bfrom\\s+\\d+\\s+to\\s+\\d+",
  "\\bwas\\s+\\d+\\s*,?\\s*(?:now|but)\\s+\\d+",
  "\\bsurviv(?:e|es|ed|ing)\\b",
  "\\bremain(?:s|ing|ed)?\\b",
  "\\bstill\\s+(?:present|alive|there)\\b",
];

const RESTATEMENT_RE = new RegExp(RESTATEMENT.join("|"), "i");

/** POPULATION: what set was counted, and from which root. */
export const HAS_POPULATION = new RegExp(
  [
    "\\bPOPULATION\\b",
    "\\bpopulacao\\b",
    "\\bpopulacao\\s*[=: ]\\d",
    "\\bof\\s+\\d[\\d.,]*",
    "\\bout\\s+of\\s+\\d",
    "\\b\\d+\\s+of\\s+\\d",
    "\\bunder\\s+[A-Za-z]:[\\\\/]",
    "\\b(?:in|from|inside)\\s+`?[A-Za-z]:[\\\\/]",
    "\\brepos?/[A-Za-z0-9_.-]+",
    "/(?:repos|worktrees?|src|tests?)/[A-Za-z0-9_.-]+",
    "[A-Za-z]:\\\\[A-Za-z0-9_.\\\\ -]+",
  ].join("|"),
  "i",
);

/** WINDOW: when the count was taken. */
export const HAS_WINDOW = new RegExp(
  [
    "\\bWINDOW\\b",
    "\\bjanela\\s*[=: ]",
    "\\b20\\d{2}-\\d{2}-\\d{2}\\b",
    "\\b\\d{1,2}:\\d{2}\\b",
    "\\b(?:as of|since|on)\\s+(?:today|yesterday|20\\d{2}-\\d{2}-\\d{2}|\\d{1,2}\\/\\d{1,2}\\/\\d{2,4})",
    "\\b(?:today|yesterday|this (?:run|session|turn|pass|hour|morning))\\b",
  ].join("|"),
  "i",
);

/** Units and decimals that make a digit string prose rather than a count. */
const PROSE_UNIT = new RegExp(
  "^[\\s\\W]{0,3}(?:%|ms|s\\b|secs?\\b|minutes?|mins?\\b|hours?|hrs?\\b|days?\\b|weeks?|kb|mb|gb|kib|mib|b\\b)",
  "i",
);
const PROSE_CONTEXT = /\d{4}-\d{2}-\d{2}|\d{1,2}\/\d{1,2}\/\d{2,4}|v\d+(?:\.\d+)+/i;

/**
 * A digit string adjacent to a countable noun can still be prose: "15 minutes of wall
 * clock", "v2 files", "3 of the 2026-10-06 runs". Reject those.
 */
function isProseNumber(line, start, token) {
  if (!/^\d{1,7}$/.test(token)) return true;
  const before = line.slice(Math.max(0, start - 14), start);
  if (PROSE_CONTEXT.test(before)) return true;
  const after = line.slice(start + token.length);
  if (PROSE_UNIT.test(after)) return true;
  return false;
}

/** The count's own line plus one adjacent line on each side: the local block. */
function localBlock(lines, i) {
  const lo = Math.max(0, i - 1);
  const hi = Math.min(lines.length - 1, i + 1);
  return lines.slice(lo, hi + 1).join("\n");
}

/**
 * Find every restated count in a message.
 * Returns [{ line, text, count }], or [] when the message contains none.
 * This is the whole trigger; judge() adds only the missing-evidence test.
 */
export function findRestatedCounts(message) {
  if (typeof message !== "string" || message === "") return [];
  const lines = message.split(/\r?\n/);
  const found = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const re = countRe();
    if (!re.test(line)) continue;
    if (!RESTATEMENT_RE.test(localBlock(lines, i))) continue;
    const scan = countRe();
    let m;
    while ((m = scan.exec(line)) !== null) {
      const token = m[1];
      const start = m.index + (m[0].indexOf(token) >= 0 ? m[0].indexOf(token) : 0);
      if (isProseNumber(line, start, token)) continue;
      found.push({ line: i, count: token, text: m[0].trim() });
    }
  }
  return found;
}

/**
 * Returns "COMPLIANT" | "VIOLATION" | "NOVALUE".
 * COMPLIANT means: no restated count, or the report establishes a population and a
 * window somewhere. VIOLATION means: a restated count and neither of them.
 */
export function judge(message) {
  if (typeof message !== "string" || message.trim() === "") return "NOVALUE";
  if (findRestatedCounts(message).length === 0) return "COMPLIANT";
  if (HAS_POPULATION.test(message) && HAS_WINDOW.test(message)) return "COMPLIANT";
  return "VIOLATION";
}

/** Which of the two evidence fields the report is missing. */
export function missingEvidence(message) {
  const missing = [];
  if (!HAS_POPULATION.test(message)) missing.push("POPULATION (what set was counted, from which root)");
  if (!HAS_WINDOW.test(message)) missing.push("WINDOW (when the count was taken)");
  return missing;
}

/**
 * The reason. It names the counts back as number+noun only - never the whole line -
 * so nothing from the report body other than a digit and a noun can reach stdout.
 * No credential, token, path or environment value is read, logged or printed.
 */
export function reason(counts, message) {
  const named = counts.map((c) => "`" + c.text.replace(/[`*_]/g, "").trim() + "`").join(", ");
  return (
    "You restated or corrected a count in this report: " + named + ".\n" +
    "Missing: " + missingEvidence(message).join("; ") + ".\n" +
    "A corrected or surviving count is the number a reader will re-use and reconcile " +
    "against the one you just replaced, so it must say WHAT was counted and from WHICH " +
    "root, and WHEN. A backticked filter is not a population: it names what was " +
    "excluded, not what was searched. State both, or downgrade the number to what you " +
    "actually measured. If the count is genuinely ungrounded, say so plainly instead of " +
    "publishing a figure. Law of 2026-09-25. One continuation only, then the turn ends " +
    "either way."
  );
}

function markerPath(session) {
  const dir = resolveDataDir();
  if (!dir) return null;
  // Own namespace, asserted not inherited - see LOOP SAFETY above.
  return join(dir, `count-population.continued.${String(session).replace(/[^A-Za-z0-9._-]/g, "_")}`);
}

function alreadyContinued(session) {
  try {
    const p = markerPath(session);
    if (!p || !existsSync(p)) return false;
    return readFileSync(p, "utf8").trim() === "1";
  } catch {
    return false;
  }
}

function markContinued(session) {
  try {
    const p = markerPath(session);
    if (p && !existsSync(p)) appendFileSync(p, "1\n", "utf8");
  } catch {
    /* a marker we cannot write must not break the turn */
  }
}

async function main() {
  const raw = await readStdin();
  const payload = parsePayload(raw);
  const event = payload.hook_event_name || "unknown";
  const message = payload.last_assistant_message;
  const session = payload.session_id || "unknown";
  const verdict = judge(message);

  if (verdict === "NOVALUE") {
    record({ event, verdict, action: "none", why: "no_last_assistant_message", session });
    return 0;
  }

  const counts = findRestatedCounts(message);

  if (verdict === "COMPLIANT") {
    record({ event, verdict, action: "pass", session, restated_counts: counts.length, msg_sha: fingerprint(message) });
    return 0;
  }

  // Both guards must fire before any block, and independently of each other.
  if (payload.stop_hook_active === true) {
    record({ event, verdict, action: "pass", why: "stop_hook_active_guard", session, restated_counts: counts.length });
    return 0;
  }
  if (alreadyContinued(session)) {
    record({ event, verdict, action: "pass", why: "session_marker_guard", session, restated_counts: counts.length });
    return 0;
  }

  markContinued(session);
  record({ event, verdict, action: "block", session, restated_counts: counts.length, msg_sha: fingerprint(message) });
  process.stdout.write(JSON.stringify({ decision: "block", reason: reason(counts, message) }) + "\n");
  return 1;
}

// Run only as the entry point. An unconditional `main()` would fire the hook on
// import - which is exactly what a selftest does to reach `judge()` - and a hook that
// runs during a test is a test that measures the wrong thing.
if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main().then(
    (code) => {
      process.exitCode = code;
    },
    () => {
      // A crash is not a verdict: exit 0 in silence rather than manufacture a block.
      process.exitCode = 0;
    },
  );
}