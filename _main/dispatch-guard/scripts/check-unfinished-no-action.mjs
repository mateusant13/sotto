// check-unfinished-no-action.mjs - Stop / SubagentStop hook.
//
// THE LAW. Owner directive, 2026-10-04, in the owner's own words, and the part that is the
// guard's subject:
//   "todo report termina com `## WHAT'S NEXT / WHAT I DID NOT DO`, so quando falta algo real.
//    Cada item com verbo + alvo; a próxima acção é executá-lo, não adiá-lo."
// Read together with the 2026-10-03 directive: "se a secção existir, manda-me executar o que
// disse que falta. ... A ausência da secção passa a ser afirmação, e afirmação precisa de
// evidência."
//
// WHY THIS EXISTS AND WHY IT IS NOT A TUNING OF check-open-items-execute.mjs.
// That sibling fires on "the section exists and holds at least one AGENT item" - i.e. on any
// item the agent did not push onto the owner, INCLUDING items that already carry a verb and a
// target ("Land the CRT gate on the healer"). This hook fires on the strict complement: an
// item under that section that admits work is not done AND carries no actionable continuation.
// The difference is the whole point - the sibling says "go do the list", this one says "this
// specific line is an admission with no action attached, which is the defect the owner named".
//
// THE TRIGGER IS NARROW, AND DELIBERATELY SO. Three gates, each of which has been measured to
// be the common reason a would-be guard fires on everything:
//   1. The non-completion section must exist AND enumerate at least one item. An empty section
//      is not an admission, and prose admissions outside the section are NOT this hook's
//      subject (see "KNOWN FALSE NEGATIVE" below).
//   2. Per item: not a past-tense "here is what I did do" line, not one of the skip words
//      (none/nada/N-A), and not an OWNER item the agent is structurally unable to execute.
//   3. Per remaining item: it must carry NEITHER a commitment (verb + target) NOR a deferral
//      that names its blocker. One of those two is the owner's acceptable form.
//
// WHY STRICT. A Stop hook that fires on most reports gets switched off, and a switched-off hook
// protects nothing while still costing the owner a look at every block. Narrow also buys a
// sharper reason: the offending line is quoted back verbatim.
//
// LOOP SAFETY. Two one-shot guards: the runtime's `stop_hook_active` flag, and a session-keyed
// marker file in PLUGIN_DATA. The marker namespace is `unfinished-no-action.continued.*` and is
// its OWN: sharing a file with a sibling hook means whichever runs second reads the first one's
// marker and silently passes, and neither ever fires twice.
//
// KNOWN FALSE NEGATIVE, DECLARED: an admission written in prose outside the section ("the retro
// file was never written") does not fire. Prose is everywhere; requiring the structural section
// is what keeps the firing rate low enough to survive contact with a real week of reports.
//
// rc contract: 0 = pass silently, 1 = block with a reason on stdout. This hook has NO crash rc:
// every internal error, malformed stdin, and missing message exits 0, because a guard that dies
// on the turn it was supposed to protect is worse than a guard that misses one line.

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

// --- the section ---------------------------------------------------------------------------------
// A section OPENER is a markdown heading, or a short label line that ends in a colon (the
// house format `**What I did NOT do:** the retro file`). Both are matched by their label, so
// `## WHAT'S NEXT / WHAT I DID NOT DO` is found by its first half.
const HEADING = /^#{1,6}\s/;
const NON_DONE_LABEL = new RegExp(
  [
    "\\bwhat (?:i )?(?:did not|didn'?t|have not|haven'?t|could not|couldn'?t) (?:do|land|verify|run|test|check|measure|fix|cover|build|write|create|implement|publish|commit|exercise)\\b",
    "\\bwhat (?:i )?(?:was|were|is|are) not (?:done|verified|landed|tested|measured|checked|fixed|implemented|completed|executed|run|closed|written|created)\\b",
    "\\bwhat'?s (?:next|left|outstanding|not done|not verified|open)\\b",
    "\\bnext steps?\\b",
    "\\bopen items?\\b",
    "\\boutstanding (?:work|items?)\\b",
    "\\bwork not (?:done|landed|finished|verified)\\b",
    "\\bnot done yet\\b",
    "\\bo que n[ãa]o (?:fiz|foi (?:feito|verificado|rodado|escrito|executado)|verifiquei|landei|executei|testei)\\b",
    "\\bn[ãa]o (?:fiz|foi (?:feito|verificado|rodado|escrito|executado)|verifiquei|landei|executei|testei)\\b",
    "\\bpendente(?:ncias|s)?\\b",
    "\\bfaltam?\\b",
    "\\bem aberto\\b",
  ].join("|"),
  "i",
);

