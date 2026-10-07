'use strict';

/**
 * Sotto — PANEL LIVE vs HISTORY probe (owner order 2026-10-06).
 *
 *   "o live nvidia do painel do sotto e' pra ser o nvidia funcionando, enquanto
 *    o historico nao e' pra ser NUNCA o historico do live nvidia. e' pra ser do
 *    parakeet redux. e eu to vendo q nao ta desse jeito"
 *
 * WHAT IT MEASURES, and it is the SAME probe for both colours:
 *
 *   LIVE   — every commit the ENGINE hands the panel. The bottom box (`#caption-list`)
 *            is fed by these, painted by `panel.js renderProvisional`/`addCaption`.
 *   HISTORY — every line that reaches the STORE (`history-store.js`), i.e. what
 *            the TOP feed (`#history-list`) is read back from.
 *
 * BEFORE  — an engine that stamps NO route: the model the defect was measured
 *           on (`const route = null`), and the state the owner was looking at.
 *           Every live partial reaches the history → the two fields are ONE.
 * AFTER   — the engine in `app/panel/caption-formulation.js`: the route comes
 *           from the worker's `final` flag, an ABSENT flag is fail-closed, and
 *           `panel.js recordHistory` declines anything that is not `final`.
 *
 * The BEFORE arm is a MUTATION of the live engine, built into a COPY at run time
 * exactly like `historico-vs-redux-probe.js --gate-off` mutates the store — so
 * the pair is derived from the file itself, not from git (the change is
 * uncommitted, `git show HEAD:` is a different tree).
 *
 *   node _main/panel-live-vs-history-probe.js
 *   node _main/panel-live-vs-history-probe.js --stream _main/_route-stream-long.jsonl
 *
 * Exit codes: 0 PASS, 1 FAIL, 2 setup error. No window: file reads + one store.
 */

const fs = require('node:fs');
const path = require('node:path');

const HERE = __dirname;
const REPO = path.join(HERE, '..');

const args = process.argv.slice(2);
function flagValue(name) {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
}

const streamPath = path.resolve(
  flagValue('--stream') || path.join(HERE, '_route-stream-long.jsonl'),
);
const enginePath = path.join(REPO, 'app', 'panel', 'caption-formulation.js');
const panelPath = path.join(REPO, 'app', 'panel', 'panel.js');
const storePath = path.join(REPO, 'app', 'panel', 'history-store.js');

// The one expression the AFTER engine uses to derive the route. Replacing it
// with `null` reproduces the BEFORE tree exactly as it stood (no engine stamped
// any route; `panel.js` fell back to `|| 'final'`), without touching any file
// on disk.
const ROUTE_LINE = 'const route = routeFor(reason);';
const ROUTE_MUTANT = 'const route = null; // BEFORE-ARM: the vacuous engine';

// The panel's own choke point, as a source-level literal — the real `panel.js`
// is DOM-bound and cannot be executed here, so its guard is (a) asserted
// present on disk and (b) applied mechanically, which is what it does.
const PANEL_GUARD = "if (route !== 'final') return;";

function readStream(file) {
  const out = [];
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const t = line.trim();
    if (!t) continue;
    try {
      const o = JSON.parse(t);
      if (o && (o.type === 'caption' || o.text !== undefined)) {
        out.push({ text: String(o.text || ''), start: o.start ?? null, end: o.end ?? null, final: o.final });
      }
    } catch { /* not a caption event */ }
  }
  return out;
}

function engineWithLine(replacement) {
  const src = fs.readFileSync(enginePath, 'utf8');
  const tmp = path.join(HERE, '_plvh-engine-mutant.js');
  fs.writeFileSync(tmp, src.replace(ROUTE_LINE, replacement), 'utf8');
  delete require.cache[tmp];
  return { mod: require(tmp), tmp };
}

