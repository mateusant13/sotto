'use strict';

/**
 * Sotto — the PANEL HALF of `_main/redux-live-overlay-oracle.py`.
 *
 * WHAT THIS ANSWERS. The Python oracle drives the SHIPPED `publish_captions`
 * and records the events a real worker would emit. Those events are worthless
 * until someone walks them through the REAL panel engine: the question "which
 * line does the transcript take" is decided by `app/panel/caption-formulation.js`
 * (it BUILDS the meta the store reads) and by `app/panel/history-source.js`
 * (it DECIDES whether that meta may enter the transcript). Re-typing either
 * decision here would only prove that this file agrees with itself — the
 * 2026-10-07 defect (`caption-formulation.js commit()` dropped the worker's
 * `producer` before the choke point) is exactly the class a re-typed copy
 * cannot see.
 *
 * CONTRACT (one JSON object on stdout, nothing else):
 *   { "arms": { "<name>": { "row_text": string|null,
 *                           "canonical": [ {line, route, producer}, ... ],
 *                           "commits": n,
 *                           "panel_uses_transcript_route": bool } },
 *     "engine": "<relative path>", "source": "<relative path>" }
 *
 * `row_text` is what the live box shows for that arm (the LAST line the engine
 * committed); `canonical` is every commit the shipped `transcriptRoute` admits.
 * A setup failure prints to STDERR and exits 2, so a broken harness can never
 * be read as an empty history.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HERE = __dirname;
const ROOT = path.resolve(HERE, '..');
const ENGINE = path.join(ROOT, 'app', 'panel', 'caption-formulation.js');
const SOURCE = path.join(ROOT, 'app', 'panel', 'history-source.js');
const PANEL = path.join(ROOT, 'app', 'panel', 'panel.js');

function setupError(msg) {
  process.stderr.write('SETUP ERROR: ' + msg + '\n');
  process.exit(2);
}

/**
 * Load one of the panel's files the way BOTH of its consumers do.
 *
 * `app/package.json` declares `"type": "module"`, so a CommonJS `require()` of
 * a dual file whose body assigns `module.exports` returns an EMPTY namespace
 * (measured in `_main/_redux-producer-path.js`). Evaluating the source with
 * `module`/`window` present is what a browser tab does and what the panel does;
 * it keeps working across the `type: module` boundary.
 */
function loadDualExport(file, globalName) {
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
    setupError(path.relative(ROOT, file) + ' exported nothing: neither '
      + 'module.exports nor window.' + globalName + ' was set.');
  }
  return exported;
}

const armsPath = process.argv[2];
if (!armsPath) setupError('usage: node redux-live-overlay-panel-oracle.js <arms.json>');
for (const p of [armsPath, ENGINE, SOURCE, PANEL]) {
  if (!fs.existsSync(p)) setupError('missing ' + path.relative(ROOT, p));
}

const payload = JSON.parse(fs.readFileSync(armsPath, 'utf8'));
const formulation = loadDualExport(ENGINE, 'SottoFormulation');
const sourceApi = loadDualExport(SOURCE, 'SottoHistorySource');
if (typeof formulation.createEngine !== 'function') {
  setupError(path.relative(ROOT, ENGINE) + ' did not export createEngine.');
}
if (typeof sourceApi.transcriptRoute !== 'function') {
  setupError(path.relative(ROOT, SOURCE) + ' did not export transcriptRoute.');
}

// The panel's own choke point, as `panel.js recordHistory` writes it. Asserted
// as a boolean so a re-wiring of the panel to a different decision is visible
// in the report instead of silently making this harness describe a dead path.
const panelUsesTranscriptRoute = fs.readFileSync(PANEL, 'utf8')
  .includes('transcriptRoute(meta)');

/** The meta the shell builds for a caption event: every key but type/text. */
function metaOf(event) {
  const meta = {};
  for (const key of Object.keys(event)) {
    if (key === 'type' || key === 'text') continue;
    meta[key] = event[key];
  }
  return meta;
}

/**
 * Drive the REAL engine with one arm's events and read what the REAL choke
 * point makes of the commits. One engine per arm, as one source is one engine
 * in the panel.
 */
function drive(events) {
  const commits = [];
  let lastCommitted = null;
  const engine = formulation.createEngine({
    onProvisional: () => {},
    onCommit: (text, reason, meta) => {
      const route = sourceApi.transcriptRoute(meta);
      commits.push({
        line: text,
        reason,
        meta,
        route,
        producer: sourceApi.producerOf(meta),
        accepted: route !== null,
      });
      lastCommitted = text;
    },
  });
  for (const event of events || []) {
    if (!event || event.type !== 'caption' || typeof event.text !== 'string') continue;
    engine.ingest(event.text, metaOf(event));
  }
  engine.flush('oracle-end');
  const visible = typeof engine.visible === 'function' ? engine.visible() : '';
  return {
    row_text: lastCommitted !== null ? lastCommitted : (visible || null),
    canonical: commits.filter((c) => c.accepted)
      .map((c) => ({ line: c.line, route: c.route, producer: c.producer })),
    commits: commits.length,
    panel_uses_transcript_route: panelUsesTranscriptRoute,
  };
}

const arms = {};
for (const arm of payload.arms || []) {
  if (!arm || typeof arm.name !== 'string') continue;
  arms[arm.name] = drive(arm.events);
}

process.stdout.write(JSON.stringify({
  arms,
  engine: path.relative(ROOT, ENGINE),
  source: path.relative(ROOT, SOURCE),
}) + '\n');
