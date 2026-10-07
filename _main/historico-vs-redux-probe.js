'use strict';

/**
 * Sotto — HISTORICO vs REDUX probe (owner 2026-10-06).
 *
 *   "o historico simplesmente mostra a legenda ao vivo, inves de mostrar a
 *    versao processada pelo redux."
 *
 * WHAT IT MEASURES. One recorded stream, replayed through the REAL engine
 * (`app/panel/caption-formulation.js`) with the REAL panel wiring, and every
 * commit handed to the REAL store (`app/panel/history-store.js`). It prints
 * the pair the acceptance asks for, from the SAME audio:
 *
 *   LIVE  — the last `final:false` partial the worker sent for a line. That is
 *           what the box paints (`renderProvisional(visibleText())`), the raw
 *           streaming caption.
 *   REDUX — the `final:true` text the worker's SECOND PASS produced (M3) —
 *           what the history is supposed to carry.
 *
 * THE PANEL WIRING IT REPRODUCES. `panel.js wireStatus` calls
 * `engine.flush('status-change')` on EVERY worker status, and this worker
 * restarts constantly (MEASURED: `restarts=36 deaths=18` in
 * `_main/panel-state.json`; 19 `BRIDGE_EXIT rc=1` in `_main/webview-run.log`).
 * The probe fires that flush after EVERY event — the worst case, and the same
 * worst case `history-route-oracle.js` arm 2 and `transcript-append-oracle.js`
 * already use as their control. The arms' claim holds at ANY cadence: a flush
 * may never put a provisional line in the transcript.
 *
 * `--gate-off` loads the store with the one HISTORICO-VS-REDUX guard line
 * removed — the EXACT before-state of this change, derived from the file itself
 * rather than from git (the 2026-10-06 cure is uncommitted, so `git show HEAD:`
 * is a pre-cure store and not a control). Nothing else differs.
 *
 *   node _main/historico-vs-redux-probe.js
 *   node _main/historico-vs-redux-probe.js --gate-off      (RED: the defect)
 *   node _main/historico-vs-redux-probe.js --max-events 400 --pair-lines 6
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

const streamPath = path.resolve(flagValue('--stream') || path.join(HERE, '_route-stream-long.jsonl'));
const root = path.resolve(flagValue('--root') || path.join(REPO, 'history-verify', 'historico-vs-redux'));
const maxEvents = Number(flagValue('--max-events') || 0) || Infinity;
const pairLines = Number(flagValue('--pair-lines') || 12);
const gateOff = args.includes('--gate-off');

const enginePath = path.join(REPO, 'app', 'panel', 'caption-formulation.js');
const storePath = path.join(REPO, 'app', 'panel', 'history-store.js');
const panelPath = path.join(REPO, 'app', 'panel', 'panel.js');
const webviewPath = path.join(REPO, 'app', 'webview', 'sotto_webview.py');

const GUARD_LINE =
  "  if (String((meta && meta.route) || '').trim() === 'provisional-draft') return null;";

/** The recorded stream: `{"type":"caption","text":…,"final":true|false,…}`. */
function readStream(file) {
  if (!fs.existsSync(file)) {
    console.log(`SETUP ERROR: no stream at ${file}`);
    process.exit(2);
  }
  const out = [];
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed[0] !== '{') continue;
    let row;
    try {
      row = JSON.parse(trimmed);
    } catch {
      continue;
    }
    if (row.type !== 'caption' || !row.text) continue;
    out.push({
      text: String(row.text),
      start: typeof row.start === 'number' ? row.start : null,
      end: typeof row.end === 'number' ? row.end : null,
      final: row.final === true,
    });
  }
  return out;
}

/** The REAL store, or the exact before-state (the guard line deleted). */
function loadStore() {
  if (!gateOff) return require(storePath);
  const src = fs.readFileSync(storePath, 'utf8');
  if (!src.includes(GUARD_LINE)) {
    console.log('SETUP ERROR: the HISTORICO-VS-REDUX guard line is not in history-store.js');
    process.exit(2);
  }
  const tmp = path.join(HERE, '_historico-vs-redux-control-store.js');
  fs.writeFileSync(tmp, src.replace(GUARD_LINE, ''), 'utf8');
  return require(tmp);
}

function routesOnDisk() {
  const found = {};
  const files = [];
  for (const day of fs.existsSync(root) ? fs.readdirSync(root) : []) {
    const folder = path.join(root, day);
    if (!fs.statSync(folder).isDirectory()) continue;
    for (const name of fs.readdirSync(folder)) {
      if (!name.endsWith('.md')) continue;
      files.push(path.join(folder, name));
    }
  }
  const lines = [];
  for (const file of files) {
    for (const l of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
      const m = /^-\s+\[(\d\d:\d\d:\d\d)\]\s+(.*)$/.exec(l);
      if (!m) continue;
      const tail = /\s*<!--\s*(route=\S+)(?:\s+start=([\d.]+))?/.exec(m[2]);
      const route = tail ? tail[1].slice('route='.length) : null;
      found[route] = (found[route] || 0) + 1;
      lines.push({
        time: m[1],
        text: tail ? m[2].slice(0, tail.index).trim() : m[2],
        route,
        start: tail && tail[2] ? Number(tail[2]) : null,
      });
    }
  }
  return { found, lines, files };
}

const norm = (s) => String(s || '').toLowerCase().replace(/[.!?…,·]+/g, '').replace(/\s+/g, ' ').trim();

