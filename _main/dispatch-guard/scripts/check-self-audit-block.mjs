// check-self-audit-block.mjs - SubagentStop hook.
//
// THE LAW. Every agent closes with a SELF-AUDIT (AGENTS.md, P1, owner 2026-09-22).
// Its oracle is `bash scripts/self-audit-lint.sh` and its verdict token for absence is
// SELF-AUDIT-MISSING. The oracle exists and works. What it lacked was a CALLER, and an
// oracle with no caller is a document, not a gate - so this file is the caller.
//
// WHAT IT READS, AND WHY THAT IS SUFFICIENT.
//
//   Exactly one field: `last_assistant_message` from the hook payload on stdin.
//   Same field, same sufficiency argument, same rejection of `transcript_path`, as
//   check-spec-line.mjs: the contract defines `SubagentStop` as "When a Subagent is
//   ready to stop" with input `last_assistant_message`
//   (references/local-plugin-hooks.md:75-76), so the field IS the subagent's closing
//   report at the moment it is complete. A whole-turn transcript read is the slowest
//   possible way to ask a question the payload already answers, against a 1-10 s
//   per-handler timeout inside a 15 s shared event budget.
//
// WHY FIELD-SHAPED DETECTION, AND WHY THE SPELLINGS ARE PORTUGUESE.
//
//   The law says the gate-doubt sub-questions must be present "as fields, not as
//   passing prose", so this file detects a FIELD: an optional list marker, then a
//   LABEL, then a separator (`:` / `-` / en / em dash), matched WHOLE. Whole-label
//   matching is what makes prose impossible to satisfy - the label of
//   "I read the gate-doubt section of AGENTS.md today." is that entire sentence, and
//   it does not equal `gate-doubt`. The oracle's own control arm is the same idea.
//
//   MEASURED, and this is the load-bearing measurement of the whole file:
//     population  : 1944 *.md directly under I:\!manager\runs
//     window      : none - every file, mtime unfiltered
//     instrument  : read each file, locate the SELF-AUDIT block heading, take the next
//                   80 lines, and test the accepted spellings of each field
//     receipts carrying a `## SELF-AUDIT` block : 1456 (74.9%)
//     campo PT spellings  : protocolos em falta 1413 (97.0%) - confianca 1103 (75.8%)
//                           verificacao adicional 1105 (75.9%) - checkboxes novas 1295
//                           (88.9%) - review por outro subagente 1430 (98.2%)
//                           - nao verificado 900 (61.8%)
//     gate-doubt 1430 (98.2%) - verde-de-verdade 1423 (97.7%) - falta-no-gate 1401
//     (96.2%) - gate-melhor 1361 (93.5%)
//
//   So the corpus writes the fields in Portuguese and the constitution writes them in
//   English, and BOTH are accepted. A field check that honoured only the English
//   spelling would have refused the large majority of the receipts this house has
//   actually closed. Both spellings are therefore first-class, which is the same
//   conflict the oracle already settled for GATE_RE at scripts/self-audit-lint.sh:164
//   with two accepted spellings rather than one.
//
// DIVERGENCE FROM THE ORACLE - DECLARED, NOT HIDDEN.
//
//   This hook is STRICTER than `self-audit-lint.sh` in two measured ways, because the
//   brief defines a conforming block as the full 7 fields plus all 3 gate-doubt
//   sub-questions, and the oracle checks neither:
//     1. the oracle requires the BLOCK + gate-doubt + verde-de-verdade + falta-no-gate
//        only (self-audit-lint.sh:634-639). It never checks the other 6 fields.
//     2. the oracle has no GATE_MELHOR_RE. `gate-melhor:` is required here.
//   Measured cost of the strictness, so the owner can rule on it: requiring all 6
//   extra fields would have flagged 38.2% of the 1456 historical receipts on
//   `nao verificado` alone (900/1456 carry it), and requiring gate-melhor would have
//   flagged 6.5% (1361/1456). A report can therefore pass the oracle and be refused by
//   this hook. That is a real divergence, it is named rather than smoothed over, and
//   the block reason always lists the exact fields owed so a false positive costs one
//   continuation rather than a dead turn.
//
// VERDICT VOCABULARY, AND WHY rc IS THE VERDICT.
//
//   0 CLEAN   - a conforming block, or the reasoned `self-audit: n/a - <reason>` form.
//   1 VIOLATION - the report was READ and does not conform. Named verdicts:
//       SELF-AUDIT-MISSING      no block and no reasoned exemption
//       SELF-AUDIT-FIELDS-MISSING  block present, some of the 7 fields absent
//       GATE-DOUBT-MISSING      block present, no gate-doubt FIELD
//       GATE-DOUBT-SHALLOW      gate-doubt field present, a sub-question absent
//   2 NO-VERDICT - the gate could NOT reach a verdict. Never a pass, never a block:
//       SELF-AUDIT-NO-VERDICT   no `last_assistant_message` to read
//       SELF-AUDIT-SCAN-UNREADABLE  the decision function DIED
//   3 USAGE    - the command line was wrong. Nothing was judged.
//
//   The rc=1 / rc=2 split is the whole point. Node exits 1 on an uncaught exception,
//   so a script that dies inside its own decision function is indistinguishable from
//   one that caught a violation - a crash wearing the clothes of a RED. Every throw
//   here is caught and mapped to rc 2 with SELF-AUDIT-SCAN-UNREADABLE, the same name
//   the oracle uses for an unreadable scan (self-audit-lint.sh:628). Arm `crash`
//   injects a fault to prove that boundary holds.
//
// FAIL-OPEN, AND THE EVIDENCE THAT BREAKS THE SYMMETRY.
//
//   The contract states that unsupported handlers "normally fail open without a
//   user-facing error" (references/local-plugin-hooks.md:229-230). Fail-open is
//   invisible by construction: a Plugin that never loaded looks exactly like one that
//   is enforcing. This file therefore appends a ledger record on EVERY invocation -
//   CLEAN, EXEMPT, every VIOLATION, every NO-VERDICT, and the crash - and prints a
//   bounded `ledger` diagnostic on stdout, so a reader can always answer "did this run?"
//   and not merely "did it find anything?".
//
//   MEASURED STATE OF THAT QUESTION ON THIS HOST, 2026-10-03: `SubagentStop` has
//   NEVER been observed firing. Measured population: 8 files matching `runtime-*.log`
//   under C:\Users\Administrador\.minimax\v2\observability\logs, window
//   2026-10-02T19:59:58 -> 2026-10-03T02:36:34 local, instrument = full-file literal
//   search for SubagentStop / SubagentStart / hookEventName / hookSpecificOutput.
//   Result 0 runtime-emitted hook events, because no Plugin was installed during that
//   window. So: this file's SCRIPT is verified by --selftest, and its FIRING on this
//   host is UNPROVEN. A green selftest is not a working gate, and the ledger line
//   count is the only thing that tells the two apart.

