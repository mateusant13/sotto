'use strict';

/**
 * Sotto — LIVE field vs HISTORY field: are they the SAME source, or TWO?
 *
 * OWNER 2026-10-07, verbatim: *"o live nvidia do painel do sotto é pra ser o
 * nvidia funcionando, enquanto o historico nao é pra ser NUNCA o historico do
 * live nvidia. é pra ser do parakeet redux. e eu to vendo q nao ta desse
 * jeito"*.
 *
 * WHAT IT MEASURES — the SAME recorded stream, both fields, and the SOURCE of
 * each:
 *
 *   LIVE    — every commit the real ENGINE (`caption-formulation.js`) hands the
 *             panel; the bottom box paints ALL of them. The stream's own events
 *             declare `model: nemotron-3.5-asr-streaming-0.6b-int8`, so this is
 *             the nvidia path by the artefact itself.
 *   HISTORY — every line that reaches the real STORE (`history-store.js`), i.e.
 *             what the top feed is read back from.
 *
 * THE CLAIM UNDER TEST is NOT the old one ("the transcript takes only
 * `route=final`" — that is `_main/historico-vs-redux-probe.js`, still GREEN, and
 * NOT contradicted here). It is the owner's: the transcript must be a DIFFERENT
 * SOURCE. A `route=final` line the LIVE engine produced is still the live
 * path's own history. So the panel's choke point now ALSO requires the line to
 * declare the CANONICAL producer (`history-source.js`), which the live engine
 * never does.
 *
 * ARMS, all in ONE command and all RED-able:
 *   asShipped   — shipped choke point (route=final AND canonical producer) on
 *                 live commits. HISTORY = 0 while LIVE = every commit → the two
 *                 fields are NO LONGER one source. ("the NEVER half")
 *   reduxTagged — the SAME commits stamped `producer:'redux'`. HISTORY > 0 →
 *                 the canonical path is OPEN, not a fake that can never fill.
 *   before      — the pre-cure permissive choke point (`(route||'final')==='final'`)
 *                 on live commits. HISTORY == LIVE → the TWO FIELDS ARE ONE,
 *                 the defect the owner saw. The control for the check.
 *
 *   node _main/live-vs-history-source-oracle.js
 *
 * Exit codes: 0 PASS, 1 FAIL, 2 setup error. No window, no audio, no shell —
 * file reads, one real engine and one real store in a throwaway root.
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
const sourcePath = path.join(REPO, 'app', 'panel', 'history-source.js');
const enginePath = path.join(REPO, 'app', 'panel', 'caption-formulation.js');
const panelPath = path.join(REPO, 'app', 'panel', 'panel.js');
const storePath = path.join(REPO, 'app', 'panel', 'history-store.js');

// The panel's choke point, as `panel.js recordHistory` writes it: the route
// guard AND the canonical-producer guard. The producer half is the REAL module
// (executed below, never regexed); these literals only pin that the panel USES
// it, so the mechanical predicate here cannot drift from the panel silently.
const PANEL_ROUTE_GUARD = "if (route !== 'final') return;";
const PANEL_SOURCE_CALL = 'SottoHistorySource.isCanonicalLine';

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

/** Replay `events` through `engineMod`; return one commit per `onCommit`. */
function replay(events, engineMod) {
  const commits = [];
  const engine = engineMod.createEngine({
    onCommit: (text, reason, meta) => commits.push({
      text,
      reason,
      route: (meta && meta.route) || null,
      routeSource: (meta && meta.routeSource) || null,
      start: meta && typeof meta.start === 'number' ? meta.start : null,
    }),
    onProvisional: () => {},
  });
  for (const c of events) {
    engine.ingest(c.text, { start: c.start, end: c.end, final: c.final });
    // panel.js `wireStatus` flush: worst case, after EVERY event.
    engine.flush('status-change');
  }
  engine.flush('stream-end');
  return commits;
}

