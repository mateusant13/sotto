// check-open-items.mjs - Stop / SubagentStop hook.
//
// THE LAW. Owner directive, 2026-10-03, verbatim:
//   "todo report meu termina com 'what's next or what i did not done' ou algo parecido.
//    caso realmente falte algo. se realmente tiver essa secao na tua mensagem, um hook
//    dispara falando pra tu fazer o que tu disse que falta"
//
// WHY THIS EXISTS AND NOT A REMINDER. The sibling omp-plane guard
// `unfinished-obligation-guard.ts` states the distinction it is modelled on:
// "A gate that can be read and ignored is a paragraph." This refuses the turn that
// ENDS with an admitted debt and no enumeration, so "the turn ended" and "the debt
// was named" become the same event.
//
// MEASURED MOTIVE. Today this house had 613 delivered lanes with 0 collectable
// artifacts, and 103 `interrupted` sessions whose work nobody read. A report that
// says "several things were not verified" and then stops is exactly how that
// happens: the admission is real, and nothing acts on it.
//
// WHAT IT READS. `last_assistant_message` from the hook payload, nothing else - the
// same sufficiency argument as check-spec-line.mjs: that field IS the closing
// utterance at the moment the report is complete.
//
// THE TRIGGER IS DELIBERATELY NARROW, and this is the load-bearing design decision.
// An earlier draft triggered on "not verified". A NOT-VERIFIED section is a REQUIRED
// coverage field on every deliverable, not an admission of an open ACTION, so that
// draft would have fired on essentially every report. A hook that always fires is a
// hook nobody consults - and a hook that always fires trains the agent to route
// around it, which is strictly worse than no hook. The trigger list below is phrases
// that cannot plausibly appear in a completed report. "pending" and "blocked" were
// REMOVED for exactly that reason: they are ordinary technical vocabulary.

import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { fingerprint, parsePayload, readStdin, record, resolveDataDir } from "./ledger.mjs";

/** Phrases that admit unfinished work. None of them is ordinary report vocabulary. */
const ADMITS_OPEN = new RegExp(
  [
    "\\bi did not\\b",
    "\\bdid not do\\b",
    "\\bnao fiz\\b",
    "\\bnão fiz\\b",
    "\\boutstanding\\b",
    "\\bstill open\\b",
    "\\bunresolved\\b",
    "\\bleft open\\b",
    "\\bcould not determine\\b",
    "\\bcouldn't determine\\b",
    "\\bremains to be done\\b",
  ].join("|"),
  "i",
);

/** The section heading, in any of the shapes actually used. */
const SECTION = /^[ \t#*_]*(what'?s next|what i did not do|next steps?|open items?|what'?s outstanding)\b/im;

export const TAIL_WINDOW_LINES = 12;

/** A section that exists but enumerates nothing is not a section. */
function hasEnumeratedItem(message) {
  const lines = String(message).split(/\r?\n/);
  let i = 0;
  while (i < lines.length) {
    if (SECTION.test(lines[i])) {
      for (let j = i + 1; j < lines.length; j += 1) {
        const t = lines[j].trim();
        if (SECTION.test(lines[j])) return false; // next section, nothing found
        if (/^#{1,6}\s/.test(t)) return false; // next heading
        if (/^([-*+]|\d+[.)])\s+\S/.test(t)) return true; // a real item
      }
      return false;
    }
    i += 1;
  }
  return false;
}

/**
 * Returns "COMPLIANT" | "VIOLATION" | "NOVALUE".
 * COMPLIANT also covers the case the owner cares about most: a report that
 * genuinely has nothing outstanding. Silence is not a debt.
 */
export function judge(message) {
  if (typeof message !== "string" || message.trim() === "") return "NOVALUE";
  const admits = ADMITS_OPEN.test(message);
  if (!admits) return "COMPLIANT";
  return hasEnumeratedItem(message) ? "COMPLIANT" : "VIOLATION";
}

const REASON =
  "This report admits unfinished work and does not enumerate it. Add a closing section " +
  "named `## WHAT'S NEXT / WHAT I DID NOT DO` with one item per outstanding thing, each " +
  "with a verb and a target:\n" +
  "- <verb> <target>            (work I will do)\n" +
  "- <verb> <target>            (a decision only the owner can make - say so)\n" +
  "Owner directive of 2026-10-03. If there is genuinely nothing outstanding, the absence " +
  "of the section is your claim that nothing is - make it deliberately. One continuation " +
  "only, then the turn ends either way.";

/** Session-keyed one-shot marker, independent of the runtime's stop_hook_active flag. */
function alreadyContinued(session) {
  try {
    const dir = resolveDataDir();
    if (!dir) return false;
    const p = join(dir, `open-items.continued.${String(session).replace(/[^A-Za-z0-9._-]/g, "_")}`);
    if (!existsSync(p)) return false;
    return readFileSync(p, "utf8").trim() === "1";
  } catch {
    return false;
  }
}

function markContinued(session) {
  try {
    const dir = resolveDataDir();
    if (!dir) return;
    const p = join(dir, `open-items.continued.${String(session).replace(/[^A-Za-z0-9._-]/g, "_")}`);
    if (!existsSync(p)) appendFileSync(p, "1\n", "utf8");
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

  // NO-VERDICT is never a pass and never a block. No closing message means nothing
  // to judge; blocking on an absent input would be a false positive.
  if (verdict === "NOVALUE") {
    record({ event, verdict, action: "none", why: "no_last_assistant_message", session });
    process.exit(0);
  }
  if (verdict === "COMPLIANT") {
    record({ event, verdict, action: "pass", session, msg_len: message.length, msg_sha: fingerprint(message) });
    process.exit(0);
  }

  // Two independent one-shot guards. Either alone would do; both together mean a
  // lost runtime flag cannot produce a continuation loop.
  if (payload.stop_hook_active === true) {
    record({ event, verdict, action: "pass", why: "stop_hook_active_guard", session });
    process.exit(0);
  }
  if (alreadyContinued(session)) {
    record({ event, verdict, action: "pass", why: "session_marker_guard", session });
    process.exit(0);
  }

  markContinued(session);
  record({ event, verdict, action: "block", session, msg_len: message.length, msg_sha: fingerprint(message) });
  process.stdout.write(JSON.stringify({ decision: "block", reason: REASON }) + "\n");
  process.exit(0);
}

main();