import { parsePayload, readStdin, record } from "./ledger.mjs";

//
// ---------------------------------------------------------------- the block
//

// Mirrors BLOCK_RE at scripts/self-audit-lint.sh:147, including both boundaries the
// oracle had to add to fix a real false negative (numbered heading) and a real false
// positive (a heading merely STARTING with the token). Kept in lockstep deliberately:
// this hook enforces the same block, so the same two defects cannot be fixed in one
// place and left live in the other.
const BLOCK_HEADING = /^##[ \t]*([0-9]+[.)][ \t]*)?SELF-AUDIT([ \t]|$)/;

// The exempt form. EXEMPT_RE at self-audit-lint.sh:148 is `self-audit: n/a` followed
// by a dash; the reason after that dash is REQUIRED here, because a bare `self-audit:
// n/a` is a rule turned off with no reason recorded, and the owner made the reason
// mandatory for the CACHE/PRICE keys on exactly that reasoning.
const EXEMPT = /self-audit:[ \t]*n\/a[ \t]*[-–—][ \t]*(\S.*)$/i;

//
// ---------------------------------------------------------------- the fields
//

// Whole-label patterns. A field is a LINE whose label equals one of these; the label
// is what sits between an optional list marker and the first separator, with emphasis
// stripped. Equality, not containment, is what rejects prose.
const FIELDS = [
  ["protocols-missing", /^(protocolos?|protocols?)[ \t]+(em[ \t]+falta|faltando|ausentes?|missing)$/i],
  ["extra-verification", /^(verifica(c(ã|a)o|coes|ões)[ \t]+(adicional|adicionais|extra)|extra[ \t]+verification|additional[ \t]+verifications?)$/i],
  ["new-checkboxes", /^(checkboxes?[ \t]+novas?|novas?[ \t]+checkboxes?|new[ \t]+checkboxes?)$/i],
  ["review-by-another-subagent", /^(review([ \t]+por[ \t]+outro[ \t]+sub(agente|agent)|[ \t]+by[ \t]+another[ \t]+subagent)?|review[ \t]+outro[ \t]+subagente)$/i],
  ["confidence", /^(confian(ç|c)a|confidence)$/i],
  ["not-verified", /^(n(ã|a)o[ \t]+verificad(os?|as?)|not[ \t]+verified|what[ \t]+was[ \t]+not[ \t]+verified)$/i],
  ["gate-doubt", /^gate[- \t]?doubt$/i],
];

