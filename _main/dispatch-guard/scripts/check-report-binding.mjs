// check-report-binding.mjs - Stop / SubagentStop hook.
//
// THE GAP THIS CLOSES, MEASURED. probes/stop-hook-adversarial.py, POPULATION 3 controls +
// 5 adversaries, WINDOW 2026-10-06 02:18:02, direct invocation, harness_ok=true:
//     C1 no-spec-line                 REFUSED by check-spec-line.mjs
//     C2 debt-as-free-text            REFUSED by check-spec-line.mjs
//     C3 nothing-left-named           REFUSED by check-spec-line + check-open-items
//     A1 success claim, no POPULATION GOT THROUGH
//     A2 GREEN, no WINDOW             GOT THROUGH
//     A4 no P0-in-three               GOT THROUGH
//     A5 narrow green called healthy  GOT THROUGH
//     A7 SELF-AUDIT absent            GOT THROUGH
// The three existing Stop hooks police the SHAPE of a report. None of them police whether a
// success claim carries the evidence the owner asked for on 2026-09-25 and 2026-10-05.
//
// THE LAWS THIS ENFORCES, both already written and both unenforced on this path:
//   1. "a DERIVED number may not be published without its POPULATION and its WINDOW"
//      (measured 2026-09-25). A claim with no population is not a narrower claim; it is a
//      different claim whose meaning is a free parameter.
//   2. "todo turno tem secção P0 em três: o que vou fazer AGORA, o que JÁ FIZ, o que NÃO FIZ
//      (e porquê)" (owner directive 2026-10-05). Three green results can coexist while the P0
//      dies waiting, which is exactly how 15 lanes stayed invisible.
//
// WHY A Stop HOOK AND NOT A LAW. Owner doctrine: reinforcement must be structural. A law in
// AGENTS.md is read once and obeyed variably; a Stop hook runs on EVERY turn, at the moment the
// report is complete, and cannot be forgotten because I never choose to run it.
//
// THE TRIGGER IS DELIBERATELY NARROW: it fires only when the closing message claims success.
// A report that claims nothing succeeded is not accused of anything. A hook that always fires
// is a hook that gets disabled.
//
// rc contract: 0 = pass silently, 1 = block with a reason on stdout, 2 = crash (never block).
import { readFileSync } from 'node:fs';

// A success verdict. Narrow on purpose: these are the phrasings I actually use.
const SUCCESS = [
  /\bGREEN\b/i,
  /\bVERDE\b/i,
  /\bworks\b/i,
  /\bfunciona\b/i,
  /\ball (?:checks|arms|gates|tests) pass\b/i,
  /\bnow parses\b/i,
  /\bis healthy\b/i,
  /\bsaud[aá]vel\b/i,
  /\b\d+\/\d+ (?:arms|checks|gates) pass\b/i,
  /\bimplemented\b.*\bcorrect\b/i,
];

const HAS_POPULATION = /\bPOPULATION\b|\bpopula(?:tion|tion)\s*[=:]/i;
const HAS_WINDOW = /\bWINDOW\b|\bjanela\b|\bwindow\s*[=:]|\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/i;
const HAS_P0 = /\bP0\b/i;
const HAS_SELF_AUDIT = /##\s*SELF-AUDIT/i;

function readPayload() {
  let raw = '';
  try {
    raw = readFileSync(0, 'utf8');
  } catch {
    return {};
  }
  try {
    return JSON.parse(raw) ?? {};
  } catch {
    return {};
  }
}

function block(reason) {
  process.stdout.write(JSON.stringify({ decision: 'block', reason }));
  process.exit(1);
}

const payload = readPayload();
const message = String(payload.last_assistant_message ?? '');
if (!message.trim()) process.exit(0); // nothing was said; nothing to bind

const claimsSuccess = SUCCESS.some((rx) => rx.test(message));

// SELF-AUDIT is unconditional: the law says every receipt/report ends with it, and the
// existing self-audit hook only covers SubagentStop, so the root agent was never bound by it.
if (!HAS_SELF_AUDIT.test(message)) {
  block(
    'This report has no `## SELF-AUDIT` section. The law is that every receipt and report ' +
      'closes with it: protocols missing, extra verification, new checkboxes (named and ' +
      'mechanical), review by another subagent, confidence plus what moves it, what was NOT ' +
      'verified, and gate-doubt. Note the existing self-audit lint is wired to SubagentStop ' +
      'only, so as the root agent you are currently unbound by it. Append the section and ' +
      're-answer. One continuation only, then the turn ends either way.',
  );
}

// The evidence laws bind only a report that CLAIMS success.
if (claimsSuccess) {
  const missing = [];
  if (!HAS_POPULATION.test(message)) missing.push('POPULATION (how many things were measured)');
  if (!HAS_WINDOW.test(message)) missing.push('WINDOW (when the measurement happened)');
  if (!HAS_P0.test(message)) missing.push('the P0-in-three section (what now / what already / what not, and why)');

  if (missing.length > 0) {
    block(
      `This report claims success but is missing: ${missing.join('; ')}.\n` +
        'A success claim with no population and no window is not a narrower claim, it is a ' +
        'different claim whose meaning is a free parameter. Either state the POPULATION and ' +
        'the WINDOW you actually measured, or downgrade the claim to what you really have. ' +
        'Owner directives 2026-09-25 and 2026-10-05. One continuation only, then the turn ' +
        'ends either way.',
    );
  }
}

process.exit(0);