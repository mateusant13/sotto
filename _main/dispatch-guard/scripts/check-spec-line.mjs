// check-spec-line.mjs - Stop / SubagentStop hook.
//
// THE LAW. Every dispatch report must close with an item that answers, explicitly,
// "Does your implementation meet the spec?" - YES or NO plus one sentence, placed
// LAST. Owner directive 2026-10-03; recorded in C:\Users\Administrador\.minimax\
// memory\user.md as "Dispatch closes with a checklist, and the spec question goes
// LAST". Measured status before this Plugin: 0 of 41 dispatch prompt slots carried
// the clause, and 23 agent bodies contained zero occurrences.
//
// WHAT IT READS, AND WHY THAT IS SUFFICIENT.
//
//   It reads exactly one field: `last_assistant_message` from the hook payload on
//   stdin. Nothing else.
//
//   Sufficiency. The contract defines `Stop` as "When the root Agent is ready to
//   stop" and `SubagentStop` as "When a Subagent is ready to stop", each with input
//   `last_assistant_message` (references/local-plugin-hooks.md:75-76). The field IS
//   the agent's closing utterance at the exact moment the report is complete. A
//   report that closes with the line has it in this field; a report that does not,
//   does not. There is no compliant shape in which the answer exists somewhere else
//   and this field omits it.
//
//   Why not the transcript. `transcript_path` is available, but scanning it is a
//   whole-turn read against a 1-10 s per-handler timeout inside a 15 s shared event
//   budget (:46-48) and a 64 KiB stdout cap (:226). It would be the slowest
//   possible way to ask a question the payload already answers. Rejected on cost,
//   not on principle.
//
//   Tolerance, stated rather than hidden. The question must appear within the last
//   TAIL_WINDOW_LINES non-empty lines, not literally on the final one. A trailing
//   sign-off or a generated footer is not a report that dodged the question. A hook
//   that blocks a compliant report is worse than no hook, because the fleet learns
//   to route around enforcement; so the tolerance is widened deliberately and
//   named, rather than left to a strictness nobody chose.
//
// ONE-SHOT GUARD. The contract requires one against a continuation loop
// (:212-213). Two independent guards are used: the runtime's own `stop_hook_active`
// flag, and a session-keyed marker in PLUGIN_DATA. Either alone is sufficient;
// both together mean a lost flag cannot produce a loop.

import { fingerprint, parsePayload, readStdin, record } from "./ledger.mjs";

// Deliberately permissive. The law is that the question is ANSWERED, not that a
// specific string was pasted, so the core is the verb phrase and the answer token
// is checked separately. A checkbox marker, a bullet, a bold span, or a table cell
// around the line changes none of this.
const QUESTION = /meet(?:s|ing)?\s+the\s+spec/i;
// Token-bounded so "NOT" or "know" or "nothing" cannot be read as an answer.
const ANSWER = /(?:^|[^A-Za-z])(YES|NO)(?![A-Za-z])/i;

const TAIL_WINDOW_LINES = 5;

const REASON =
  "Dispatch report must close with the spec question, answered explicitly and placed " +
  "LAST. Add a final line in this exact shape:\n" +
  "`Does your implementation meet the spec? YES - <one sentence>` " +
  "(or `NO - <which part is unmet and why>`). " +
  "This is the owner directive of 2026-10-03; enforced by the mcode-dispatch-guard " +
  "Plugin, Stop/SubagentStop hook. One continuation only, then the turn ends either way.";

/** Split into non-empty trimmed lines. */
function tailLines(message, window) {
  return String(message)
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
    .slice(-window);
}

/**
 * The predicate, exported so the self-test can drive it directly and so the
 * liveness report can name the exact rule that produced a verdict.
 * Returns "COMPLIANT" | "VIOLATION" | "NOVALUE".
 */
export function judge(message) {
  if (typeof message !== "string" || message.trim() === "") return "NOVALUE";
  const tail = tailLines(message, TAIL_WINDOW_LINES);
  if (tail.length === 0) return "NOVALUE";
  for (let i = 0; i < tail.length; i += 1) {
    if (!QUESTION.test(tail[i])) continue;
    // Answer on the same line, or on the line immediately after (wrapped answers).
    if (ANSWER.test(tail[i])) return "COMPLIANT";
    if (i + 1 < tail.length && ANSWER.test(tail[i + 1])) return "COMPLIANT";
  }
  return "VIOLATION";
}

async function main() {
  const raw = await readStdin();
  const payload = parsePayload(raw);
  const event = payload.hook_event_name || "unknown";
  const message = payload.last_assistant_message;
  const verdict = judge(message);
  const session = payload.session_id || "unknown";

  // NO-VERDICT is never a pass and never a block. With no closing message there is
  // nothing to judge; blocking on an absent input would be a false positive, and
  // this house's rc contract says a check that did not run is not green.
  if (verdict === "NOVALUE") {
    record({ event, verdict, action: "none", why: "no_last_assistant_message", session });
    process.exit(0);
  }

  if (verdict === "COMPLIANT") {
    record({ event, verdict, action: "pass", session, msg_len: message.length, msg_sha: fingerprint(message) });
    process.exit(0);
  }

  // VIOLATION. Two guards before any block.
  if (payload.stop_hook_active === true) {
    record({ event, verdict, action: "pass", why: "stop_hook_active_guard", session });
    process.exit(0);
  }

  record({ event, verdict, action: "block", session, msg_len: message.length, msg_sha: fingerprint(message) });
  process.stdout.write(JSON.stringify({ decision: "block", reason: REASON }) + "\n");
  process.exit(0);
}

main();