function routesOnDisk(root) {
  const found = {};
  if (!fs.existsSync(root)) return { found, count: 0 };
  for (const day of fs.readdirSync(root)) {
    const folder = path.join(root, day);
    if (!fs.statSync(folder).isDirectory()) continue;
    for (const name of fs.readdirSync(folder)) {
      if (!name.endsWith('.md')) continue;
      for (const l of fs.readFileSync(path.join(folder, name), 'utf8').split(/\r?\n/)) {
        const m = /^-\s+\[(\d\d:\d\d:\d\d)\]\s+(.*)$/.exec(l);
        if (!m) continue;
        const tail = /\s*<!--\s*(route=\S+)/.exec(m[2]);
        const route = tail ? tail[1].slice('route='.length) : null;
        found[route] = (found[route] || 0) + 1;
      }
    }
  }
  return { found, count: Object.values(found).reduce((a, b) => a + b, 0) };
}

/**
 * Hand the commits to the REAL store under `root`.
 *
 * `panelAccepts` is `panel.js recordHistory`'s choke point, as the panel writes
 * it in the arm under test: the BEFORE arm is the OLD permissive guard,
 * `(route || 'final') === 'final'` — always true; the AFTER arm is the shipped
 * fail-closed `route === 'final'`.
 */
function run(engineMod, root, events, panelAccepts, flushEvery) {
  fs.rmSync(root, { recursive: true, force: true });
  process.env.SOTTO_HISTORY_ROOT = root;
  delete require.cache[require.resolve(storePath)];
  const store = require(storePath);

  const commits = [];
  const engine = engineMod.createEngine({
    onCommit: (text, reason, meta) => commits.push({
      text,
      reason,
      route: (meta && meta.route) || null,
      start: meta && typeof meta.start === 'number' ? meta.start : null,
    }),
    onProvisional: () => {},
  });

  for (const c of events) {
    engine.ingest(c.text, { start: c.start, end: c.end, final: c.final });
    // panel.js wireStatus flush, worst case: after EVERY event (the arm the
    // repo's own probe uses). With `flushEvery=false` only the ingest
    // boundaries close a line — the natural cadence.
    if (flushEvery !== false) engine.flush('status-change');
  }
  engine.flush('stream-end');

  // panel.js recordHistory — the choke point, applied as the panel writes it.
  const panelAccepted = commits.filter(panelAccepts);
  for (const c of panelAccepted) store.append(c.text, { source: 'live', route: c.route, start: c.start, reason: c.reason });

  const disk = routesOnDisk(root);
  const handed = commits.reduce((a, c) => ((a[c.route] = (a[c.route] || 0) + 1), a), {});
  return { commits, handed, panelAccepted: panelAccepted.length, disk };
}

