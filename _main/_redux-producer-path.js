'use strict';

/**
 * Sotto — DOES A WORKER-STAMPED `producer:'redux'` REACH THE TRANSCRIPT?
 *
 * THE QUESTION. `app/electron/history-source.js:51,61-63` accepts a line into the
 * canonical transcript only when `meta.producer === 'redux'` (fail-closed: an
 * absent or unknown producer is refused, never assumed). The batch engine
 * (`worker/redux_batch.py`) now stamps that field, so the question that decides
 * whether "History · Redux" is decorative or real is: does the field SURVIVE from
 * the worker's JSONL to the choke point? A grep cannot answer it, because the
 * path runs through an engine that builds its OWN meta object.
 *
 * A SOURCE READ CANNOT ANSWER IT — and this instrument's own history is the proof.
 * Its FIRST version measured the answer and it was NO: `caption-formulation.js`
 * `commit()` called `onCommit(line, reason, { route, start, routeSource })`, a new
 * three-key object, so the worker's `producer` was DROPPED before `recordHistory`
 * ever saw it — the batch engine could stamp all day and the feed would stay
 * empty. That was reported and the lane owning `app/electron/` fixed it at
 * 2026-10-07 04:45:51 (`bufferProducer` / `committedProducer()`, forwarded as
 * `producer: tag`). THIS FILE IS NOW THE STANDING ARM OVER THE OPEN PATH, and its
 * thesis at the time of writing is the opposite of its first run's.
 *
 * ARMS, both colours on ONE engine, differing ONLY in the stamp:
 *   ARM A   the guard itself: `{producer:'redux',route:'final'}` accepted,
 *           `{route:'final'}` refused.
 *   ARM B   a REDUX line — the worker's meta as the WebView2 shell builds it
 *           (`sotto_webview.py WorkerBridge._consume`: every key of the JSONL line
 *           except `type`/`text`) → the engine's commit meta must still CARRY
 *           `producer:'redux'`, and the transcript must take the line.
 *   ARM C   the CONTROL, and the load-bearing half: the SAME engine, the same
 *           stream, the same route — a LIVE nvidia line, which declares
 *           `final:true` and NO producer. The transcript must take ZERO lines.
 *           Without this arm, ARM B only shows the engine accepts things; with it,
 *           ARM B shows that the STAMP is what decides — which is the owner's law
 *           verbatim: *"o historico nao e' pra ser NUNCA o historico do live
 *           nvidia. e' pra ser do parakeet redux"*.
 *
 *   node _main/_redux-producer-path.js
 *   node _main/_redux-producer-path.js --json
 *
 * Exit 0 when the REDUX shape opens the feed AND the LIVE shape cannot; 1 when the
 * machine disagrees (including the case that the drop came BACK — that is a
 * regression and must never pass silently); 2 on a setup error.
 */

const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..');
// THE ENGINE MOVED WHILE THIS LANE WAS RUNNING. It lived in `app/electron/` when
// this instrument was written; another lane restructured the tree and the live
// copies are now `app/panel/`. A hard-coded path would have gone RED for the
// wrong reason ("no such file") — so BOTH are tried, the one actually used is
// PRINTED, and a missing engine is still a setup error.
const ENGINE_CANDIDATES = [
  path.join(ROOT, 'app', 'panel', 'caption-formulation.js'),
  path.join(ROOT, 'app', 'electron', 'caption-formulation.js'),
  path.join(ROOT, 'app', '_legacy-electron', 'caption-formulation.js'),
];
const SOURCE_CANDIDATES = [
  path.join(ROOT, 'app', 'panel', 'history-source.js'),
  path.join(ROOT, 'app', 'electron', 'history-source.js'),
  path.join(ROOT, 'app', '_legacy-electron', 'history-source.js'),
];

function firstExisting(candidates, what) {
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  fail(`no ${what} found. Tried:\n  ${candidates.join('\n  ')}`);
}