// The three sub-questions of item 7. The oracle checks the first two
// (VERDE_RE / FALTA_RE, self-audit-lint.sh:165-166) and has NO third; gate-melhor is
// required here per the brief and per AGENTS.md's own item 7 spelling. Declared in the
// divergence note above.
const SUB_QUESTIONS = [
  ["verde-de-verdade", /^verde[- \t]?de[- \t]?verdade$/i],
  ["falta-no-gate", /^falta[- \t]?no[- \t]?gate$/i],
  ["gate-melhor", /^gate[- \t]?melhor$/i],
];

// A field line: optional list marker, then a label, then a separator. The separator
// is optional because AGENTS.md's own item 7 is written `- **Gate-doubt**` with
// nothing after it, and the oracle accepts that spelling (GATE_RE's bold leg).
const LIST_MARKER = /^[ \t]*(?:[-*+][ \t]+|[0-9]+[.)][ \t]+)?/;
const SEPARATOR = /[:–—]|[ \t]-[ \t]/;

/** Strip markdown emphasis so `**gate-doubt**` and `gate-doubt` are one label. */
function deemphasise(s) {
  return s.replace(/[*_`]+/g, "").trim();
}

/**
 * The label a line carries, or null when the line is not a field.
 * Whole-line work: a sentence that merely mentions a field yields a label that is the
 * whole sentence, which then fails every equality test above. That asymmetry is the
 * entire prose defence.
 */
export function fieldLabel(line) {
  const body = String(line).replace(LIST_MARKER, "");
  const sep = body.match(SEPARATOR);
  // With a separator the label is what precedes it; without one the whole line is the
  // label, which still has to equal a field name to count.
  return deemphasise(sep ? body.slice(0, sep.index) : body);
}

/** Every field name present in a block of lines, in first-seen order. */
function collectFields(lines) {
  const found = new Set();
  for (const line of lines) {
    const label = fieldLabel(line);
    if (!label) continue;
    for (const [name, re] of FIELDS) if (re.test(label)) found.add(name);
    for (const [name, re] of SUB_QUESTIONS) if (re.test(label)) found.add(name);
  }
  return found;
}

/**
 * The lines that belong to the SELF-AUDIT block: from the heading to the next `## `
 * heading at or above its level, matching how the oracle delimits its own sections
 * (`if ($0 ~ /^##/) { insec = 0; next }`, self-audit-lint.sh:546).
 */
function blockRegion(lines) {
  const start = lines.findIndex((l) => BLOCK_HEADING.test(l));
  if (start === -1) return null;
  for (let i = start + 1; i < lines.length; i += 1) {
    if (/^##[ \t]/.test(lines[i])) return lines.slice(start + 1, i);
  }
  return lines.slice(start + 1);
}

/**
 * The decision function. Returns a verdict plus the evidence for it.
 * Exported so --selftest can drive it directly and so a reader can name the exact rule
 * that produced a verdict.
 */
export function judge(message) {
  if (typeof message !== "string" || message.trim() === "") {
    return { verdict: "SELF-AUDIT-NO-VERDICT", why: "no_last_assistant_message" };
  }
  const lines = message.split(/\r?\n/);

  // The exemption is checked over the WHOLE message, like the oracle (self-audit-lint.sh:634
  // tests the exempt flag before the block flag), and it requires a reason.
  for (const line of lines) {
    const m = line.match(EXEMPT);
    if (m && m[1].trim() !== "") return { verdict: "EXEMPT", why: "self_audit_na_with_reason" };
  }

  const region = blockRegion(lines);
  if (region === null) return { verdict: "SELF-AUDIT-MISSING", missing: [] };

  const present = collectFields(region);
  const missing = FIELDS.map(([name]) => name).filter((name) => !present.has(name));
  const missingSubs = SUB_QUESTIONS.map(([name]) => name).filter((name) => !present.has(name));

  // Order matters and mirrors the oracle: a missing block outranks everything, a
  // missing gate-doubt outranks a shallow one, and a shallow one outranks a thin
  // block, so a report that is wrong in three ways is told the FIRST thing to fix.
  if (!present.has("gate-doubt")) {
    return { verdict: "GATE-DOUBT-MISSING", missing, missingSubs };
  }
  if (missingSubs.length > 0) {
    return { verdict: "GATE-DOUBT-SHALLOW", missing, missingSubs };
  }
  if (missing.length > 0) {
    return { verdict: "SELF-AUDIT-FIELDS-MISSING", missing, missingSubs };
  }
  return { verdict: "CLEAN", missing: [], missingSubs: [] };
}

const HOWTO =
  "Add a `## SELF-AUDIT` block as a FIELD LIST (each item `- <field>: <answer>`), " +
  "carrying the 7 items: protocolos em falta | protocols missing; verificacao adicional | " +
  "extra verification; checkboxes novas | new checkboxes; review por outro subagente | " +
  "review by another subagent; confianca | confidence; nao verificado | not verified; " +
  "and gate-doubt with all THREE sub-questions as their own fields: `verde-de-verdade:`, " +
  "`falta-no-gate:`, `gate-melhor:`. A bare `self-audit: n/a - <reason>` is also " +
  "accepted. (mcode-dispatch-guard, SubagentStop)";

function blockReason(verdict, why) {
  if (verdict === "SELF-AUDIT-MISSING") {
    return (
      "Subagent report closed without a SELF-AUDIT. " + HOWTO +
      " Oracle: bash scripts/self-audit-lint.sh (token SELF-AUDIT-MISSING)."
    );
  }
  if (verdict === "GATE-DOUBT-MISSING") {
    return (
      "SELF-AUDIT block present but it carries no `gate-doubt` FIELD. " + HOWTO +
      " (A mention of gate-doubt in running prose does not satisfy this.)"
    );
  }
  if (verdict === "GATE-DOUBT-SHALLOW") {
    return (
      "SELF-AUDIT block present and `gate-doubt` is a field, but these sub-questions " +
      "are not present as their own fields: " + why.missingSubs.join(", ") + ". " + HOWTO
    );
  }
  return (
    "SELF-AUDIT block present, but these fields are absent: " + why.missing.join(", ") +
    ". " + HOWTO
  );
}

// A bounded, secret-free diagnostic printed on every path. Its presence is the
// evidence that this hook RAN, which is the only thing distinguishing "it found
// nothing" from "this host never fired it". A hook that fails open leaves no other
// trace at all.
function ledgerLine(ok) {
  return ok
    ? { ledger: "written" }
    : { ledger: "unwritable", why: "PLUGIN_DATA unset or not writable" };
}

const USAGE = `usage: check-self-audit-block.mjs [--selftest] [--help]

  Reads a SubagentStop hook payload on stdin and refuses a subagent report whose
  closing SELF-AUDIT is not conforming. With no arguments it is the hook.

  --selftest   run this gate's own non-vacuity arms; rc 0 only if EVERY declared arm ran
               and every expected rc was observed.
  --help      this text.

EXIT CODES - each one is a VERDICT, and each says what it is a verdict ABOUT:
  0  CLEAN        the report was read and carries a conforming SELF-AUDIT, or the
                  reasoned 'self-audit: n/a - <reason>' form. Verdict token CLEAN/EXEMPT.
  1  VIOLATION    the report was READ and does not conform. Tokens:
                  SELF-AUDIT-MISSING         no block, no reasoned exemption
                  SELF-AUDIT-FIELDS-MISSING  block present, some of the 7 fields absent
                  GATE-DOUBT-MISSING         block present, no gate-doubt FIELD
                  GATE-DOUBT-SHALLOW         gate-doubt field present, a sub-question absent
  2  NO VERDICT   the gate could not reach a verdict. Tokens:
                  SELF-AUDIT-NO-VERDICT      no 'last_assistant_message' was present
                  SELF-AUDIT-SCAN-UNREADABLE the decision function DIED
                  Nothing is claimed about the report; the absence of a finding here
                  is UNKNOWN, not clean.
  3  USAGE        the command line was wrong. No report was judged.

  A CRASH IS NOT A RED. Node exits 1 on an uncaught exception, so a dying script would
  be indistinguishable from a script that caught a violation. Every throw here is
  caught and mapped to rc 2 / SELF-AUDIT-SCAN-UNREADABLE, the same name the oracle uses
  for an unreadable scan. The --selftest arm 'crash' injects a fault to prove it.`;

function usageError(msg) {
  process.stderr.write("check-self-audit-block: USAGE ERROR: " + msg + "\n" + USAGE + "\n");
  process.exit(3);
}

//
// ---------------------------------------------------------------- the hook path
//

async function main() {
  const raw = await readStdin();
  const payload = parsePayload(raw);
  const event = payload.hook_event_name || "SubagentStop";
  const session = payload.session_id || "unknown";
  const message = payload.last_assistant_message;

  let verdict;
  let why = {};
  let threw = null;
  try {
    const judged = judge(message);
    verdict = judged.verdict;
    why = judged;
  } catch (err) {
    // The rc=2 path. Caught here, named, and NOT allowed to become a rc=1.
    verdict = "SELF-AUDIT-SCAN-UNREADABLE";
    threw = err && err.message ? err.message : String(err);
  }

  const clean = verdict === "CLEAN" || verdict === "EXEMPT";
  const noVerdict = verdict === "SELF-AUDIT-NO-VERDICT" || verdict === "SELF-AUDIT-SCAN-UNREADABLE";

  // NO-VERDICT is never a pass and never a block. With no closing message there is
  // nothing to judge, and blocking on an absent input would be a false positive on
  // every call; reporting 0 would be a pass-by-construction, which is the defect this
  // whole family of hooks exists to kill.
  if (noVerdict) {
    const ok = record({
      event, verdict, action: "none", why: why.why || threw || null,
      msg_present: typeof message === "string", session,
    });
    process.stdout.write(JSON.stringify(ledgerLine(ok)) + "\n");
    process.exit(2);
  }

  if (clean) {
    const ok = record({
      event, verdict, action: "pass", session,
      msg_len: message.length, exempt: verdict === "EXEMPT",
    });
    process.stdout.write(JSON.stringify(ledgerLine(ok)) + "\n");
    process.exit(0);
  }

  // VIOLATION. One guard before any block: the runtime's own continuation flag.
  if (payload.stop_hook_active === true) {
    const ok = record({ event, verdict, action: "pass", why: "stop_hook_active_guard", session });
    process.stdout.write(JSON.stringify(ledgerLine(ok)) + "\n");
    process.exit(0);
  }

  const ok = record({
    event, verdict, action: "block", session,
    missing: why.missing || [], missing_subs: why.missingSubs || [],
  });
  process.stdout.write(
    JSON.stringify({ decision: "block", reason: blockReason(verdict, why) }) + "\n",
  );
  process.stdout.write(JSON.stringify(ledgerLine(ok)) + "\n");
  process.exit(1);
}

//
// ---------------------------------------------------------------- the self-test
//

// Every arm declares a name, a payload, and the rc it MUST produce. An arm that
// cannot produce its own RED is not an arm; each of these has a matching mutation
// (see MUTATIONS at the end of the report) that flips the conforming fixture to RED.
const ARMS = [
  {
    name: "conforming-pt",
    want: 0,
    why: "the real shape, measured off SealGuardOrdering.md: PT field names, gate-doubt as a field with all three sub-questions",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: [
        "# receipt",
        "## SELF-AUDIT",
        "- protocolos em falta: nenhum critico",
        "- verificacao adicional: duas, ambas barato",
        "- checkboxes novas: uma, mecanica",
        "- review por outro subagente: nao - razao especifica",
        "- confianca: ALTA no root cause, MEDIA em processo",
        "- nao verificado: o processo vivo, precisa de restart",
        "- gate-doubt:",
        "  - verde-de-verdade: duas corridas que devia desconfiar",
        "  - falta-no-gate: a suite nao prova reflecte o que o LLM pode chamar",
        "  - gate-melhor: ligar o preflight ao guard no arranque",
      ].join("\n"),
    },
  },
  {
    name: "conforming-en",
    want: 0,
    why: "the AGENTS.md spelling, in English, must be equally acceptable - the corpus writes PT and the constitution writes EN",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: [
        "## SELF-AUDIT",
        "- Protocols missing: none blocking",
        "- Extra verification: one cheap probe",
        "- New checkboxes: one, named and mechanical",
        "- Review by another subagent: skipped (orchestrator discretion, no second seat)",
        "- Confidence: HIGH on the root cause, LOW in process",
        "- What was NOT verified: the live process, needs a restart",
        "- **Gate-doubt**",
        "  - **verde-de-verdade:** the first green was constructed, not measured",
        "  - **falta-no-gate:** a cache that hides a route flip still passes",
        "  - **gate-melhor:** invert the gate rather than delete it",
      ].join("\n"),
    },
  },
  {
    name: "no-block",
    want: 1,
    why: "a report with no SELF-AUDIT at all -> SELF-AUDIT-MISSING",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: "# receipt\n\n## Result\n\nChanged two files and ran the gate.\n",
    },
  },
  {
    name: "gate-doubt-shallow",
    want: 1,
    why: "the gate-doubt field is there but verde/falta/gate-melhor are not -> GATE-DOUBT-SHALLOW, and the reason NAMES which are owed",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: [
        "## SELF-AUDIT",
        "- protocolos em falta: nenhum",
        "- verificacao adicional: duas",
        "- checkboxes novas: uma",
        "- review por outro subagente: nao",
        "- confianca: alta",
        "- nao verificado: o processo vivo",
        "- gate-doubt: questionei o gate e nao vi nada troubling",
      ].join("\n"),
    },
  },
  {
    name: "prose-only",
    want: 1,
    why: "EVERY field name and every sub-question is present in the text - and none of them as a field, only inside running sentences -> SELF-AUDIT-MISSING. This is the arm that makes 'as fields, not passing prose' a behaviour: it is the CONTROL for the whole-label equality, and stripping the ^...$ anchors from the field patterns flips it to rc 0.",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: [
        "# receipt",
        "## SELF-AUDIT",
        "I worked through protocolos em falta and verificacao adicional today, and I",
        "added checkboxes novas as a result. For review por outro subagente I had no",
        "seat available. My confianca is high and nao verificado is empty, so I also",
        "weighed gate-doubt, asking verde-de-verdade, falta-no-gate and gate-melhor as I went.",
      ].join("\n"),
    },
  },
  {
    name: "gate-doubt-prose-only",
    want: 1,
    why: "a bare gate-doubt mention inside a otherwise complete field list -> GATE-DOUBT-MISSING. The oracle's own control arm, same shape.",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: [
        "## SELF-AUDIT",
        "- protocolos em falta: nenhum",
        "- verificacao adicional: duas",
        "- checkboxes novas: uma",
        "- review por outro subagente: nao",
        "- confianca: alta",
        "- nao verificado: o processo vivo",
        "I read the gate-doubt section of AGENTS.md today.",
      ].join("\n"),
    },
  },
  {
    name: "exempt-trivial",
    want: 0,
    why: "the trivial form `self-audit: n/a - <reason>` is a lawful close, and the reason is present",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message:
        "# receipt\n\nNo work was done; this is a reading-only turn.\n\nself-audit: n/a - nothing was built or concluded\n",
    },
  },
  {
    name: "exempt-no-reason",
    want: 1,
    why: "a bare `self-audit: n/a` with NO reason is a rule turned off silently, not an exemption -> SELF-AUDIT-MISSING",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: "# receipt\n\nself-audit: n/a\n",
    },
  },
  {
    name: "field-missing",
    want: 1,
    why: "block + gate-doubt complete, but `nao verificado` absent -> SELF-AUDIT-FIELDS-MISSING naming that one field",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: [
        "## SELF-AUDIT",
        "- protocolos em falta: nenhum",
        "- verificacao adicional: duas",
        "- checkboxes novas: uma",
        "- review por outro subagente: nao",
        "- confianca: alta",
        "- gate-doubt:",
        "  - verde-de-verdade: ok",
        "  - falta-no-gate: none",
        "  - gate-melhor: invert the gate",
      ].join("\n"),
    },
  },
  {
    name: "numbered-heading",
    want: 0,
    why: "P1 3bdf951a642ff99bd1af6ea6: a complete block under '## 11. SELF-AUDIT' is GREEN. Removing the enumerator leg is the mutation that turns this RED.",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: [
        "## 11. SELF-AUDIT",
        "- protocolos em falta: nenhum",
        "- verificacao adicional: duas",
        "- checkboxes novas: uma",
        "- review por outro subagente: nao",
        "- confianca: alta",
        "- nao verificado: o processo vivo",
        "- gate-doubt:",
        "  - verde-de-verdade: ok",
        "  - falta-no-gate: none",
        "  - gate-melhor: invert the gate",
      ].join("\n"),
    },
  },
  {
    name: "audity-heading",
    want: 1,
    why: "P3 7be76459ce518db54c43eced: '## SELF-AUDITY' is not the heading, and must not satisfy it. Removing the closing boundary is the mutation.",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: [
        "## SELF-AUDITY",
        "- protocolos em falta: nenhum",
        "- verificacao adicional: duas",
        "- checkboxes novas: uma",
        "- review por outro subagente: nao",
        "- confianca: alta",
        "- nao verificado: o processo vivo",
        "- gate-doubt:",
        "  - verde-de-verdade: ok",
        "  - falta-no-gate: none",
        "  - gate-melhor: invert the gate",
      ].join("\n"),
    },
  },
  {
    name: "empty-payload",
    want: 2,
    why: "no last_assistant_message at all -> NO-VERDICT, rc 2. NEVER CLEAN: a check that did not run is not a pass.",
    payload: { hook_event_name: "SubagentStop", session_id: "selftest" },
  },
  {
    name: "empty-string",
    want: 2,
    why: "a present-but-empty closing message is the same no-verdict state, not a violation and not a pass",
    payload: { hook_event_name: "SubagentStop", session_id: "selftest", last_assistant_message: "   \n  " },
  },
  {
    name: "wrong-type",
    want: 2,
    why: "last_assistant_message as an object is a payload shape this gate does not understand -> NO-VERDICT, never CLEAN and never VIOLATION",
    payload: { hook_event_name: "SubagentStop", session_id: "selftest", last_assistant_message: { text: "hi" } },
  },
  {
    name: "malformed-json",
    want: 2,
    why: "unparseable stdin degrades to an empty payload -> NO-VERDICT, not a blind pass",
    raw: "{ this is not json",
    wantVerdict: "SELF-AUDIT-NO-VERDICT",
  },
  {
    name: "crash",
    want: 2,
    why: "a fault injected INTO the decision function must surface as its own rc (2 / SELF-AUDIT-SCAN-UNREADABLE), never as rc 1",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      last_assistant_message: "## SELF-AUDIT\n",
    },
    env: { SELF_AUDIT_FAULT: "judge" },
    wantVerdict: "SELF-AUDIT-SCAN-UNREADABLE",
  },
  {
    name: "loop-guard",
    want: 0,
    why: "a violation on a continuation turn records the guard and does not block again - a block that loops is a wedge",
    payload: {
      hook_event_name: "SubagentStop",
      session_id: "selftest",
      stop_hook_active: true,
      last_assistant_message: "# receipt\n\nno self-audit here\n",
    },
    wantVerdict: null,
  },
];