function main() {
  if (!fs.existsSync(enginePath) || !fs.existsSync(storePath) || !fs.existsSync(panelPath)) {
    console.log('SETUP ERROR: engine, store or panel missing');
    return 2;
  }
  const events = readStream(streamPath);
  if (!events.length) {
    console.log(`SETUP ERROR: ${streamPath} carries no caption event`);
    return 2;
  }

  const src = fs.readFileSync(enginePath, 'utf8');
  if (!src.includes(ROUTE_LINE)) {
    console.log(`SETUP ERROR: the route line is not in caption-formulation.js:\n  ${ROUTE_LINE}`);
    return 2;
  }
  const panelSrc = fs.readFileSync(panelPath, 'utf8');
  const guardPresent = panelSrc.includes(PANEL_GUARD);

  const real = require(enginePath);
  const before = engineWithLine(ROUTE_MUTANT);
  // BEFORE = the vacuous engine + the OLD permissive panel guard
  //          `const route = (meta && meta.route) || 'final';`
  // AFTER  = the shipped engine + the shipped fail-closed guard.
  const beforeRes = run(
    before.mod,
    path.resolve(flagValue('--root-before') || path.join(REPO, 'history-verify', 'plvh-before')),
    events,
    (c) => ((c.route || 'final') === 'final'),
  );
  const after = run(
    real,
    path.resolve(flagValue('--root-after') || path.join(REPO, 'history-verify', 'plvh-after')),
    events,
    (c) => c.route === 'final',
  );
  // THE FAIL-CLOSED PROPERTY, proven rather than asserted: a stream from a
  // worker that stamps NO `final` at all (the pipeline as it stands, the flag's
  // producer is `worker/sotto_worker.py:_event` — see the receipt). At the
  // panel's WORST case (a status-change flush after every event) it must put a
  // live caption in the history ZERO times — the "NUNCA" half. At the NATURAL
  // cadence the audio's own boundaries still close lines, so the history is not
  // emptied: those are the lines the audio ended, not the panel's deadline.
  const legacy = run(
    real,
    path.resolve(flagValue('--root-legacy') || path.join(REPO, 'history-verify', 'plvh-legacy')),
    events.map((e) => ({ ...e, final: undefined })),
    (c) => c.route === 'final',
  );
  const legacyNatural = run(
    real,
    path.resolve(flagValue('--root-legacy-natural') || path.join(REPO, 'history-verify', 'plvh-legacy-natural')),
    events.map((e) => ({ ...e, final: undefined })),
    (c) => c.route === 'final',
    false,
  );
  fs.rmSync(before.tmp, { force: true });

  console.log(`stream    : ${path.relative(REPO, streamPath)} — ${events.length} event(s)` +
    ` (final:true ${events.filter((e) => e.final === true).length}, final:false ${events.filter((e) => e.final === false).length})`);
  console.log(`engine    : ${path.relative(REPO, enginePath)}`);
  console.log(`panel     : ${path.relative(REPO, panelPath)}   guard(${PANEL_GUARD}) present=${guardPresent}`);

  const line = (label, r) => {
    const disk = JSON.stringify(r.disk.found);
    console.log(`\n${label}`);
    console.log(`  LIVE    : ${r.commits.length} commit(s) handed to the panel — ${JSON.stringify(r.handed)}`);
    console.log(`  HISTORY : panel accepted ${r.panelAccepted}, on disk ${r.disk.count} line(s) — ${disk}`);
  };
  line('BEFORE (engine with `route = null` — the defect the owner saw)', beforeRes);
  line('AFTER  (the shipped engine)', after);
  line('AFTER  (a stream that stamps NO `final` — fail-closed, the "NUNCA" half)', legacy);
  line('AFTER  (same stream, NATURAL cadence — the audio still closes lines)', legacyNatural);

  const arms = [];
  function arm(name, real, want) {
    const ok = JSON.stringify(real) === JSON.stringify(want);
    arms.push(ok);
    console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
    console.log(`       real = ${JSON.stringify(real)}`);
    console.log(`       want = ${JSON.stringify(want)}`);
  }

  console.log('\n--- the split, both colours of the SAME probe ---');
  arm('BEFORE: the two fields are ONE — every commit reaches the history',
      beforeRes.disk.count === beforeRes.commits.length && beforeRes.disk.count > 0, true);
  arm('AFTER : no live caption (provisional-draft) reaches the history',
      Object.keys(after.disk.found).filter((r) => r === 'provisional-draft'), []);
  arm('AFTER : every history line is a worker-closed line (route=final)',
      Object.keys(after.disk.found).sort(), ['final']);
  arm('AFTER : the same audio still reaches the history (not "write nothing")',
      after.disk.count > 0, true);
  arm('AFTER : the LIVE box is untouched — the panel is still handed the live partial',
      (after.handed['provisional-draft'] || 0) > 0 && (after.handed.final || 0) > 0, true);
  arm('AFTER : a stream with NO `final` key writes NOTHING at the worst-case flush cadence (the "NUNCA" half)',
      legacy.disk.count, 0);
  arm('AFTER : a stream with NO `final` key is NOT emptied — the audio still closes lines',
      legacyNatural.disk.count > 0, true);
  arm('AFTER : the panel guard is FAIL-CLOSED (no `|| final` default)',
      guardPresent && /const route = meta && meta\.route;/.test(panelSrc), true);
  arm('control: the two values DIFFER (the probe is not vacuous)',
      beforeRes.disk.count !== after.disk.count, true);

  const ok = arms.every(Boolean);
  console.log(`\nRESULT: ${ok ? 'GREEN' : 'RED'} — ${arms.filter(Boolean).length}/${arms.length} arm(s)`);
  return ok ? 0 : 1;
}

process.exit(main());