/**
 * Load one of the panel's files the way BOTH of its consumers do.
 *
 * WHY NOT `require`. The files moved from `app/electron/` into `app/panel/`
 * while this lane was running, and `app/package.json` declares
 * `"type": "module"` — so Node treats every `.js` under `app/` as an ES module,
 * and a CommonJS `require()` of a file whose body assigns `module.exports`
 * returns an EMPTY namespace. MEASURED: `require()` gave `keys: []` and
 * `typeof createEngine: undefined`, which this instrument reported as a setup
 * error rather than as a verdict — correctly, but uselessly.
 *
 * These files are deliberately DUAL: each ends with a CommonJS `module.exports`
 * AND a `window.X = …`, precisely so the panel can load them as a `<script>` and
 * an oracle can `require` them. The right harness therefore evaluates the SOURCE
 * with BOTH globals present, which is what a browser tab does — and it keeps
 * working whether or not the file sits under a `type: module` boundary.
 */
function loadDualExport(file, globalName) {
  const vm = require('vm');
  const src = fs.readFileSync(file, 'utf8');
  const mod = { exports: {} };
  const sandbox = {
    module: mod,
    exports: mod.exports,
    window: {},
    console,
    require,
    __filename: file,
    __dirname: path.dirname(file),
  };
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox, { filename: file });
  const fromModule = mod.exports && Object.keys(mod.exports).length
    ? mod.exports : null;
  const fromWindow = sandbox.window && sandbox.window[globalName];
  const exported = fromModule || fromWindow;
  if (!exported) {
    fail(`${path.relative(ROOT, file)} exported nothing: neither `
      + `module.exports nor window.${globalName} was set.`);
  }
  return exported;
}

const ENGINE = firstExisting(ENGINE_CANDIDATES, 'caption-formulation.js');
const SOURCE = firstExisting(SOURCE_CANDIDATES, 'history-source.js');
console.log(`ENGINE  ${path.relative(ROOT, ENGINE)}`);
console.log(`GUARD   ${path.relative(ROOT, SOURCE)}`);

function fail(msg) {
  console.log(`SETUP ERROR: ${msg}`);
  process.exit(2);
}

const SottoHistorySource = loadDualExport(SOURCE, 'SottoHistorySource');
const formulation = loadDualExport(ENGINE, 'SottoFormulation');
if (!formulation || typeof formulation.createEngine !== 'function') {
  fail(`${path.relative(ROOT, ENGINE)} did not export a createEngine.`);
}

const problems = [];
const say = (s) => console.log(s);

// One stream, narrated as the same line GROWING, so the engine commits once at
// the terminal punctuation. `final:true` on the fragment that closes it is the
// worker's own route vote — the value both engines emit.
const STREAM = [
  { text: 'O rádio anunciou que a ponte', meta: { start: 0.0, end: 2.5 } },
  { text: 'O rádio anunciou que a ponte sobre o rio', meta: { start: 0.0, end: 5.0 } },
  { text: 'O rádio anunciou que a ponte sobre o rio vai ser interditada.',
    meta: { start: 0.0, end: 7.92, final: true } },
];

// The meta the WebView2 shell builds for a caption line — every key of the JSONL
// object except `type` and `text` (`WorkerBridge._consume`, sotto_webview.py).
// REDUX: `worker/sotto_worker.py` `_run_runner` stamps exactly this shape.
const REDUX_META = {
  producer: 'redux',
  start: 0.0,
  end: 7.92,
  final: true,
  model: 'parakeet-redux-ternary',
  route: 'redux-batch',
};
// LIVE: what the nvidia streaming engine emits — a route vote and NO producer.
const LIVE_META = {
  start: 0.0,
  end: 7.92,
  final: true,
  model: 'nemotron-3.5-asr-streaming-0.6b-int8',
};

/** Drive the REAL engine with one stream and read the meta its commits carry. */
function drive(workerMeta) {
  const commits = [];
  const engine = formulation.createEngine({
    // Part of the engine's contract (the live box paints the partial).
    onProvisional: () => {},
    onCommit: (text, reason, meta) => {
      commits.push({
        text,
        reason,
        meta,
        keys: Object.keys(meta).sort(),
        accepted: SottoHistorySource.isCanonicalLine(meta),
      });
    },
  });
  for (const ev of STREAM) {
    engine.ingest(ev.text, Object.assign({}, workerMeta, ev.meta || {}));
  }
  engine.flush('probe-end');
  return commits;
}