function loadEngine(modPath) {
  delete require.cache[require.resolve(modPath)];
  return require(modPath);
}

// The one expression the shipped engine uses to derive the route. Replacing it
// with `null` reproduces the BEFORE tree (no route stamped) — the exact defect
// the owner saw — built from the file itself, never from git.
const ROUTE_LINE = 'const route = routeFor(reason);';
const ROUTE_MUTANT = 'const route = null; /* BEFORE-ARM: the vacuous engine */';

function engineWithLine(replacement) {
  const src = fs.readFileSync(enginePath, 'utf8');
  if (!src.includes(ROUTE_LINE)) return null;
  const tmp = path.join(HERE, '_lvs-engine-mutant.js');
  fs.writeFileSync(tmp, src.replace(ROUTE_LINE, replacement), 'utf8');
  return tmp;
}

/**
 * Hand `commits` to the REAL store under `root`, keeping only those the panel's
 * choke point `accepts`. `producer` (when given) is stamped on every commit —
 * that is how the redux arm differs from the live arm, and nothing else.
 */
function writeHistory(commits, accepts, producer, root) {
  fs.rmSync(root, { recursive: true, force: true });
  process.env.SOTTO_HISTORY_ROOT = root;
  delete require.cache[require.resolve(storePath)];
  const store = require(storePath);

  const tagged = producer ? commits.map((c) => ({ ...c, producer })) : commits;
  const accepted = tagged.filter(accepts);
  for (const c of accepted) {
    store.append(c.text, {
      source: 'redux',
      route: c.route,
      routeSource: c.routeSource,
      start: c.start,
      reason: c.reason,
    });
  }
  return { handed: commits.length, accepted: accepted.length, disk: routesOnDisk(root) };
}

