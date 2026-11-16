'use strict';

/**
 * AUDIT RECEIPT — "is the transcript ('History · Redux') reachable at all?"
 *
 * `_main/live-vs-history-source-oracle.js` asserts the panel REFUSES the live
 * path (GREEN), and it takes the acceptance predicate's INPUT from a meta object
 * it builds itself (`replay()` at :111-117 assembles {text, reason, route,
 * routeSource, start} and never copies `producer`; the "canonical path is OPEN"
 * arm then INJECTS `producer:'redux'` at :219). So the oracle proves the
 * predicate, not the wiring: nothing in the running app is exercised for the
 * `producer` field.
 *
 * This receipt asks the missing question against the REAL modules:
 *
 *   1. run the REAL engine (`caption-formulation.js`) over a stream shaped like
 *      the worker's own wire (partials with `final:false`, then the ONE line the
 *      second pass closed with `final:true`), and print the meta it hands
 *      `onCommit` — the exact object `panel.js recordHistory` receives;
 *   2. hand THAT meta to the REAL `history-source.js` predicate;
 *   3. let the REAL store (`history-store.js`) write whatever passes, into a
 *      throwaway root, and count the lines on disk.
 *
 * Exit 0 always: this is a measurement, not a gate. Nothing outside a temp dir
 * is written, no process is started, no window is opened.
 *
 *     node _main/_audit-history-dead.js
 *
 * `--neg-arm` is the control of the control (added 2026-11-16): it runs the SAME
 * engine output through the RETIRED predicate (`route==='final' &&
 * isCanonicalLine`) and requires that predicate to refuse what the shipped one
 * accepts. Without it, the 2026-11-05 drift was invisible: the probe restated an
 * old rule for four days, published a defect that no longer existed and could
 * not fail. rc=1 on catch, the house convention for a `:expectred` step.
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const REPO = path.normalize(path.join(__dirname, '..'));
const engineMod = require(path.join(REPO, 'app', 'panel', 'caption-formulation.js'));
const source = require(path.join(REPO, 'app', 'panel', 'history-source.js'));

// The worker's own wire, as `worker/sotto_worker.py::_event()` writes it: the
// live channel is `final:false`, and the SECOND PASS publishes the closed line
// with `final:true` (sotto_worker.py:2402 `ev["final"] = True`).
const STREAM = [
  { text: 'o rato roeu', start: 0.0, end: 1.2, final: false },
  { text: 'o rato roeu a rolha', start: 0.0, end: 2.4, final: false },
  { text: 'O rato roeu a rolha da garrafa do rei da Russia.', start: 0.0, end: 4.0, final: true },
  { text: 'a prova dos nove', start: 5.0, end: 6.4, final: false },
];

const commits = [];
const engine = engineMod.createEngine({
  onCommit: (text, reason, meta) => commits.push({ text, reason, meta }),
  onProvisional: () => {},
});

for (const e of STREAM) {
  engine.ingest(e.text, { start: e.start, end: e.end, final: e.final });
}
engine.flush('stream-end');   // the panel's `wireStatus`/shutdown flush

console.log('meta hand-delivered to panel.js recordHistory (one per commit):');
for (const c of commits) {
  console.log(`  text=${JSON.stringify(c.text)} reason=${JSON.stringify(c.reason)}`
    + ` meta=${JSON.stringify(c.meta)}`);
}

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sotto-audit-history-'));
process.env.SOTTO_HISTORY_ROOT = root;
delete require.cache[require.resolve(path.join(REPO, 'app', 'panel', 'history-store.js'))];
const store = require(path.join(REPO, 'app', 'panel', 'history-store.js'));

// THE RULE IS THE SHIPPED ONE, never a copy (measured 2026-11-16). This line
// restated `route === 'final' && isCanonicalLine(meta)` -- the rule the product
// STOPPED using on 2026-11-05, when `historyDecision` made the route the only
// gate and the producer mere provenance. The copy stayed behind, so the probe
// reported "the panel refuses EVERY line" about a door that had already been
// opened, and the step that carries it could never fail: it printed a dramatic
// verdict and returned 0 either way.
const NEG_ARM = process.argv.includes('--neg-arm');
const shippedAccepts = (meta) => source.transcriptRoute(meta) !== null;
//: the RETIRED predicate, kept ONLY so the control has something to prove.
const retiredAccepts = (meta) =>
  !!meta && meta.route === 'final' && source.isCanonicalLine(meta);
const panelAccepts = NEG_ARM ? retiredAccepts : shippedAccepts;

let accepted = 0;
let acceptedShipped = 0;
for (const c of commits) {
  if (shippedAccepts(c.meta)) acceptedShipped += 1;
  if (!panelAccepts(c.meta)) {
    const refusal = source.historyRefusal(c.meta) || { reason: 'unknown', route: null, producer: null };
    console.log(`REFUSED  text=${JSON.stringify(c.text)}`
      + ` why=${JSON.stringify(refusal.reason)}`
      + ` route=${JSON.stringify(refusal.route)}`
      + ` producer=${JSON.stringify(refusal.producer)}`);
    continue;
  }
  accepted += 1;
  store.append(c.text, { source: 'redux', ...c.meta });
}

const lines = [];
for (const day of fs.existsSync(root) ? fs.readdirSync(root) : []) {
  for (const f of fs.readdirSync(path.join(root, day))) {
    lines.push(...fs.readFileSync(path.join(root, day, f), 'utf8').trim().split('\n'));
  }
}
fs.rmSync(root, { recursive: true, force: true });

console.log('');
console.log(`commits handed to the panel : ${commits.length}`);
console.log(`accepted by the choke point : ${accepted}`);
console.log(`lines written to disk       : ${lines.length}`);
console.log(`CANONICAL_PRODUCER          : ${source.CANONICAL_PRODUCER}`);
console.log(`producer seen on any commit : ${JSON.stringify(
  commits.map((c) => source.producerOf(c.meta)))}`);
console.log(`commits accepted by SHIPPED : ${acceptedShipped}`);
console.log('');
if (NEG_ARM) {
  // The control: the retired predicate must REFUSE what the shipped one
  // accepts. Two ways to fail, both named: the retired rule also accepts (then
  // the two predicates are identical and this probe proves nothing), or the
  // shipped rule accepts nothing (nothing to prove the control against).
  const caught = acceptedShipped > 0 && accepted === 0;
  console.log(caught
    ? 'NEG-ARM: PASS -- the retired predicate refuses the line the shipped'
      + ` rule accepts (retired=${accepted} shipped=${acceptedShipped})`
    : 'NEG-ARM: FAIL -- the two predicates do not differ on this stream'
      + ` (retired=${accepted} shipped=${acceptedShipped})`);
  process.exitCode = caught ? 1 : 0;   // house convention: 1 WHEN CAUGHT
} else {
  console.log(accepted === 0
    ? 'VERDICT: the panel refuses EVERY line this engine can produce - the feed'
      + ' cannot fill, and the top half of the panel is unreachable.'
    : 'VERDICT: the transcript received lines.');
  // THE VERDICT IS THE EXIT CODE (2026-11-16). Both branches used to return 0,
  // so the step `audit-history-dead` was declared `:record` and could never
  // fail: a dead transcript and a live one published the same green.
  process.exitCode = accepted === 0 ? 1 : 0;
}
