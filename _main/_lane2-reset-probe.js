'use strict';

/**
 * _lane2-reset-probe.js — "Clear" must clear the ENGINE, not just the DOM.
 *
 * THE DEFECT THIS EXISTS FOR (audit task 3, panel.js Clear handler):
 *
 *   Clear emptied `#caption-list` and left `caption-formulation.js` holding the
 *   line it had on screen. The engine's re-cover watermark
 *   (`emittedStart`/`emittedWords`/`emittedEnd`) deliberately SURVIVES `commit`
 *   — that is the cure for the duplicated-transcript defect — so the next
 *   fragment of the same worker line still looked like a continuation and the
 *   panel re-rendered the words the owner had just cleared, or swallowed them
 *   as a duplicate. Either way the Clear control lied.
 *
 * WHAT THIS CHECKS. Against the REAL engine (`app/panel/caption-formulation.js`),
 * the file `panel.js` loads:
 *
 *   ARM 1  a fresh engine holds nothing
 *   ARM 2  after one ingest the engine holds the line (`state()` non-empty)
 *   ARM 3  `reset()` empties every field `state()` reports (and `visible()`)
 *   ARM 4  THE CONTROL, both colours in ONE run: re-ingesting the SAME fragment
 *          WITHOUT a reset commits NOTHING (the engine still believes it already
 *          wrote that line — the bug), and WITH a reset commits it again (the
 *          cure). A no-op `reset()` makes this arm RED.
 *   ARM 5  nothing of the DROPPED buffer's route survives: the first line after
 *          the reset is routed by its own reason (`hold-timeout` ->
 *          `provisional-draft`/`panel-deadline`), not by the `final:true` the
 *          cleared buffer carried.
 *   ARM 6  the rest of the engine's API is untouched and `reset` exists
 *   ARM 6c the module's TOP-LEVEL SURFACE is unchanged - a change detector over
 *          the real exports (the list is the surface as of 2026-10-19; the
 *          2026-10-17 revision added `PUNCT_PERIOD_GAP_S`, `PUNCT_COMMA_GAP_S`
 *          and `formulateTokens` to it)
 *   ARM 6d THE NEGATIVE ARM of 6c, EXECUTED: a COPY of the module with ONE
 *          extra top-level export must be FLAGGED by the same comparison. An
 *          arm that only ever compares two lists and says "ok" when one IS the
 *          other proves nothing about the other direction.
 *
 *   node _main/_lane2-reset-probe.js
 */

const fs = require('node:fs');
const path = require('node:path');

// WHICH MODULE IS UNDER TEST. The default is the shipped one. `--engine <path>`
// points the probe at another copy — it exists so the negative arm (ARM 6c) can
// be demonstrated END TO END: point it at a copy with one extra export and the
// arm goes RED, in this file's own code, not in a re-implementation of it.
const ENGINE = (() => {
  const i = process.argv.indexOf('--engine');
  if (i >= 0 && i + 1 < process.argv.length) return path.resolve(process.argv[i + 1]);
  return path.join(__dirname, '..', 'app', 'panel', 'caption-formulation.js');
})();
const F = require(ENGINE);

const arms = [];
function arm(name, real, want) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  arms.push({ name, ok, real, want });
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
  console.log(`       real = ${JSON.stringify(real)}`);
  console.log(`       want = ${JSON.stringify(want)}`);
  return ok;
}

function newEngine(commits) {
  return F.createEngine({
    onCommit: (text, reason, meta) => commits.push({ text, reason, meta }),
    onProvisional: () => {},
  });
}

console.log(`engine under test: ${ENGINE}`);
console.log(`reset() is a function: ${typeof F.createEngine({ onCommit: () => {}, onProvisional: () => {} }).reset}`);

const FRAGMENT = 'O rádio';
const META = { start: 1, end: 2 };

// ── ARM 1 ────────────────────────────────────────────────────────────────────
const commitsA = [];
const a = newEngine(commitsA);
arm('ARM 1 a fresh engine holds nothing', a.state(), {
  committed: [],
  provisional: [],
  lastAudioEnd: null,
});