// An item line, and nothing else. Prose is not an item.
const ITEM_LINE = /^(?:[-*+]|\d+[.)])\s+\S/;

// --- the three acceptable item shapes ------------------------------------------------------------

// One source of truth for the verb list. It is used ONLY for the commitment-clause path
// ("next: land X"), where a verb plus a commitment marker is unambiguous. It is deliberately
// NOT used to recognise an imperative: enumerating verbs loses to every list, and a census
// over 2181 real receipts measured exactly that - "Arm the OMP reaper", "Free disk on the
// three volumes", "Re-read the Defender exclusions" are all directives, none is in any list
// worth maintaining, and all three were blocked by the whitelist version of this hook.
const VERB = [
  "do", "redo", "re-do", "make", "build", "land", "write", "file", "add", "create",
  "implement", "fix", "repair", "patch", "wire", "run", "re-run", "rerun", "execute",
  "measure", "verify", "re-verify", "check", "confirm", "test", "cover", "close", "finish",
  "complete", "open", "draft", "send", "publish", "commit", "push", "deploy", "dispatch",
  "spawn", "retry", "schedule", "escalate", "report", "document", "note", "record",
  "investigate", "diagnose", "review", "audit", "update", "refresh", "rewrite", "replace",
  "remove", "delete", "revert", "backout", "ask", "decide", "choose", "pick", "rule",
  "authorize", "approve", "grant", "unblock", "integrate", "reenable", "re-enable",
  "fazer", "landar", "escrever", "adicionar", "criar", "implementar", "corrigir", "consertar",
  "rodar", "executar", "medir", "verificar", "testar", "fechar", "publicar", "enviar",
  "documentar", "registrar", "investigar", "perguntar", "decidir", "escolher", "retomar",
  "reativar", "conectar",
];
const VERB_ALT = VERB.join("|");
// Contains an action verb as a word, not as part of a longer token.
const HAS_VERB = new RegExp(`(?:^|[\\s(\\[/>:—-])(?:${VERB_ALT})\\b`, "i");

// THE IMPERATIVE TEST, and it is not a verb list. An item is a directive - the owner's
// "verbo + alvo" - when its first word is NOT a closed-class word. Articles, determiners,
// pronouns, prepositions, conjunctions, adverbs and copulas cannot open a command; a content
// word can. That test needs no verb inventory, so "Arm the reaper", "Free disk" and
// "Re-read the exclusions" are directives for free, and it is falsifiable in the right
// direction: a bare noun phrase opens with an article ("the retro file ...") and stays INERT.
const NOT_DIRECTIVE_FIRST = new Set([
  // articles, determiners, demonstratives, quantifiers
  "the", "a", "an", "this", "that", "these", "those", "my", "our", "your", "its", "their",
  "his", "her", "no", "any", "some", "each", "every", "all", "both", "none", "many", "most",
  "o", "os", "as", "um", "uma", "uns", "umas", "este", "esta", "isto", "isso", "aquele",
  "aquela", "meu", "minha", "nosso", "nossa", "seu", "sua", "dele", "dela", "nenhum",
  "nenhuma", "todo", "toda", "outro", "outra",
  // pronouns
  "i", "we", "you", "they", "he", "she", "it", "me", "us", "them", "him", "who", "what",
  "which", "whose", "there", "here", "eu", "tu", "ele", "ela", "nos", "vos", "voces",
  // prepositions and conjunctions
  "in", "on", "at", "to", "for", "with", "without", "from", "by", "of", "about", "after",
  "before", "until", "since", "during", "into", "onto", "over", "under", "per", "via",
  "and", "but", "or", "so", "because", "if", "when", "while", "as", "than", "then",
  "em", "para", "por", "com", "sem", "de", "da", "do", "das", "dos", "e", "mas", "ou",
  "porque", "se", "quando", "enquanto", "apos", "desde",
  // adverbs and negations
  "not", "never", "still", "just", "only", "even", "also", "already", "always", "nao",
  "nunca", "jamais", "ainda", "so", "apenas", "somente", "tambem", "entao",
  // copulas and existential verbs: the grammar of an admission, never of a command
  "was", "were", "is", "are", "am", "be", "been", "has", "have", "had", "will", "would",
  "can", "could", "may", "might", "must", "should", "there", "exists", "remain", "remains",
  "remained", "left", "lacks", "lack", "missing", "foi", "era", "sao", "foram", "ficou",
  "existe", "existem", "falta", "faltou", "restam", "faltam",
]);

