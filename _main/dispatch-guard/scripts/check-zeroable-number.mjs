// check-zeroable-number.mjs - Stop / SubagentStop hook.
//
// THE LAW. "every claim of 'works' must carry a number that could have been zero and
// wasn't." A success claim whose evidence is a bare adjective ("the audio device is
// detected", "the extractor works", "all arms pass", "the plugin is recognised") has
// nothing behind it that could have come out as 0. The observed shape is exactly that:
// green, passed, healthy, recognised, with no quantity anywhere.
//
// WHY THIS EXISTS. The verdict "it works" is the one verdict in this repo that can be
// produced with the instrument switched off. A file-count, a byte-count, a peak level, a
// duration or a `9/9` is falsifiable; "the plugin is recognised" is not, because nothing
// in it can disagree with the report. Owner doctrine: reinforcement must be structural,
// so this lives in a Stop hook that runs on every closing message and that I cannot
// forget because I never choose to run it.
//
// WHAT THIS DOES NOT DO, so it is not a second copy of check-report-binding.mjs.
// That hook polices whether a success claim carries POPULATION, WINDOW and the P0
// section. A report can satisfy all three and still contain no measurement at all:
// `POPULATION unknown, WINDOW 2026-10-06` is a well-formed binding with nothing bound.
// This hook asks the disjoint question - is there a MEASURED QUANTITY whose zero is a
// possible outcome - and its complaint is never "missing POPULATION/WINDOW/P0".
//
// HOW A NUMBER IS CLASSIFIED, because "contains a digit" is not a test.
// Decorative numbers are removed BEFORE the measurement search runs:
//   - dates and clocks   `2026-10-06`, `02:15:36`
//   - versions           `v1.2.3`, `3.1.4`  (but NOT `1.6 MB`, which needs a unit)
//   - file references    `hooks.json:42`, `check-spec-line.mjs`
//   - session ids        `mvs_a3cbbed1dbc94f32`
// What survives is zeroable only with EVIDENCE OF MEASUREMENT, in one of four shapes:
//   1. SUFFIX UNIT       `1,204 bytes`, `120 s`, `1.6 MB`, `100%`, `-3.2 dBFS`, `3 files`,
//                        `0 errors`, `9 arms` - a number followed by a unit or count noun.
//   2. MEASURE CUE      `peak 0.98`, `duration 12.4`, `count: 386` - a measuring word
//                        (peak, level, max, mean, size, length, duration, latency, score,
//                        count, total, population, ...) sitting directly before the number.
//   3. LABELLED COUNT    `errors: 0`, `arms = 9` - a count noun with an explicit `:` or `=`.
//   4. EQUAL FRACTION    `9/9`, `5/5` - or any fraction with a count noun on its line.
// A bare integer is never zeroable on its own, which is what keeps the year in "in 2026
// the extractor works" from passing the gate. `questions` is deliberately NOT a count
// noun: the agent's own constitution boilerplate opens with "the 5 questions", so counting
// it would let every report that quotes policy satisfy this gate without measuring.
//
// THE TRIGGER IS DELIBERATELY NARROW. It fires only when the closing message CLAIMS
// success AND carries no zeroable number. A report that claims nothing worked is not
// accused of anything. A report that claims success with `peak 0.98` is not accused. A
// hook that always fires is a hook that gets disabled, and a disabled hook teaches the
// fleet to route around the whole plugin.
//
// ONE-SHOT GUARD. `stop_hook_active` is honoured before any block
// (references/local-plugin-hooks.md:212-213), so a continuation cannot loop.
//
// SECRETS. The block reason is a fixed string. No byte of `last_assistant_message` is
// ever copied to stdout, stderr or the reason, so a credential inside a report cannot
// escape through this hook.
//
// rc contract: 0 = silent pass (also every internal error, malformed input, and empty
// stdin - a crash must never become a verdict), 1 = block, with the reason on stdout.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const MAX_MESSAGE_CHARS = 120_000; // bounded work inside a 5 s handler timeout
const NEGATION_WINDOW = 40; // characters of context inspected before a success cue
const NEGATION_TAIL = 16; // characters of that context that must stay negation-flavoured

