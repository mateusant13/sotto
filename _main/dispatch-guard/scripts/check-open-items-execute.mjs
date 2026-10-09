// check-open-items-execute.mjs - Stop / SubagentStop hook.
//
// THE LAW. Owner directive, 2026-10-04, in the owner's own words:
//   "faz um hook esperto: se o agente escreve whats left e did not do no final,
//    o hook manda mensagem na hora, falando pra fazer exatamente isso"
//
// WHY THIS IS A DIFFERENT HOOK AND NOT A TUNING OF check-open-items.mjs.
// That sibling asks a NARROWER question: "if you admit a debt, did you NAME it?"
// It blocks an unenumerated admission and is satisfied by the section existing.
// It is therefore SILENT on the case the owner is now pointing at: a report that
// did enumerate its debts, cleanly, one per line, and then stopped. The debt is
// legible and nothing acts on it. This hook fires on that case and on no other.
//
// THE DESIGN DECISION THAT DECIDES WHETHER THIS HOOK IS USEFUL.
// "The section exists" is NOT the trigger. A section exists on almost every real
// report, and the items in it are of two incompatible kinds:
//
//   * an OWNER ITEM - a decision only the owner can make ("PENDENTE-DONO",
//     "autoriza", "espera por ti"). The agent CANNOT execute it. Firing on it
//     produces an instruction the agent cannot obey, which is worse than silence:
//     it teaches the reader that this hook is noise.
//   * an AGENT ITEM - work the agent itself said it will do. This is the only
//     thing the hook is allowed to act on.
//
// So the trigger is: a parsed section, at least one enumerated item, and at least
// one item classified AGENT. Zero agent items is a pass, recorded as such, with the
// owner items counted so the pass is itself evidence rather than a shrug.
//
// WHY THE REASON ECHOES THE ITEMS BACK. "Go do what you said you did not do" is a
// sentence an agent can satisfy by re-asserting that it will do them. The reason
// therefore quotes the extracted items verbatim, numbered, and asks for the work in
// this turn. The instruction and the debt are the same string.
//
// LOOP SAFETY. Two independent one-shot guards, matching the sibling's design: the
// runtime's `stop_hook_active` flag, and a session-keyed marker file. The marker is
// in its OWN namespace (`open-items-execute.continued.*`) and must stay there: if it
// shared the sibling's `open-items.continued.*` file, whichever hook ran second
// would read the first one's marker and silently pass, and neither would ever fire
// twice. That coupling is invisible in a per-hook read and is the reason the
// namespace is asserted, not assumed.

import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { fingerprint, parsePayload, readStdin, record, resolveDataDir } from "./ledger.mjs";

/** The section heading, in the shapes actually used. Same set as the sibling. */
export const SECTION = /^[ \t#*_]*(what'?s next|what i did not do|next steps?|open items?|what'?s outstanding)\b/im;

/**
 * An item the OWNER must resolve. The agent cannot execute any of these, so a hook
 * that fires on them is a hook that cannot be obeyed.
 *
 * Matched against the item text only, case-insensitively. Kept narrow on purpose:
 * "waiting" alone is ordinary English in a report ("I am waiting on the background
 * task"), so the phrases below all carry the owner as their subject.
 */
export const OWNER_ITEM = new RegExp(
  [
    "\\bpendente[- ]?dono\\b",
    "\\bowner[- ]?decides?\\b",
    "\\bonly the owner\\b",
    "\\bso (?:only )?(?:you|the owner) can\\b",
    "\\bdecis[aã]o do dono\\b",
    "\\bpergunta ao dono\\b",
    "\\bask the owner\\b",
    "\\bowner (?:must|has to|needs to) (?:decide|choose|pick|rule|answer)\\b",
    // Portuguese is conjugated, so the stem is matched, not one finite form.
    // "autoriza" + \\b does NOT match "autorizas": there is no word boundary
    // before the final s. The first version of this rule had that bug and the
    // anti-noise arm A2 caught it - the arm existed precisely to catch it.
    "\\bautoriz\\w*\\b",
    "\\baguard(?:a|ando|o)\\s+(?:a\\s+)?(?:tua|your|do dono|do owner|te)\\b",
    "\\baguard(?:a|ando|o)\\s+(?:a\\s+)?(?:decis[aã]o|resposta|veredicto|resposta)\\b",
    "\\bwaiting (?:on|for) (?:you|the owner|your)\\b",
    "\\byour call\\b",
    "\\bneeds? (?:an?\\s+)?(?:owner\\s+)?decision\\b",
  ].join("|"),
  "i",
);

/** True when the line is a real enumerated item, not prose inside the section. */
function isItemLine(trimmed) {
  return /^([-*+]|\d+[.)])\s+\S/.test(trimmed);
}