// An item that OPENS with an admission. Checked before the imperative test, because "Did not
// raise the budget, lower it, or convert it to rc=2" begins with a finite verb and would
// otherwise read as a command to do all three.
const ADMISSION_FIRST = new Set([
  "did", "didnt", "didn't", "do", "dont", "don't", "does", "doesnt", "doesn't", "was",
  "wasnt", "wasn't", "were", "werent", "weren't", "is", "isnt", "isn't", "are", "arent",
  "aren't", "has", "hasnt", "hasn't", "have", "havent", "haven't", "had", "never", "nothing",
  "no", "nada", "nenhum", "nao", "não", "faltou", "faltam", "fez", "fiz", "rodei", "escrevi",
  "verifiquei", "executei", "landei", "corrigi",
]);

// A commitment marker is what makes a verb a promise. Without one, a verb in the item is just
// part of the thing that was not done.
const COMMITMENT = new RegExp(
  [
    "\\bnext\\b",
    "\\bthen\\b",
    "\\bi(?:'ll| will| am going to|'m going to| intend to| plan to| intend| plan)\\b",
    "\\bvou\\b",
    "\\bvai\\b",
    "\\bfollow[- ]?up\\b",
    "\\baction\\s*:",
    "\\btodo\\s*:",
    "\\bimmediately\\b",
    "\\bdepois\\b",
    "\\bamanh[ãa]\\b",
    "\\bna pr[óo]xima\\b",
    "\\bfollowing\\b",
  ].join("|"),
  "i",
);

// A deferral that NAMES its blocker. A bare "later", "blocked", "pending" is not a deferral
// with a blocker - it is the defect wearing a deferral's clothes.
const DEFERRAL_WITH_BLOCKER = new RegExp(
  [
    "\\bwaiting (?:on|for)\\s+[a-z0-9][\\w\\-\\u2019']*(?:\\s+[a-z0-9][\\w\\-\\u2019']*){1,5}\\b",
    "\\bblocked (?:by|on|:)\\s+\\S[\\s\\S]{2,}",
    "\\bdeferred (?:until|to|pending)\\s+\\S[\\s\\S]{2,}",
    "\\bparked (?:until|on|pending|:)\\s+\\S[\\s\\S]{2,}",
    "\\bpending (?:on|until|for)\\s+\\S[\\s\\S]{2,}",
    "\\bdepends on\\s+\\S[\\s\\S]{2,}",
    "\\bonce\\s+\\S[\\s\\S]{2,}",
    "\\buntil\\s+(?:the\\s+)?[a-z0-9][\\w\\-\\u2019']*(?:\\s+[a-z0-9][\\w\\-\\u2019']*){0,4}\\s+(?:lands?|arrives?|completes?|passes?|resolves?|is (?:green|done|merged|approved|fixed))\\b",
    "\\bafter\\s+\\S[\\s\\S]{0,60}?\\b(?:lands?|merges?|passes?|completes?|is (?:done|green|merged))\\b",
    "\\bbloquead[oa]\\s+(?:por|:)\\s+\\S[\\s\\S]{2,}",
    "\\baguard(?:a|ando|o)\\s+\\S[\\s\\S]{2,}",
  ].join("|"),
  "i",
);

// An OWNER item: the agent cannot execute it, so a hook that fires on it issues an instruction
// the agent is structurally unable to obey. Deliberately overlapping with check-open-items-
// execute.mjs OWNER_ITEM; duplicated here on purpose so this file has no dependency on a
// sibling that another lane owns.
const OWNER_ITEM = new RegExp(
  [
    "\\bpendente[- ]?dono\\b",
    "\\bowner[- ]?decides?\\b",
    "\\bonly the owner\\b",
    "\\bso (?:only )?(?:you|the owner) can\\b",
    "\\bowner (?:must|has to|needs to) (?:decide|choose|pick|rule|answer|approve)\\b",
    "\\bwaiting (?:on|for) (?:you|the owner|your)\\b",
    "\\byour call\\b",
    "\\bneeds? (?:an? )?(?:owner )?decision\\b",
    "\\bautoriz\\w*\\b",
    "\\bdecis[aã]o do dono\\b",
    "\\bpergunta ao dono\\b",
    "\\bdecide the owner\\b",
  ].join("|"),
  "i",
);