function main() {
  for (const p of [streamPath, sourcePath, enginePath, panelPath, storePath]) {
    if (!fs.existsSync(p)) {
      console.log(`SETUP ERROR: missing ${path.relative(REPO, p)}`);
      return 2;
    }
  }

  const source = require(sourcePath);
  const events = readStream(streamPath);
  if (!events.length) {
    console.log(`SETUP ERROR: ${path.relative(REPO, streamPath)} carries no caption event`);
    return 2;
  }

  // The stream's OWN model id — this is what makes LIVE the nvidia path by the
  // artefact, not by a label.
  const firstModel = (() => {
    for (const l of fs.readFileSync(streamPath, 'utf8').split(/\r?\n/)) {
      try { const o = JSON.parse(l.trim()); if (o && o.model) return o.model; } catch { /* skip */ }
    }
    return '(none)';
  })();

  const panelSrc = fs.readFileSync(panelPath, 'utf8');
  const panelHasRouteGuard = panelSrc.includes(PANEL_ROUTE_GUARD);
  const panelHasSourceCall = panelSrc.includes(PANEL_SOURCE_CALL);

  const commits = replay(events, loadEngine(enginePath));
  const mutantTmp = engineWithLine(ROUTE_MUTANT);
  if (!mutantTmp) {
    console.log(`SETUP ERROR: ${ROUTE_LINE} is not in caption-formulation.js`);
    return 2;
  }
  const beforeCommits = replay(events, loadEngine(mutantTmp));

  // The SHIPPED panel choke point: route=final AND the line declares the
  // canonical producer (the REAL `history-source.js` predicate, executed).
  const shipped = (c) => c.route === 'final' && source.isCanonicalLine(c);
  // The PRE-CURE pair: the vacuous engine (no route stamped) AND the permissive
  // choke point — the two-engine defect the owner saw, where the two fields were
  // ONE source.
  const preCure = (c) => ((c.route || 'final') === 'final');

  const ROOT = path.join(REPO, 'history-verify');
  const asShipped = writeHistory(commits, shipped, null, path.join(ROOT, 'source-as-shipped'));
  const reduxTagged = writeHistory(commits, shipped, source.CANONICAL_PRODUCER, path.join(ROOT, 'source-redux'));
  const before = writeHistory(beforeCommits, preCure, null, path.join(ROOT, 'source-before'));
  fs.rmSync(mutantTmp, { force: true });

  console.log(`stream    : ${path.relative(REPO, streamPath)} — ${events.length} event(s), model=${firstModel}`);
  console.log(`source    : ${path.relative(REPO, sourcePath)}   (LIVE_PRODUCER=${source.LIVE_PRODUCER} CANONICAL_PRODUCER=${source.CANONICAL_PRODUCER})`);
  console.log(`panel     : ${path.relative(REPO, panelPath)}   route-guard=${panelHasRouteGuard} uses-isCanonicalLine=${panelHasSourceCall}`);

  const line = (label, r) => {
    console.log(`\n${label}`);
    console.log(`  LIVE    : ${r.handed} commit(s) handed to the panel (the bottom box paints all)`);
    console.log(`  HISTORY : ${r.accepted} accepted by the choke point, on disk ${r.disk.count} — ${JSON.stringify(r.disk.found)}`);
  };
  line('AS SHIPPED (route=final AND canonical producer) on the LIVE nvidia commits', asShipped);
  line('SAME commits stamped producer:\'redux\' (the canonical path — is it OPEN?)', reduxTagged);
  line('BEFORE (pre-cure permissive: (route||\'final\')===\'final\') on the LIVE commits', before);

  const arms = [];
  function arm(name, real, want) {
    const ok = JSON.stringify(real) === JSON.stringify(want);
    arms.push(ok);
    console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
    console.log(`       real = ${JSON.stringify(real)}`);
    console.log(`       want = ${JSON.stringify(want)}`);
  }

  console.log('\n--- the predicate, executed (the REAL history-source.js) ---');
  arm('the predicate REFUSES the live producer', source.isCanonicalLine({ producer: 'live' }), false);
  arm('the predicate REFUSES an absent producer (fail-closed)', source.isCanonicalLine(undefined), false);
  arm('the predicate REFUSES an empty meta (fail-closed)', source.isCanonicalLine({}), false);
  arm('the predicate ACCEPTS the canonical producer', source.isCanonicalLine({ producer: 'redux' }), true);
  arm('producerOf reports an unknown producer verbatim (not rounded to canonical)', source.producerOf({ producer: 'nvidia' }), 'nvidia');

  console.log('\n--- the panel WIRES it (panel.js is DOM-bound; its source is asserted) ---');
  arm('panel.js recordHistory still carries the route guard verbatim', panelHasRouteGuard, true);
  arm('panel.js recordHistory calls the canonical-producer predicate', panelHasSourceCall, true);

  console.log('\n--- THE CONTROL PAIR: can the two fields still draw from ONE source? ---');
  arm('AS SHIPPED: every live commit is still handed to the LIVE box (not "drop the live path")',
      asShipped.handed > 0, true);
  arm('AS SHIPPED: HISTORY takes ZERO lines from the LIVE nvidia path (the "NUNCA")',
      asShipped.disk.count, 0);
  arm('REDUX-TAGGED: the canonical path is OPEN — HISTORY takes the closed lines (not a dead end)',
      reduxTagged.disk.count > 0, true);
  arm('REDUX-TAGGED: and it is exactly the worker-closed lines',
      Object.keys(reduxTagged.disk.found).sort(), ['final']);
  arm('BEFORE: the pre-cure choke point made the two fields ONE (the defect the owner saw)',
      before.disk.count === before.handed && before.handed > 0, true);
  arm('CONTROL: the shipped and pre-cure HISTORY counts DIFFER (the check is not vacuous)',
      asShipped.disk.count !== before.disk.count, true);

  const ok = arms.every(Boolean);
  console.log(`\nRESULT: ${ok ? 'GREEN' : 'RED'} — ${arms.filter(Boolean).length}/${arms.length} arm(s)`);
  return ok ? 0 : 1;
}

process.exit(main());