/**
 * Parse the section into items. Returns [] when the section is absent or enumerates
 * nothing - an empty section is not a section, same rule as the sibling.
 */
export function extractItems(message) {
  const lines = String(message).split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    if (!SECTION.test(lines[i])) continue;
    const items = [];
    for (let j = i + 1; j < lines.length; j += 1) {
      const raw = lines[j];
      const t = raw.trim();
      if (SECTION.test(raw)) break; // next section
      if (/^#{1,6}\s/.test(t)) break; // next heading
      if (isItemLine(t)) items.push(t.replace(/^([-*+]|\d+[.)])\s+/, "").trim());
    }
    return items;
  }
  return [];
}

export function classify(item) {
  return OWNER_ITEM.test(item) ? "OWNER" : "AGENT";
}

/**
 * Returns "COMPLIANT" | "VIOLATION" | "NOVALUE".
 * COMPLIANT means: nothing for the agent to go execute right now. That is the
 * correct verdict for a clean report, AND for a report whose only open items are
 * the owner's to answer.
 */
export function judge(message) {
  if (typeof message !== "string" || message.trim() === "") return "NOVALUE";
  const items = extractItems(message);
  if (items.length === 0) return "COMPLIANT";
  const agentItems = items.filter((it) => classify(it) === "AGENT");
  return agentItems.length > 0 ? "VIOLATION" : "COMPLIANT";
}

export function reason(agentItems) {
  const numbered = agentItems.map((it, i) => `${i + 1}. ${it}`).join("\n");
  return (
    "You ended this turn having listed work you said you would do. Do it now, in this turn, " +
    "before writing anything else. These are your own items, copied back verbatim from your " +
    "closing section:\n\n" +
    numbered +
    "\n\nExecute them in order and report what each one closed with. If one of them turns out to " +
    "be impossible, say which and why, and move it to a section headed `OWNER DECISIONS` - do not " +
    "leave it sitting in a list of things you will do later. Listing a debt is not discharging it. " +
    "Owner directive of 2026-10-04. One continuation only, then the turn ends either way."
  );
}

function markerPath(session) {
  const dir = resolveDataDir();
  if (!dir) return null;
  // Namespace asserted, not inherited: see the LOOP SAFETY note above.
  return join(dir, `open-items-execute.continued.${String(session).replace(/[^A-Za-z0-9._-]/g, "_")}`);
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
    process.exit(0);
  }

  const items = extractItems(message);
  const agentItems = items.filter((it) => classify(it) === "AGENT");
  const ownerItems = items.filter((it) => classify(it) === "OWNER");

  if (verdict === "COMPLIANT") {
    record({
      event,
      verdict,
      action: "pass",
      session,
      items_total: items.length,
      items_agent: agentItems.length,
      items_owner: ownerItems.length,
      why: items.length === 0 ? "no_section_or_no_items" : "only_owner_items",
      msg_sha: fingerprint(message),
    });
    process.exit(0);
  }

  if (payload.stop_hook_active === true) {
    record({ event, verdict, action: "pass", why: "stop_hook_active_guard", session, items_agent: agentItems.length });
    process.exit(0);
  }
  if (alreadyContinued(session)) {
    record({ event, verdict, action: "pass", why: "session_marker_guard", session, items_agent: agentItems.length });
    process.exit(0);
  }

  markContinued(session);
  record({
    event,
    verdict,
    action: "block",
    session,
    items_total: items.length,
    items_agent: agentItems.length,
    items_owner: ownerItems.length,
    msg_sha: fingerprint(message),
  });
  process.stdout.write(JSON.stringify({ decision: "block", reason: reason(agentItems) }) + "\n");
  process.exit(0);
}

// Run only as the entry point. Unconditional `main()` here would fire the hook
// on import - which is exactly what a selftest does to reach `judge()` - and a
// hook that runs during a test is a test that measures the wrong thing.
if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) main();