// ── ARM 2 ────────────────────────────────────────────────────────────────────
a.ingest(FRAGMENT, META);
const held = a.state();
console.log(`  held after ingest: ${JSON.stringify(held)}  visible="${a.visible()}"`);
arm(
  'ARM 2 the engine holds the line it was fed (committed + provisional > 0)',
  held.committed.length + held.provisional.length > 0,
  true,
);
arm('ARM 2b and the line it holds is the fragment that arrived', a.visible(), FRAGMENT);

// ── ARM 3 ────────────────────────────────────────────────────────────────────
a.reset();
console.log(`  state after reset(): ${JSON.stringify(a.state())}  visible="${a.visible()}"`);
arm('ARM 3 reset() empties the committed words', a.state().committed, []);
arm('ARM 3b reset() empties the provisional tail', a.state().provisional, []);
arm('ARM 3c reset() drops the audio watermark', a.state().lastAudioEnd, null);
arm('ARM 3d reset() empties the rendered line', a.visible(), '');

// ── ARM 4 — the CONTROL, both colours in one run ─────────────────────────────
// (a) the bug, reproduced: NO reset, same fragment again -> the engine stays
//     silent because it believes that line is already written.
const commitsB = [];
const b = newEngine(commitsB);
b.ingest(FRAGMENT, META);
b.expireHold();
const firstLine = commitsB.length;
b.ingest(FRAGMENT, META);
b.expireHold();
const withoutReset = commitsB.length - firstLine;

// (c) the cure: reset, then the SAME fragment -> a new line, committed again.
const commitsC = [];
const c = newEngine(commitsC);
c.ingest(FRAGMENT, META);
c.expireHold();
const lineBefore = commitsC.length;
c.reset();
c.ingest(FRAGMENT, META);
c.expireHold();
const withReset = commitsC.length - lineBefore;

console.log(`  without reset(): ${withoutReset} new commit(s); with reset(): ${withReset} new commit(s)`);
console.log(`  commits with reset(): ${JSON.stringify(commitsC.map((x) => x.text))}`);
arm('ARM 4  CONTROL: without reset() the same fragment is swallowed (the Clear bug)', withoutReset, 0);
arm('ARM 4b CURE: after reset() the same fragment starts a NEW line', withReset, 1);
arm(
  'ARM 4c and the line is the fragment, formulated once',
  commitsC[commitsC.length - 1] && commitsC[commitsC.length - 1].text,
  'O rádio.',
);

// ── ARM 5 — no stale route survives the reset ────────────────────────────────
const commitsD = [];
const d = newEngine(commitsD);
d.ingest('Fim da linha', { start: 5, end: 6, final: true });
d.expireHold();
const closedRoute = commitsD[0] && commitsD[0].meta.route;
d.reset();
d.ingest('Linha limpa', { start: 0.5, end: 1 });
d.expireHold();
const afterReset = commitsD[1] && commitsD[1].meta;
console.log(`  route before reset (worker-closed buffer): ${JSON.stringify(closedRoute)}`);
console.log(`  meta of the first line AFTER reset:      ${JSON.stringify(afterReset)}`);
arm('ARM 5 the cleared buffer was a closed (final) line', closedRoute, 'final');
arm('ARM 5b the first line after reset() is routed by ITS OWN reason, not the dead buffer', afterReset && afterReset.route, 'provisional-draft');
arm('ARM 5c and it declares the panel deadline as its source', afterReset && afterReset.routeSource, 'panel-deadline');

// ── ARM 6 — the API surface is otherwise identical ───────────────────────────
arm('ARM 6 createEngine still returns ingest/flush/expireHold/visible/state/reset', [
  typeof a.ingest, typeof a.flush, typeof a.expireHold, typeof a.visible,
  typeof a.state, typeof a.reset,
], ['function', 'function', 'function', 'function', 'function', 'function']);
arm('ARM 6b reset() is idempotent and returns nothing', a.reset() === undefined && JSON.stringify(a.state()) === JSON.stringify({ committed: [], provisional: [], lastAudioEnd: null }), true);