function main() {
  if (!fs.existsSync(enginePath) || !fs.existsSync(storePath)) {
    console.log('SETUP ERROR: the engine or the store is missing');
    return 2;
  }

  const all = readStream(streamPath);
  const events = all.slice(0, maxEvents === Infinity ? undefined : maxEvents);
  if (!events.length) {
    console.log(`SETUP ERROR: ${streamPath} carries no caption event`);
    return 2;
  }
  console.log(`stream    : ${path.relative(REPO, streamPath)} — ${all.length} event(s), replaying ${events.length}`);

  // Fresh root: a census over this run only (never the owner's `history/`).
  fs.rmSync(root, { recursive: true, force: true });
  process.env.SOTTO_HISTORY_ROOT = root;
  const store = loadStore();
  console.log(`store     : ${path.relative(REPO, storePath)}${gateOff ? '  (--gate-off: the guard line DELETED)' : ''}`);
  console.log(`root      : ${root}`);

  const F = require(enginePath);
  const commits = [];
  const engine = F.createEngine({
    onCommit: (text, reason, meta) => commits.push({
      text,
      reason,
      route: (meta && meta.route) || null,
      start: meta && typeof meta.start === 'number' ? meta.start : null,
      fileText: (meta && typeof meta.fileText === 'string' && meta.fileText) || text,
    }),
    onProvisional: () => {},
  });

  for (const c of events) {
    engine.ingest(c.text, { start: c.start, end: c.end, final: c.final });
    // panel.js `wireStatus` — a status change flushes the held tail. Worst case:
    // after every event. See the header for why the claim is cadence-free.
    engine.flush('status-change');
  }
  engine.flush('stream-end');

  const written = [];
  for (const c of commits) {
    const entry = store.append(c.fileText, {
      source: 'live',
      route: c.route,
      start: c.start,
      reason: c.reason,
    });
    if (entry) written.push({ ...entry, route: c.route });
  }

  const { found, lines, files } = routesOnDisk();
  console.log(`\ncommits   : ${commits.length} handed to the panel — ` +
    `${JSON.stringify(commits.reduce((a, c) => ((a[c.route] = (a[c.route] || 0) + 1), a), {}))}`);
  console.log(`on disk   : ${written.length} line(s) in ${files.length} file(s) — ${JSON.stringify(found)}`);

  // ── THE PAIR: the same audio, LIVE (the stream's partial) vs REDUX (final) ─
  const liveByStart = new Map();
  for (const c of events) if (!c.final && c.start !== null) liveByStart.set(c.start, c.text);
  let identical = 0;
  for (const line of lines) {
    const live = line.start !== null && liveByStart.has(line.start) ? liveByStart.get(line.start) : '(none)';
    if (norm(live) === norm(line.text)) identical += 1;
  }
  console.log('\nLIVE (the stream\'s last partial for the line) vs HISTORY (the file):');
  const starts = Array.from(new Set(lines.map((l) => l.start)));
  for (const s of starts.slice(0, pairLines)) {
    const line = lines.find((l) => l.start === s);
    const live = liveByStart.has(s) ? liveByStart.get(s) : '(none)';
    console.log(`  start=${s}`);
    console.log(`    LIVE  "${live}"`);
    console.log(`    FILE  "${line.text}"  <!-- route=${line.route} -->`);
  }
  console.log(`\n  a history line word-for-word the LIVE partial: ${identical}/${lines.length}` +
    ' (the rest were RE-DECODED by the worker\'s second pass)');

  // ── THE ARMS ─────────────────────────────────────────────────────────────
  const results = [];
  function arm(name, real, want) {
    const ok = JSON.stringify(real) === JSON.stringify(want);
    results.push(ok);
    console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
    console.log(`       real = ${JSON.stringify(real)}`);
    console.log(`       want = ${JSON.stringify(want)}`);
  }

  arm(
    'no provisional draft reaches the transcript (any flush cadence)',
    Object.keys(found).filter((r) => r === 'provisional-draft'),
    [],
  );
  arm(
    'every line on disk is a worker-closed line (route=final)',
    Object.keys(found).sort(),
    ['final'],
  );
  arm(
    'the same audio reached the file at all (the fix is not "write nothing")',
    lines.length > 0,
    true,
  );
  // The fix is at the HISTORY, not at the box: the engine still hands the panel
  // the provisional line, so `addCaption` keeps painting it. If a future change
  // "fixes" this by dropping the provisional commit in the engine, the live box
  // loses text and this arm goes RED.
  arm(
    'the LIVE BOX is untouched: the panel is still handed the provisional line',
    Array.from(new Set(commits.map((c) => c.route))).sort(),
    ['final', 'provisional-draft'],
  );
  // The two guards the probe CANNOT execute (panel.js is DOM-bound; the webview
  // store is Python). Source-level, so deleting a guard goes RED here.
  arm(
    'guard present — panel.js recordHistory declines a provisional-draft',
    /if \(route !== 'final'\) return;/.test(fs.readFileSync(panelPath, 'utf8')),
    true,
  );
  arm(
    'guard present — sotto_webview.py history_append declines a provisional-draft',
    /== 'provisional-draft':\r?\n\s+return None/.test(fs.readFileSync(webviewPath, 'utf8')),
    true,
  );

  const failed = results.filter((r) => !r).length;
  console.log(`\nRESULT: ${failed ? `RED — ${failed} violation(s)` : 'GREEN — the transcript carries only the worker-closed line'}`);
  return failed ? 1 : 0;
}

process.exit(main());