// Run the real CLI as a child process, so the arms exercise the shipped path
// (argument handling, fault injection, the try/catch, the exit code) and not an
// in-process re-implementation of it.
function runArm(arm) {
  const { spawnSync } = require_spawn();
  const args = [process.argv[1]];
  const res = spawnSync(process.execPath, args, {
    input: arm.raw !== undefined ? arm.raw : JSON.stringify(arm.payload),
    encoding: "utf8",
    env: Object.assign({}, process.env, arm.env || {}),
  });
  return { rc: res.status, stdout: res.stdout || "", stderr: res.stderr || "" };
}

function require_spawn() {
  // Imported lazily so the hook path itself never pays for it.
  return { spawnSync: spawnSyncRef };
}

let spawnSyncRef = null;

async function selftest() {
  spawnSyncRef = (await import("node:child_process")).spawnSync;

  // The ledger must not touch a real install during the self-test.
  const scratch = process.env.SELF_AUDIT_SELFTEST_DIR ||
    (await import("node:os")).tmpdir() + "/mcode-self-audit-selftest";
  process.env.PLUGIN_DATA_OVERRIDE = scratch;

  const failures = [];
  let ran = 0;

  for (const arm of ARMS) {
    const got = runArm(arm);
    ran += 1;
    const okRc = got.rc === arm.want;
    let okVerdict = true;
    if (arm.wantVerdict !== undefined && arm.wantVerdict !== null) {
      // The verdict token has to be visible, not merely implied by the rc: a gate
      // that dies and a gate that refuses must be told apart by NAME too.
      const ledgerPath = scratch + "/invocations.jsonl";
      let last = "";
      try {
        last = (await import("node:fs")).readFileSync(ledgerPath, "utf8").trim().split("\n").pop();
      } catch { last = ""; }
      const parsed = last ? JSON.parse(last) : {};
      okVerdict = parsed.verdict === arm.wantVerdict;
      if (!okVerdict) {
        failures.push(arm.name + ": want verdict " + arm.wantVerdict + ", ledger says " + parsed.verdict);
      }
    }
    if (!okRc) {
      failures.push(arm.name + ": want rc " + arm.want + ", got " + got.rc +
        (got.stderr ? " stderr=" + got.stderr.trim().split("\n")[0] : ""));
    }
    process.stdout.write(
      "selftest: " + arm.name.padEnd(22) + " want rc=" + arm.want + " got rc=" + got.rc +
      (okRc && okVerdict ? "  PASS" : "  FAIL") + "\n",
    );
  }

  // The fail-open distinguisher, asserted rather than claimed: a run must leave a
  // ledger line. If this file ever stops being callable, this arm is what notices.
  let ledgerLines = 0;
  try {
    const body = (await import("node:fs")).readFileSync(scratch + "/invocations.jsonl", "utf8");
    ledgerLines = body.trim() === "" ? 0 : body.trim().split("\n").length;
  } catch { ledgerLines = 0; }
  if (ledgerLines < ARMS.length) {
    failures.push("ledger: want >=" + ARMS.length + " invocation records, got " + ledgerLines);
  }
  process.stdout.write(
    "selftest: ledger-records      want rc=0 got rc=" + (ledgerLines >= ARMS.length ? 0 : 1) +
    "  (" + ledgerLines + " records for " + ARMS.length + " arms - the fail-open distinguisher)\n",
  );
  ran += 1;

  // The ledger arm is an ASSERTION, not a payload arm: it is counted in the runner
  // total above, so it is subtracted here to keep numerator and denominator the same
  // kind of thing. Reporting "18/17 declared" would be a count that cannot be wrong,
  // which is the property this whole file exists to distrust.
  process.stdout.write(
    "selftest: arms ran " + (ran - 1) + "/" + ARMS.length + " payload arms" +
    " + 1 ledger assertion\n",
  );
  if (failures.length > 0) {
    process.stdout.write("SELFTEST FAIL\n");
    for (const f of failures) process.stdout.write("  - " + f + "\n");
    process.exit(1);
  }
  process.stdout.write(
    "SELFTEST PASS - " + ARMS.length + " payload arms + 1 ledger assertion, every expected rc " +
    "observed. It says NO to a report with " +
    "no block, to a block whose gate-doubt is prose, to a block whose sub-questions are prose, " +
    "to a reason-less exemption, to a missing field, to a heading that merely starts with the " +
    "token, and to a fault inside its own decision function - which it names as rc 2, not rc 1 - " +
    "while accepting both the Portuguese and the English field spellings, a numbered heading, " +
    "and a reasoned exemption. Every arm wrote a ledger record.\n",
  );
  process.exit(0);
}