// A line of work already DONE, wrongly parked under the non-completion heading. Flagging it
// would be a false positive with no owner-facing value.
const PAST_DONE = new RegExp(
  "^(?:\\*\\*|__)?\\s*(?:fixed|added|created|wrote|written|landed|implemented|ran|verified|measured|tested|checked|closed|committed|deployed|published|sent|updated|removed|deleted|patched|reverted|done|passed|green|finished|corrected)\\b",
  "i",
);
// "nothing left" is a claim, not an admission.
const NO_ITEMS = /^(?:\*\*|__)?\s*(?:n\/a|na|none|nada|nothing|nenhum|no open items?|no pending|sem pend(?:ê|e)ncias|-{1,2}|\u2014)\s*\.?\s*$/i;

// A PROHIBITION: a constraint the agent is forbidden to act on, not work it put down. Measured
// need: the 2026-10-03 day report lists "Do not commit anything in I:\!manager" and "Do not
// kill, start, or restart MiniMax Code" under its non-completion heading; both are the
// opposite of a debt, and the hook that fires on a prohibition teaches the reader to ignore it.
const PROHIBITION = /^(?:\*\*|__)?\s*(?:do not|do n[oó]t|don'?t|never|n[ãa]o|nunca|avoid)\b/i;

// A RUBRIC FIELD, not an admission: a short line that is only a field name ("gate-doubt:",
// "verde-de-verdade:"). These come from the SELF-AUDIT template, where item 6 names its
// sub-fields on their own lines. A field name carries nothing to execute.
const RUBRIC_FIELD = /[:\uFF1A]$/;

// --- parsing -------------------------------------------------------------------------------------

/**
 * Returns { label, items } for the first non-completion section that enumerates at least one
 * item, else null. An empty section is not an admission.
 */
export function extractSection(message) {
  const lines = String(message).split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    const raw = lines[i];
    const trimmed = raw.trim();
    if (!trimmed) continue;
    const isHeading = HEADING.test(trimmed);
    // A bare label line ("**What I did NOT do:** ...") opens the section too; the text after
    // the colon, if any, is the first item. It must NOT be an item line: SELF-AUDIT item 6
    // ("6. What was NOT verified: the hook on a live event.") matches this label and, when
    // accepted as an opener, converted a self-audit line into a section on almost every report
    // in this workspace. Measured: that one condition made both realistic GREEN arms block.
    const isLabel =
      !isHeading &&
      !ITEM_LINE.test(trimmed) &&
      trimmed.length <= 160 &&
      NON_DONE_LABEL.test(trimmed) &&
      /:\s*\S/.test(trimmed);
    if (!isHeading && !isLabel) continue;
    if (!NON_DONE_LABEL.test(trimmed)) continue;

    const items = [];
    const tail = cleanItem(trimmed.split(":").slice(1).join(":"));
    if (isLabel && tail) items.push(tail);

    for (let j = i + 1; j < lines.length; j += 1) {
      const t = lines[j].trim();
      if (/^#{1,6}\s/.test(t)) break; // next heading
      if (ITEM_LINE.test(t)) items.push(cleanItem(t.replace(/^([-*+]|\d+[.)])\s+/, "")));
    }
    if (items.length > 0) return { label: trimmed, items };
  }
  return null;
}

/**
 * Strips the markdown noise an item arrives with, so the classification reads the sentence and
 * not the formatting. Measured need: items arrived as "**Nenhum recibo foi escrito do zero.** ..."
 * and "` nothing compares `survival-plane.json` ...", which broke both the first-token test
 * and the reason text.
 */
function cleanItem(raw) {
  return String(raw).replace(/^[*_`~\s]+/, "").replace(/[*_`~\s]+$/, "").trim();
}

/**
 * The imperative test: an item opens a command when its first word is a CONTENT word. Returns
 * false for a closed-class opener ("the retro file ..."), for an admission opener ("Did not
 * raise ...") and for a one-word item, which cannot carry "verbo + alvo" at all.
 */