// ── ARM A: the guard, in both directions ──────────────────────────────────
const aOpen = SottoHistorySource.isCanonicalLine({ producer: 'redux', route: 'final' });
const aNoField = SottoHistorySource.isCanonicalLine({ route: 'final', start: 0.0 });
const aOther = SottoHistorySource.isCanonicalLine({ producer: 'live', route: 'final' });
say(`ARM A  isCanonicalLine({producer:'redux', route:'final'}) = ${aOpen}`);
say(`ARM A  isCanonicalLine({route:'final'})                  = ${aNoField}   (fail-closed)`);
say(`ARM A  isCanonicalLine({producer:'live', route:'final'}) = ${aOther}   (only the literal 'redux')`);
if (aOpen !== true || aNoField !== false || aOther !== false) {
  problems.push('ARM A: the guard is not the fail-closed literal the source says it is');
}

// ── ARM B: the REDUX line must survive the engine ─────────────────────────
const reduxCommits = drive(REDUX_META);
const reduxAccepted = reduxCommits.filter((c) => c.accepted);
say('');
say(`ARM B  REDUX line (worker stamps producer:'redux')`);
say(`ARM B    commits from the REAL engine = ${reduxCommits.length}`);
for (const c of reduxCommits) {
  say(`ARM B    meta keys the engine built  = [${c.keys.join(', ')}]`);
  say(`ARM B    producer on that meta       = ${JSON.stringify(c.meta.producer)}`);
  say(`ARM B    isCanonicalLine(that meta)  = ${c.accepted}`);
}
say(`ARM B  lines the transcript takes   = ${reduxAccepted.length}`);
if (reduxCommits.length === 0) {
  problems.push('ARM B: the engine committed nothing — the harness, not the claim, is broken');
} else if (!reduxCommits.some((c) => c.keys.includes('producer'))) {
  problems.push('ARM B: REGRESSION — `producer` did not survive the engine '
    + `(keys: [${reduxCommits[0].keys.join(', ')}]). The feed is closed again; the `
    + 'field the worker stamps is being dropped before the choke point.');
} else if (reduxAccepted.length !== reduxCommits.length) {
  problems.push(`ARM B: ${reduxCommits.length - reduxAccepted.length} of `
    + `${reduxCommits.length} stamped line(s) were still refused`);
}

// ── ARM C: the LIVE line must NOT get in (the control) ────────────────────
const liveCommits = drive(LIVE_META);
const liveAccepted = liveCommits.filter((c) => c.accepted);
say('');
say(`ARM C  LIVE line (nvidia streaming: route vote, NO producer)  — the control`);
say(`ARM C    commits from the REAL engine = ${liveCommits.length}`);
for (const c of liveCommits) {
  say(`ARM C    meta keys the engine built  = [${c.keys.join(', ')}]`);
  say(`ARM C    producer on that meta       = ${JSON.stringify(c.meta.producer)}`);
  say(`ARM C    isCanonicalLine(that meta)  = ${c.accepted}`);
}
say(`ARM C  lines the transcript takes   = ${liveAccepted.length}`);
if (liveCommits.length === 0) {
  problems.push('ARM C: the engine committed nothing for a live-shaped stream — the '
    + 'control is broken, so ARM B proves nothing');
}
if (liveAccepted.length !== 0) {
  problems.push(`ARM C: ${liveAccepted.length} LIVE line(s) reached the canonical `
    + 'transcript — the two fields are ONE source again, which is the owner-reported defect');
}
// The two arms must actually differ, or the whole instrument is vacuous.
if (reduxAccepted.length === liveAccepted.length && reduxCommits.length === liveCommits.length) {
  problems.push('ARM B and ARM C agree — the run cannot distinguish a stamped line from '
    + 'an unstamped one, so nothing here is measured');
}

say('');
if (problems.length) {
  for (const p of problems) say(`!! ${p}`);
  say('PRODUCER-PATH-VERDICT: RED');
  process.exit(1);
}
say('PRODUCER-PATH-VERDICT: GREEN — the whole chain is OPEN, end to end:');
say(`  the batch engine's line carries producer:'redux' -> the REAL engine forwards it`);
say(`  (commit meta keys [${reduxCommits[0].keys.join(', ')}]) -> the choke point accepts it`);
say(`  (${reduxAccepted.length}/${reduxCommits.length}) while the LIVE nvidia shape is refused`);
say(`  (${liveAccepted.length}/${liveCommits.length}): the two fields are different sources.`);
process.exit(0);