// Fault injection. A declared, tested seam: it is how the crash arm proves that a death
// in the decision function is rc 2. It is a no-op unless the env var is set.
if (process.env.SELF_AUDIT_FAULT === "judge") {
  const real = judge;
  judge = function faultInjectedJudge(message) {
    throw new Error("SELF_AUDIT_FAULT=judge: injected fault inside the decision function");
  };
  judge.fieldLabel = fieldLabel;
  judge.__real = real;
}

//
// ---------------------------------------------------------------- entry
//

const argv = process.argv.slice(2);
for (const arg of argv) {
  if (arg === "--help" || arg === "-h") {
    process.stdout.write(USAGE + "\n");
    process.exit(0);
  }
  if (arg === "--selftest") continue;
  usageError("unknown option '" + arg + "' (see --help)");
}

if (argv.includes("--selftest")) {
  await selftest();
} else {
  try {
    await main();
  } catch (err) {
    // Last line of defence. If even the ledger throws, this must still be rc 2 and not
    // rc 1, because Node's default for an uncaught throw is exactly the code a real
    // RED uses.
    process.stderr.write("check-self-audit-block: SELF-AUDIT-SCAN-UNREADABLE: " +
      (err && err.message ? err.message : String(err)) + "\n");
    process.exit(2);
  }
}