// ARM 6c is a CHANGE DETECTOR over the module's top-level surface. The
// EXPECTED list below is the REAL surface, measured 2026-10-19 against
// `app/panel/caption-formulation.js` at commit 494a927 (2026-10-17), which is
// the revision that added `PUNCT_PERIOD_GAP_S`, `PUNCT_COMMA_GAP_S` and
// `formulateTokens` to it. A NEW export is a red arm, on purpose: `panel.js`
// and every oracle read this module's surface, and a silent addition is
// exactly what nobody notices.
//
// The comparison lives in ONE function (`surfaceDiff`) because ARM 6d runs the
// SAME code against a mutated copy.
const EXPECTED_SURFACE = [
  'COMMIT_MAX_HOLD_MS',
  'PUNCT_COMMA_GAP_S',
  'PUNCT_PERIOD_GAP_S',
  'READY_SECONDS_MEASURED',
  'SENTENCE_GAP_S',
  'SENTENCE_MAX_CHARS',
  'agreedPrefixLength',
  'createEngine',
  'describeReadiness',
  'formulate',
  'formulateTokens',
  'healSeams',
  'words',
];

function surfaceDiff(real, expected) {
  const added = real.filter((k) => !expected.includes(k));
  const removed = expected.filter((k) => !real.includes(k));
  return { added, removed, ok: added.length === 0 && removed.length === 0 };
}

const liveSurface = Object.keys(F).sort();
const liveDiff = surfaceDiff(liveSurface, EXPECTED_SURFACE);
console.log(`  live surface : ${JSON.stringify(liveSurface)}`);
console.log(`  expected     : ${JSON.stringify(EXPECTED_SURFACE)}`);
console.log(`  diff         : added=${JSON.stringify(liveDiff.added)} removed=${JSON.stringify(liveDiff.removed)}`);
arm('ARM 6c the module surface is unchanged (no new top-level export)',
  { added: liveDiff.added, removed: liveDiff.removed },
  { added: [], removed: [] });

// ── ARM 6d — THE NEGATIVE ARM of 6c: the surface check CAN fail ─────────────
// A COPY of the module with ONE extra top-level export. The SAME `surfaceDiff`
// must FLAG it; if the mutated copy slips through, this arm goes RED and the
// check above is decoration. The copy is deleted before the probe exits.
//
// WHY A COPY AND NOT A STUB: the arm has to run the REAL comparison against a
// REAL module object. A hand-made object with one extra key would only prove
// that `surfaceDiff` compares objects, which is not what is being claimed.
const COPY = path.join(__dirname, '_lane2-formulation-copy.js');
let mutatedSurface = [];
let mutatedError = null;
try {
  const src = fs.readFileSync(ENGINE, 'utf8');
  fs.writeFileSync(COPY, `${src}\nmodule.exports.__lane2_probe_extra__ = 1;\n`, 'utf8');
  mutatedSurface = Object.keys(require(COPY)).sort();
} catch (err) {
  mutatedError = String(err && err.stack ? err.stack : err);
} finally {
  try {
    if (fs.existsSync(COPY)) fs.unlinkSync(COPY);
  } catch (err) {
    console.log(`  [WARN] the mutated copy could not be deleted: ${err}`);
  }
}
if (mutatedError) console.log(`  [FAIL] the mutated copy could not be built:\n${mutatedError}`);
const mutatedDiff = surfaceDiff(mutatedSurface, EXPECTED_SURFACE);
console.log(`  mutated copy : ${JSON.stringify(mutatedSurface)}`);
console.log(`  diff         : added=${JSON.stringify(mutatedDiff.added)} removed=${JSON.stringify(mutatedDiff.removed)}`);
arm('ARM 6d the surface check FLAGS a new top-level export (the mutated copy)',
  mutatedError || mutatedDiff.added,
  ['__lane2_probe_extra__']);
arm('ARM 6d and the mutated copy differs from the real one by THAT export only',
  { added: mutatedDiff.added, removed: mutatedDiff.removed },
  { added: ['__lane2_probe_extra__'], removed: [] });

const failed = arms.filter((x) => !x.ok);
console.log(`\nRESULT: ${failed.length ? `RED — ${failed.length} violation(s)` : 'GREEN — reset() clears the engine, and the cleared line cannot come back'}`);
for (const f of failed) console.log(`  FAIL ${f.name}: real=${JSON.stringify(f.real)} want=${JSON.stringify(f.want)}`);
process.exit(failed.length ? 1 : 0);