// A success verdict. Deliberately wider than check-report-binding's list: the observed
// failures in this defect are `detected` and `recognised`, which that list does not
// contain, and this hook must fire on them or it is decorative itself.
const SUCCESS_CUES = [
  /\bwork(?:s|ed|ing)?\b/i,
  /\bfunctional\b/i,
  /\boperational\b/i,
  /\bin place\b/i,
  /\bgreen\b/i,
  /\bverde\b/i,
  /\bpass(?:es|ed|ing)?\b/i,
  /\bdetected\b/i,
  /\bdetect(?:s|ing)\b/i,
  /\brecogni[sz]ed\b/i,
  /\brecogni[sz]able\b/i,
  /\breachable\b/i,
  /\bregistered\b/i,
  /\bloaded\b/i,
  /\bavailable\b/i,
  /\bhealthy\b/i,
  /\bsaud[aá]vel\b/i,
  /\bverif(?:y|ied|ies|ied|ying)\b/i,
  /\bconfirmed\b/i,
  /\bparses\b/i,
  /\bfixed\b/i,
  /\bresolved\b/i,
  /\bimplemented\b/i,
  /\bcomplete[ds]?\b/i,
  /\bshipped\b/i,
  /\bland(?:s|ed|ing)\b/i,
];

// "nothing is green", "is not detected", "unverified", "did not pass" are NOT claims of
// success. Checked against the words immediately preceding the cue.
const NEGATED_BEFORE =
  /(?:\b(?:not|no|none|nothing|never|neither|nor|zero|un\w{1,3}|n[’']t|isn\w*|wasn\w*|aren\w*|weren\w*|doesn\w*|didn\w*|can\w*|won\w*|couldn\w*|shouldn\w*|hasn\w*|haven\w*|fails?|failed|broken|unable)\b)[^\n]{0,16}$/i;

const NUM = String.raw`\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?`;
const INT = String.raw`\d{1,3}(?:,\d{3})*`;

// Units and count nouns usable as a SUFFIX (`1,204 bytes`, `3 files`, `0 errors`).
const UNITS = [
  String.raw`dBFS|dBA|dBm|dB`,
  String.raw`KiB|MiB|GiB|kB|KB|MB|GB|TB|bytes?`,
  String.raw`percent|pct|%|kHz|MHz|GHz|Hz`,
  String.raw`milliseconds?|seconds?|minutes?|hours?|ms|secs?|mins?|hrs?|s`,
];

// Count nouns. `questions` is intentionally absent - see header note on boilerplate.
const NOUNS = [
  String.raw`files?|lines?|chars?|characters?|rows?|columns?|entries|blocks?|items?|nodes?`,
  String.raw`tests?|checks?|arms?|gates?|lanes?|hooks?|handlers?|diagnostics?`,
  String.raw`errors?|failures?|warnings?|violations?|findings?|defects?|regressions?`,
  String.raw`records?|results?|attempts?|cases?|samples?|readings?|matches?|items?`,
  String.raw`sessions?|agents?|messages?|tokens?|commands?|scripts?|modules?|repos?|commits?`,
  String.raw`devices?|peaks?|endpoints?|routes?|artifacts?|subscribers?|listeners?`,
  String.raw`population|window|count|total`,
];

// Measuring words. Allowed to sit directly before a number with no connector, because
// `peak 0.98` and `duration 12.4` ARE the measurement and need no `:`.
const MEASURE_CUES = [
  String.raw`peaks?|peaked|level|max(?:imum)?|min(?:imum)?|mean|median|average|avg`,
  String.raw`duration|elapsed|latency|throughput|bandwidth|size|length|width|height|depth`,
  String.raw`score|count|total|population|rate|ratio|weight|cost|bytes?|bits?`,
];

// NOTE. NUM and INT contain a top-level `|`, so they MUST be interpolated inside a
// non-capturing group. Interpolating them bare splits the whole pattern into
// "cue + number" OR "any bare number", which silently accepts every integer in the
// report. That bug shipped once in this file and the self-test caught it; the `(?:)`
// below is load-bearing, not decoration.
const SUFFIX_MEASURE = new RegExp(
  String.raw`\b(?:${NUM})[ \t]*(?:-[ \t]*)?(?:${UNITS.join('|')}|${NOUNS.join('|')})\b`,
  'i',
);

const PREFIX_MEASURE = new RegExp(
  String.raw`\b(?:${MEASURE_CUES.join('|')})\b[ \t]*(?:of|at|is|are|was|were|reached|hit)?[ \t]*[:=]?[ \t]*-?(?:${NUM})\b`,
  'i',
);

const PREFIX_LABELLED = new RegExp(
  String.raw`\b(?:${NOUNS.join('|')})\b[^\S\n]{0,4}[:=][ \t]*(?:${NUM})\b`,
  'i',
);

const FRACTION = new RegExp(String.raw`\b(?:${INT})[ \t]*/[ \t]*(?:${INT})\b`);

// Stripped before any measurement search: none of these can be the evidence.
const DECORATIVE = [
  /\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?Z?\b/g,
  /\b\d{4}\/\d{1,2}\/\d{1,2}\b/g,
  /\b\d{1,2}:\d{2}(?::\d{2})?\b/g,
  /\bv\d+(?:\.\d+)+\b/gi,
  /\b\d+\.\d+\.\d+(?:\.\d+)*\b/g,
  /[A-Za-z0-9_.\-\\/]*\.(?:mjs|cjs|js|json|md|ts|tsx|py|sh|bash|txt|log|ya?ml|toml|ini)\b(?::\d+)?/g,
  /\b(?:mvs|mcp|mcp_srv|gh|abc|sk|ses|task)_[0-9a-f]{4,}[0-9a-z]*/gi,
];

function stripDecorative(text) {
  let out = text;
  for (const rx of DECORATIVE) out = out.replace(rx, ' ');
  return out;
}

function claimsSuccess(message) {
  for (const rx of SUCCESS_CUES) {
    const m = rx.exec(message);
    if (!m) continue;
    const before = message.slice(Math.max(0, m.index - NEGATION_WINDOW), m.index);
    if (NEGATED_BEFORE.test(before)) continue;
    return true;
  }
  return false;
}

/**
 * The measurement predicate.
 * @returns {"suffix-unit"|"measure-cue"|"labelled-count"|"equal-fraction"|null}
 */
export function measureKind(message) {
  const text = stripDecorative(String(message));

  if (SUFFIX_MEASURE.test(text)) return 'suffix-unit';
  if (PREFIX_MEASURE.test(text)) return 'measure-cue';
  if (PREFIX_LABELLED.test(text)) return 'labelled-count';

  // A fraction is only evidence when it is complete (`9/9`) or carries a count noun on
  // its line. `16/9` or a stray date fragment is not a pass rate.
  const fm = FRACTION.exec(text);
  if (fm) {
    const [n, d] = fm[0].split('/').map((s) => Number(s.trim()));
    if (n === d) return 'equal-fraction';
    const line = text.slice(text.lastIndexOf('\n', fm.index) + 1, text.indexOf('\n', fm.index) < 0 ? text.length : text.indexOf('\n', fm.index));
    if (new RegExp(String.raw`\b(?:${NOUNS.join('|')})\b`, 'i').test(line)) return 'count-fraction';
  }
  return null;
}

function readPayload() {
  let raw = '';
  try {
    raw = readFileSync(0, 'utf8');
  } catch {
    return {};
  }
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

const REASON =
  'This report claims something works, but carries no number that could have been ' +
  'zero and was not - no count, no byte count, no duration, no percentage, no peak ' +
  'level, no `9/9`. A success claim with nothing falsifiable in it cannot be ' +
  'distinguished from a guess. Either state the measured quantity you actually ' +
  'observed (for example `peak -3.2 dBFS`, `1,204 bytes`, `0 errors`, `9/9 arms`), ' +
  'or downgrade the claim to what you really have. This is not the POPULATION/WINDOW ' +
  'rule - this hook is asking whether a measurement exists at all. One continuation ' +
  'only, then the turn ends either way.';

function block() {
  process.stdout.write(JSON.stringify({ decision: 'block', reason: REASON }));
  process.exit(1);
}

function main() {
  const payload = readPayload();
  const message = String(payload.last_assistant_message ?? '');
  if (!message.trim()) process.exit(0); // nothing was said; nothing to accuse

  const tail = message.length > MAX_MESSAGE_CHARS ? message.slice(-MAX_MESSAGE_CHARS) : message;

  // ONE-SHOT GUARD. Never block twice into the same stop.
  if (payload.stop_hook_active === true) process.exit(0);

  if (!claimsSuccess(tail)) process.exit(0); // no claim of success, no accusation
  if (measureKind(tail) !== null) process.exit(0); // a measurement exists; this hook is done

  block();
}

// Entry guard. The self-test drives the REAL process, but the rule itself is exported so
// a rule change can be probed directly; without this guard, importing the module runs
// main(), which reads stdin and exits the prober before it can print anything.
const IS_ENTRY = (() => {
  if (!process.argv[1]) return true; // always run the hook unless we are provably imported
  try {
    return resolve(process.argv[1]) === fileURLToPath(import.meta.url);
  } catch {
    return true; // undecidable: run the hook rather than silently do nothing
  }
})();

if (IS_ENTRY) {
  try {
    main();
  } catch {
    // An internal error is NOT a verdict. Silent pass, never a block.
    process.exit(0);
  }
}