function isDirective(t) {
  const tokens = t.replace(/^[*_`~\s]+/, "").split(/\s+/).filter(Boolean);
  if (tokens.length < 2) return false;
  const first = tokens[0].toLowerCase().replace(/[^\p{L}\p{N}-]/gu, "");
  if (!first) return false;
  if (ADMISSION_FIRST.has(first)) return false;
  if (NOT_DIRECTIVE_FIRST.has(first)) return false;
  return true;
}

/**
 * COMPLIANT = the item is one of the two forms the owner accepts, or is not an admission at
 * all. INERT = it admits unfinished work and carries no verb + target and no named blocker.
 */
export function itemVerdict(item) {
  const t = cleanItem(item);
  if (!t) return "COMPLIANT";
  if (NO_ITEMS.test(t)) return "COMPLIANT"; // "nothing left" is a claim
  if (PAST_DONE.test(t)) return "COMPLIANT"; // already done, misfiled under the heading
  if (RUBRIC_FIELD.test(t) && t.split(/\s+/).length <= 4) return "COMPLIANT"; // a field name
  if (PROHIBITION.test(t)) return "COMPLIANT"; // "do not X" is a constraint, not a debt
  if (OWNER_ITEM.test(t)) return "COMPLIANT"; // the agent cannot execute it
  if (DEFERRAL_WITH_BLOCKER.test(t)) return "COMPLIANT"; // explicit deferral, blocker named
  if (COMMITMENT.test(t) && HAS_VERB.test(t)) return "COMPLIANT"; // "next: land X"
  if (isDirective(t)) return "COMPLIANT"; // imperative: the item IS the verb + target
  return "INERT"; // an admission with nothing attached to it
}

/** NOVALUE | NOSECTION | COMPLIANT | VIOLATION */
export function judge(message) {
  if (typeof message !== "string" || !message.trim()) return "NOVALUE";
  const section = extractSection(message);
  if (!section) return "NOSECTION";
  const inert = section.items.filter((it) => itemVerdict(it) === "INERT");
  return inert.length > 0 ? "VIOLATION" : "COMPLIANT";
}

export function reason(inertItems) {
  const shown = inertItems
    .slice(0, 8)
    .map((it, i) => `${i + 1}. ${it.length > 140 ? it.slice(0, 140) + "..." : it}`);
  const more = inertItems.length > shown.length ? `\n(+${inertItems.length - shown.length} more)` : "";
  return (
    "You ended this turn admitting work you did not do, and the admission carries no action. " +
    "These lines are yours, copied back verbatim:\n\n" +
    shown.join("\n") +
    more +
    "\n\nEvery item under a non-completion heading must carry a verb + a target (Land the CRT " +
    "gate on the healer) or an explicit deferral that names its blocker (blocked: waiting on " +
    "the owner). Do the work now, in this turn, before writing anything else - or say which " +
    "one you are handing to the owner and why. Naming a debt is not discharging it. Owner " +
    "directive of 2026-10-04. One continuation only, then the turn ends either way."
  );
}

// --- process boundary ----------------------------------------------------------------------------

function readPayload() {
  let raw = "";
  try {
    raw = readFileSync(0, "utf8");
  } catch {
    return {};
  }
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {}; // malformed stdin is not a verdict
  }
}

function markerPath(session) {
  const dir = process.env.PLUGIN_DATA;
  if (!dir) return null; // PLUGIN_ROOT is immutable; never write there
  const safe = String(session).replace(/[^A-Za-z0-9._-]/g, "_");
  return join(dir, `unfinished-no-action.continued.${safe}`);
}

function alreadyContinued(session) {
  try {
    const p = markerPath(session);
    if (!p || !existsSync(p)) return false;
    return readFileSync(p, "utf8").trim() === "1";
  } catch {
    return false; // an unreadable marker must not silence a real violation
  }
}

function markContinued(session) {
  try {
    const p = markerPath(session);
    if (p) writeFileSync(p, "1", { flag: "wx", encoding: "utf8" }); // EEXIST is the desired state
  } catch {
    /* a marker we cannot write must not break the turn */
  }
}

function block(text) {
  process.stdout.write(JSON.stringify({ decision: "block", reason: text }));
  process.exit(1);
}

function main() {
  const payload = readPayload();
  const message = payload.last_assistant_message;
  const verdict = judge(message);
  if (verdict !== "VIOLATION") process.exit(0);

  if (payload.stop_hook_active === true) process.exit(0); // runtime one-shot guard
  if (alreadyContinued(payload.session_id)) process.exit(0); // marker one-shot guard
  markContinued(payload.session_id);

  const inert = extractSection(message).items.filter((it) => itemVerdict(it) === "INERT");
  block(reason(inert));
}

try {
  main();
} catch {
  process.exit(0); // fail open: never crash into a verdict
}
process.on("uncaughtException", () => process.exit(0));