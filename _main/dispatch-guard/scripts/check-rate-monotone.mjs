#!/usr/bin/env node
// check-rate-monotone.mjs - Stop / SubagentStop hook for mcode-dispatch-guard.
//
// THE DEFECT, VERBATIM, FROM MY OWN TRANSCRIPT (two consecutive closing reports):
//
//     "2 REDs in 6 runs"   (ts 1791153615687)
//     "1 RED in 7 runs"    (ts 1791153949441)
//
//   Adding one GREEN run cannot reduce the number of RED runs from 2 to 1. A cumulative
//   count of bad runs is non-decreasing when the run total only grows, so under the plain
//   reading the two figures are mutually exclusive: one of them was computed from a
//   different population, and BOTH were published as measured. That is the law this
//   guards - "a DERIVED number may not be published without its POPULATION and its
//   WINDOW" (measured 2026-09-25) - and it is a shape no existing hook in this Plugin
//   looks at. check-report-binding.mjs requires POPULATION and WINDOW to be PRESENT; it
//   cannot see that two present figures disagree.
//
// WHAT IT MATCHES. Figures of the form "N <bad-noun> in M <total-noun>" inside ONE closing
// message, plus the percentage that may hang off the same figure. Three rules, all of them
// arithmetic impossibilities, none of them a judgement about wording:
//
//   A  the bad count FALLS while the run total GROWS  (2 REDs in 6 runs -> 1 RED in 7 runs)
//      -- the transcript defect, and the two-figure inconsistency the brief asks for.
//   C  a figure's own percentage disagrees with its own numerator/denominator
//      ("1 RED in 7 runs (50%)" -- the true rate is 14%)
//   D  the bad count exceeds the total it is drawn from (3 REDs in 2 runs)
//
// A FOURTH RULE WAS WRITTEN AND DELETED: "the rate RISES while the total grows and the bad
// count does not". It is unreachable, and that is worth recording rather than hiding. If a
// percentage is arithmetically consistent with its own figure then it is round(n/d), and
// round() is monotonic: with n_b <= n_a and d_b > d_a the true rate strictly FALLS, so a
// correctly-rounded pair of percentages can never show the reported rate rising. Every
// case rule B was meant to catch is therefore either rule A (n falls, d grows) or rule C
// (one of the two percentages is wrong for its own figure, which is how the rate ends up
// moving the wrong way against its own numerator). A house law says a check that cannot go
// RED is not evidence; an unreachable rule is the same defect, so it is not shipped.
//
// NARROW ON PURPOSE. Two figures are compared only when they use the SAME bad noun and the
// SAME total noun (inflections folded: "REDs"/"red", "runs"/"run"). Two different metrics -
// "0 errors in 6 runs" beside "2 REDs in 7 runs" - are never compared. A single figure never
// fires. A hook that blocks a consistent report is worse than no hook, because the fleet
// learns to route around enforcement.
//
// SCOPE LIMIT, STATED NOT HIDDEN. This hook sees ONE message. Cross-TURN regression - the
// exact shape of the defect above, where the two figures were published by two different
// closing reports - is OUT OF SCOPE HERE and this hook cannot detect it: there is no durable
// state on the path. Closing it needs a ledger in PLUGIN_DATA that appends the last published
// (bad, total, bad-noun, total-noun) per session, so the next turn can require
// bad_now >= bad_prev whenever total_now > total_prev.
//
// KNOWN FALSE POSITIVE, NAMED. A report that QUOTES this very defect to explain it contains
// both figures in one message and will be blocked once. That is the deliberate price of a
// within-message rule; the cost is one continuation and a clearer sentence.
//
// rc contract: 0 = pass silently (and always on any internal error, malformed or empty
// stdin), 1 = block with {"decision":"block","reason":"..."} on stdout. A crash must never
// become a verdict. Only numbers from the closing report are ever echoed; no message text,
// no environment, no credentials.
//
// ONE-SHOT GUARD. The contract requires one against a continuation loop
// (references/local-plugin-hooks.md:212-213). Two guards are used: the runtime's own
// `stop_hook_active` flag, and a session-keyed marker file in PLUGIN_DATA. COST, NAMED: the
// marker is session-scoped, so this rule blocks at most ONCE per session even when the
// runtime flag is missing. Fail-open everywhere: an unwritable PLUGIN_DATA never stops the
// turn from being judged.
import { existsSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { fingerprint, parsePayload, readStdin, record, resolveDataDir } from "./ledger.mjs";

// A bad-noun and a total-noun, in the shapes a closing report actually uses.
const BAD_NOUNS =
  "REDs?|fails?|failed|failing|failure|failures|errors?|broken|defects?|misses|missed";
const TOTAL_NOUNS =
  "runs?|attempts?|times?|tries|trials?|samples?|cases?|tests?|checks?|executions?|" +
  "iterations?|cycles?|passes|invocations?|calls?|turns?";

// Figure shapes, all with named groups. "in" and "out of" and "/" and the reversed
// "2/6 runs RED" and "2 of 6 runs were RED" all reach the same verdict.
const FIGURES = [
  new RegExp(
    String.raw`(?<n>\d{1,7})\s+(?<bad>${BAD_NOUNS})\s+(?:in|out\s+of|of|per)\s+(?<d>\d{1,7})\s*(?<tot>${TOTAL_NOUNS})?\b`,
    "gi",
  ),
  new RegExp(
    String.raw`(?<n>\d{1,7})\s+(?<bad>${BAD_NOUNS})\s*\/\s*(?<d>\d{1,7})\s*(?<tot>${TOTAL_NOUNS})?\b`,
    "gi",
  ),
  new RegExp(
    String.raw`(?<d>\d{1,7})\s*\/\s*(?<n>\d{1,7})\s*(?<tot>${TOTAL_NOUNS})?\s*(?:were|are|was|is|remained|stayed)?\s*(?<bad>${BAD_NOUNS})\b`,
    "gi",
  ),
  new RegExp(
    String.raw`(?<n>\d{1,7})\s+of\s+(?<d>\d{1,7})\s*(?<tot>${TOTAL_NOUNS})?\s+(?:were|are|was|is)\s+(?<bad>${BAD_NOUNS})\b`,
    "gi",
  ),
  // Label-first, which is how a per-line figure is usually written: "REDs: 2 of 6 runs",
  // "red: 2/6 runs". Demands the `:`/`=` label AND an of-slash separator between the two
  // numbers, so a bare number after a noun is never read as a denominator.
  new RegExp(
    String.raw`(?<bad>${BAD_NOUNS})\s*[:=]\s*(?<n>\d{1,7})\s*(?:in|out\s+of|of|per|\/)\s*(?<d>\d{1,7})\s*(?<tot>${TOTAL_NOUNS})?\b`,
    "gi",
  ),
];

// A percentage belongs to the figure only when nothing but punctuation separates it.
const PCT_TAIL = /^\s*[(\[\-–—*]?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*%/;
const PCT_LOOKAHEAD = 24;
// Truncation of a true ratio loses at most 1 point (4/6 = 66.67 -> 66), so anything
// beyond that is a different number, not a rounding.
const PCT_EPS = 1.05;

const ONE_SHOT_PREFIX = "rate-monotone.";

/** Fold plurals only. Two nouns match when they are the same word, not merely alike. */
function singular(word) {
  if (!word) return "";
  const s = String(word).toLowerCase();
  if (s.length > 4 && s.endsWith("ies")) return `${s.slice(0, -3)}y`;
  if (s.length > 4 && s.endsWith("ses")) return s.slice(0, -2);
  if (s.length > 3 && s.endsWith("s") && !s.endsWith("ss")) return s.slice(0, -1);
  return s;
}

/** Every "N bad in M total" figure in the message, in document order. */
function collectFigures(message) {
  const found = [];
  for (const rx of FIGURES) {
    rx.lastIndex = 0;
    let m;
    while ((m = rx.exec(message)) !== null) {
      const g = m.groups || {};
      const n = Number(g.n);
      const d = Number(g.d);
      if (!Number.isFinite(n) || !Number.isFinite(d)) continue;
      const end = m.index + m[0].length;
      const pm = PCT_TAIL.exec(message.slice(end, end + PCT_LOOKAHEAD));
      const pct = pm ? Number(pm[1].replace(",", ".")) : null;
      found.push({
        pos: m.index,
        len: m[0].length,
        n,
        d,
        bad: g.bad || "",
        tot: g.tot || "",
        pct: Number.isFinite(pct) ? pct : null,
        key: `${singular(g.bad)}|${singular(g.tot)}`,
      });
      if (m[0].length === 0) rx.lastIndex += 1; // no zero-width loop
    }
  }
  found.sort((a, b) => a.pos - b.pos || b.len - a.len);
  // Two patterns can describe the same span. Keep the first (longest at that position).
  const out = [];
  for (const f of found) {
    const prev = out[out.length - 1];
    if (prev && f.pos < prev.pos + prev.len) continue;
    out.push(f);
  }
  return out;
}

/** "2 REDs in 6 runs" - numbers only, never the surrounding message text. */
function render(f) {
  return `${f.n} ${f.bad} in ${f.d}${f.tot ? ` ${f.tot}` : ""}`;
}

/**
 * The only cross-figure question: can both figures describe the same population?
 * A shrinking denominator is NOT an inconsistency - "in the last 5 runs: 1 RED in 5 runs"
 * beside "over 20 runs: 4 REDs in 20 runs" is a narrowed window stated honestly.
 */
function compare(group) {
  for (let i = 0; i < group.length; i += 1) {
    for (let j = i + 1; j < group.length; j += 1) {
      const a = group[i];
      const b = group[j];
      // A: cumulative bad count falls while the run total grows.
      if (b.d > a.d && b.n < a.n) return { rule: "A", a, b };
    }
  }
  return null;
}

/**
 * The predicate, exported so the self-test can name the exact rule that fired.
 * Returns { verdict: "PASS" | "BLOCK" | "NOVALUE", rule?, a?, b? }.
 */
export function judge(message) {
  if (typeof message !== "string" || message.trim() === "") return { verdict: "NOVALUE" };
  const figures = collectFigures(message);
  if (figures.length === 0) return { verdict: "PASS", why: "no-figure" };

  // D: a bad count cannot exceed the population it is drawn from. Checked first so the
  // ratio rules never divide by a zero total.
  for (const f of figures) {
    if (f.n > f.d) return { verdict: "BLOCK", rule: "D", a: f, b: null };
  }
  // C: the figure disagrees with itself.
  for (const f of figures) {
    if (f.pct === null) continue;
    const expected = (100 * f.n) / f.d;
    if (Math.abs(f.pct - expected) > PCT_EPS) {
      return { verdict: "BLOCK", rule: "C", a: f, b: null, expected: Math.round(expected) };
    }
  }
  // A and B, only inside one noun group.
  const groups = new Map();
  for (const f of figures) {
    if (!groups.has(f.key)) groups.set(f.key, []);
    groups.get(f.key).push(f);
  }
  for (const group of groups.values()) {
    const hit = compare(group);
    if (hit) return { verdict: "BLOCK", rule: hit.rule, a: hit.a, b: hit.b };
  }
  return { verdict: "PASS", why: "consistent", figures: figures.length };
}

function reasonFor(v) {
  const a = render(v.a);
  const b = v.b ? render(v.b) : null;
  const tail =
    " State the POPULATION and the WINDOW of each figure, or drop the one you cannot " +
    "measure (owner law 2026-09-25). One continuation only, then the turn ends either way.";
  if (v.rule === "A") {
    return (
      `Two figures in this report cannot both describe the same runs: ${a}, then ${b}. ` +
      "A cumulative count of bad runs cannot fall while the run total grows, so the two " +
      "numbers came from different populations and at most one of them is the rate." + tail
    );
  }
  if (v.rule === "C") {
    return (
      `A figure disagrees with its own percentage: ${a} is ${v.expected}%, not ${v.a.pct}%. ` +
      "Recompute it or delete the percentage." + tail
    );
  }
  return `${a} reports more bad runs than runs. That count cannot be right; recompute it.` + tail;
}

/** Session-keyed one-shot marker. A write failure never silences the guard. */
function oneShotAlreadyFired(session) {
  const dir = resolveDataDir();
  if (!dir) return false;
  const key = fingerprint(String(session)) || "nosession";
  const marker = join(dir, `${ONE_SHOT_PREFIX}${key}.once`);
  try {
    if (existsSync(marker)) return true;
    writeFileSync(marker, `${new Date().toISOString()}\n`, "utf8");
    return false;
  } catch {
    return false; // fail open on the GUARD, not on the verdict
  }
}

function block(reason) {
  process.stdout.write(JSON.stringify({ decision: "block", reason }) + "\n");
  process.exit(1);
}

async function main() {
  const raw = await readStdin();
  const payload = parsePayload(raw);
  const event = payload.hook_event_name || "unknown";
  const session = payload.session_id || "unknown";
  const message = payload.last_assistant_message;

  let v;
  try {
    v = judge(message);
  } catch {
    // An internal error is not a verdict. Fail open.
    record({ event, verdict: "ERROR", action: "none", why: "judge_threw", session });
    process.exit(0);
    return;
  }

  if (v.verdict !== "BLOCK") {
    record({ event, verdict: v.verdict, action: "none", why: v.why || "no-figure", session });
    process.exit(0);
    return;
  }

  if (payload.stop_hook_active === true) {
    record({ event, verdict: "BLOCK", action: "none", why: "stop_hook_active_guard", session });
    process.exit(0);
    return;
  }

  if (oneShotAlreadyFired(session)) {
    record({ event, verdict: "BLOCK", action: "none", why: "one_shot_guard", session, rule: v.rule });
    process.exit(0);
    return;
  }

  record({ event, verdict: "BLOCK", action: "block", session, rule: v.rule, msg_len: typeof message === "string" ? message.length : 0 });
  block(reasonFor(v));
}

// Only run when executed. The self-test imports `judge` from this file, and an unguarded
// main() would read the self-test's own stdin.
const isEntry = (() => {
  if (!process.argv[1]) return false;
  const me = fileURLToPath(import.meta.url).toLowerCase();
  const them = process.argv[1].toLowerCase();
  return me === them || me.endsWith(them) || them.endsWith(me);
})();

if (isEntry) main().catch(() => process.exit(0));