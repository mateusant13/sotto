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

// The panel's choke point, verbatim from panel.js:335-351.
const panelAccepts = (meta) =>
  meta && meta.route === 'final' && source.isCanonicalLine(meta);

let accepted = 0;
for (const c of commits) {
  if (!panelAccepts(c.meta)) {
    console.log(`REFUSED  text=${JSON.stringify(c.text)}`
      + ` route=${JSON.stringify(c.meta.route)}`
      + ` producer=${JSON.stringify(source.producerOf(c.meta))}`);
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
console.log('');
console.log(accepted === 0
  ? 'VERDICT: the panel refuses EVERY line this engine can produce — the feed'
    + ' cannot fill, and the top half of the panel is unreachable by design'
    + ' until a batch engine stamps producer:"redux".'
  : 'VERDICT: the transcript received lines.');
