'use strict';

/**
 * Sotto — THE SILENT-FALLBACK PROBE (owner order 2026-10-07).
 *
 *   "faz o fallback ser DISTINGUIVEL ... um fallback que nao sabe dizer que
 *    entrou e' a mesma classe de defeito que um gate que nao sabe dizer nao"
 *
 * THE DEFECT THIS EXISTS FOR. `app/panel/caption-formulation.js routeFor`
 * returns `'final'` when the worker stamped NOTHING (its else-half). That is
 * DELIBERATE and must stay — the live worker is the pre-cure snapshot whose
 * `_event` never stamps `final`, so deleting the wrap would blank the owner's
 * transcript. But it made a DE-LANDING invisible: when the worker's M2 contract
 * (`line_events` / `take_closed` / `_event(final=)`) was de-landed, the renderer
 * kept emitting `route=final` from this very default and the loss went unnoticed
 * for a day (lane SottoCaptionLines, `_main/receipt-20261007-caption-lines.md`;
 * P1 ticket `4fb5b25380cbc8269977e22e`).
 *
 * THE CURE, and what this probe PINS. `routeSourceFor()` makes the commit carry
 * WHICH branch decided the route — `'worker-stamped'`, `'panel-deadline'` or
 * `'fallback'` — and both stores write it on the line as `src=`. So a line that
 * reached the transcript ONLY because the else-half manufactured it now reads
 * `route=final src=fallback`, and a genuine worker vote reads
 * `route=final src=worker-stamped`: SAME route, DIFFERENT observable.
 *
 * WHAT IT RUNS: the REAL engine (`app/panel/caption-formulation.js`) and the
 * REAL store (`app/panel/history-store.js`), on the REAL recorded stream
 * (`_main/_route-stream-long.jsonl`), in disposable roots under `history-verify/`.
 * Nothing is executed in the DOM and no window is opened (pure file reads + one
 * store under a temp root).
 *
 *   node _main/silent-fallback-probe.js
 *
 *   # the RED half, as its own run and its own exit code, on a COPY:
 *   node _main/silent-fallback-probe.js --emit-mutant _main/_sf-red-copy.js
 *   node _main/silent-fallback-probe.js --engine _main/_sf-red-copy.js     # rc 1
 *
 * Exit codes: 0 the distinction holds, 1 THE PROBE IS RED, 2 setup error.
 *
 * THE ARMS, non-vacuous by construction:
 *
 *   ARM A   a worker-STAMPED final  -> route 'final' AND routeSource
 *           'worker-stamped' on disk (`src=worker-stamped`).
 *   ARM B   the SAME stream with NO worker stamp -> route 'final' (the wrapped
 *           result, unchanged) AND routeSource 'fallback' (`src=fallback`).
 *   NON-VACUITY: the two arms' disk ROUTES are IDENTICAL ({final:N}) and their
 *           SOURCES DIFFER. If both read identically the change proved nothing.
 *   COMPAT  the OLD `route=… start=…` readers still capture route and start
 *           (src= is appended AFTER start=).
 *   RED     `--engine <copy>` with the source forced to a constant -> ARM A and
 *           ARM B read IDENTICALLY (both 'worker-stamped') -> NON-VACUITY fails.
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
const storePath = path.join(REPO, 'app', 'panel', 'history-store.js');

// The engine the arms are run against. Default: the repo's own file. A MUTATED
// COPY is how the RED half is produced — the live file is only ever READ.
const engineUnderTest = path.resolve(flagValue('--engine') || enginePath);
const testingLive = engineUnderTest === enginePath;

// The one expression `routeSourceFor` uses to NAME the fallback. Replacing it
// with a constant removes the distinction: every source reads 'worker-stamped'.
// Asserted PRESENT before use, so a refactor turns this into a SETUP ERROR (2)
// instead of a vacuous PASS.
const SOURCE_EXPR = "return route === 'final' ? 'fallback' : 'panel-deadline';";
const SOURCE_MUTANT =
  "return 'worker-stamped'; /* PROBE-MUTANT: the fallback no longer says it engaged */";

function readStream(file) {
  const out = [];
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const t = line.trim();
    if (!t) continue;
    try {
      const o = JSON.parse(t);
      if (o && o.type === 'caption' && o.text !== undefined) {
        out.push({
          text: String(o.text),
          start: o.start ?? null,
          end: o.end ?? null,
          final: o.final,
        });
      }
    } catch { /* not a caption event */ }
  }
  return out;
}

/**
 * `route=` and `src=` on every line of every `.md` under `root`. `start` is
 * captured with the ORIGINAL shape the older probes use — `src=` sits AFTER it
 * precisely so this capture is unchanged (the COMPAT arm).
 */
function routesOnDisk(root) {
  const found = { route: {}, src: {} };
  const lines = [];
  if (!fs.existsSync(root)) return { found, count: 0, lines };
  for (const day of fs.readdirSync(root)) {
    const folder = path.join(root, day);
    if (!fs.statSync(folder).isDirectory()) continue;
    for (const name of fs.readdirSync(folder)) {
      if (!name.endsWith('.md')) continue;
      for (const l of fs.readFileSync(path.join(folder, name), 'utf8').split(/\r?\n/)) {
        const m = /^-\s+\[(\d\d:\d\d:\d\d)\]\s+(.*)$/.exec(l);
        if (!m) continue;
        const tail = /\s*<!--\s*(.*?)\s*-->\s*$/.exec(m[2]);
        const kv = {};
        if (tail) for (const tok of tail[1].split(/\s+/)) {
          const eq = tok.indexOf('=');
          if (eq > 0) kv[tok.slice(0, eq)] = tok.slice(eq + 1);
        }
        const route = kv.route || null;
        const src = kv.src || null;
        found.route[route] = (found.route[route] || 0) + 1;
        found.src[src] = (found.src[src] || 0) + 1;
        lines.push({ text: m[2], route, src, start: kv.start || null, tail: tail ? tail[1] : null });
      }
    }
  }
  return {
    found,
    count: Object.values(found.route).reduce((a, b) => a + b, 0),
    lines,
  };
}

/**
 * Replay `events` through `engineMod` and hand every accepted commit to the
 * REAL store under `root`. `panelAccepts` is `panel.js recordHistory`'s choke
 * point as the shipped panel writes it (`route === 'final'`). `flushEvery`
 * fires the panel's worst-case `status-change` flush after EVERY event.
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
      routeSource: (meta && meta.routeSource) || null,
      start: meta && typeof meta.start === 'number' ? meta.start : null,
    }),
    onProvisional: () => {},
  });

  for (const c of events) {
    engine.ingest(c.text, { start: c.start, end: c.end, final: c.final });
    if (flushEvery !== false) engine.flush('status-change');
  }
  engine.flush('stream-end');

  const accepted = commits.filter(panelAccepts);
  for (const c of accepted) {
    store.append(c.text, {
      source: 'live',
      route: c.route,
      routeSource: c.routeSource,
      start: c.start,
      reason: c.reason,
    });
  }

  // The source of every commit whose ROUTE is 'final' — the only route that can
  // reach the transcript (panel guard + store guard).
  const finalSources = Array.from(new Set(
    commits.filter((c) => c.route === 'final').map((c) => c.routeSource),
  )).sort();

  return { commits, panelAccepted: accepted.length, finalSources, disk: routesOnDisk(root) };
}

function main() {
  // --emit-mutant writes a COPY of the engine with the distinction removed and
  // prints its path, then exits. It is the input the RED half is run against.
  const emitMutant = flagValue('--emit-mutant');
  if (emitMutant) {
    const src = fs.readFileSync(enginePath, 'utf8');
    const n = src.split(SOURCE_EXPR).length - 1;
    if (n !== 1) {
      console.log(`SETUP ERROR: the source expression appears ${n} time(s), want 1:\n  ${SOURCE_EXPR}`);
      return 2;
    }
    const out = path.resolve(emitMutant);
    fs.writeFileSync(out, src.replace(SOURCE_EXPR, SOURCE_MUTANT), 'utf8');
    console.log(`wrote mutant engine: ${path.relative(REPO, out)}`);
    return 0;
  }

  if (!fs.existsSync(enginePath) || !fs.existsSync(storePath)) {
    console.log('SETUP ERROR: engine or store missing');
    return 2;
  }
  if (!fs.existsSync(engineUnderTest)) {
    console.log(`SETUP ERROR: no engine at ${engineUnderTest}`);
    return 2;
  }
  if (!fs.existsSync(streamPath)) {
    console.log(`SETUP ERROR: no stream at ${streamPath}`);
    return 2;
  }
  const src = fs.readFileSync(enginePath, 'utf8');
  if (!src.includes(SOURCE_EXPR)) {
    console.log(`SETUP ERROR: the source expression is not in caption-formulation.js:\n  ${SOURCE_EXPR}`);
    return 2;
  }

  const events = readStream(streamPath);
  if (!events.length) {
    console.log(`SETUP ERROR: ${streamPath} carries no caption event`);
    return 2;
  }
  const engineMod = require(engineUnderTest);

  // ARM A — the recorded stream WITH its worker stamps. Worst-case cadence: a
  // `status-change` flush after EVERY event, so only a worker-stamped final can
  // survive to the transcript; a stamp-less line would be a `provisional-draft`.
  const armA = run(
    engineMod,
    path.resolve(flagValue('--root-a') || path.join(REPO, 'history-verify', 'sf-arm-a')),
    events,
    (c) => c.route === 'final',
    true,
  );
  // ARM B — the SAME stream with NO worker stamp at all (the live pipeline as
  // it stands), natural cadence: the audio's own boundaries and the terminal
  // flush close the lines, and every one of them is manufactured by the
  // else-half. This is the de-landing the old tree could not name.
  const armB = run(
    engineMod,
    path.resolve(flagValue('--root-b') || path.join(REPO, 'history-verify', 'sf-arm-b')),
    events.map((e) => ({ ...e, final: undefined })),
    (c) => c.route === 'final',
    false,
  );

  const firstTail = (r) => (r.disk.lines[0] ? r.disk.lines[0].tail : '(no line)');
  console.log(`stream    : ${path.relative(REPO, streamPath)} — ${events.length} event(s)` +
    ` (final:true ${events.filter((e) => e.final === true).length},` +
    ` final:false ${events.filter((e) => e.final === false).length})`);
  console.log(`engine    : ${path.relative(REPO, engineUnderTest)}${testingLive ? '' : '   (MUTANT COPY)'}`);
  console.log(`\nARM A (worker-stamped final)`);
  console.log(`  LIVE    : final-route commits carry routeSource = ${JSON.stringify(armA.finalSources)}`);
  console.log(`  HISTORY : ${armA.disk.count} line(s) on disk — routes ${JSON.stringify(armA.disk.found.route)}` +
    ` — sources ${JSON.stringify(armA.disk.found.src)}`);
  console.log(`  LINE A  : <!-- ${firstTail(armA)} -->`);
  console.log(`\nARM B (NO worker stamp — the wrapped result)`);
  console.log(`  LIVE    : final-route commits carry routeSource = ${JSON.stringify(armB.finalSources)}`);
  console.log(`  HISTORY : ${armB.disk.count} line(s) on disk — routes ${JSON.stringify(armB.disk.found.route)}` +
    ` — sources ${JSON.stringify(armB.disk.found.src)}`);
  console.log(`  LINE B  : <!-- ${firstTail(armB)} -->`);

  const arms = [];
  function arm(name, real, want) {
    const ok = JSON.stringify(real) === JSON.stringify(want);
    arms.push(ok);
    console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
    console.log(`       real = ${JSON.stringify(real)}`);
    console.log(`       want = ${JSON.stringify(want)}`);
  }

  console.log('\n--- the control pair, both colours of the SAME probe ---');
  // ARM A: the renderer STILL emits 'final', and the field says STAMPED.
  arm('ARM A: a worker-stamped final still emits route=final',
      armA.finalSources.length === 1 && armA.disk.count > 0, true);
  arm('ARM A: the new field says it was STAMPED (worker-stamped) on disk',
      Object.keys(armA.disk.found.src), ['worker-stamped']);
  // ARM B: the renderer emits its WRAPPED result, and the field says FALLBACK.
  arm('ARM B: with NO worker stamp the renderer still emits route=final (the wrap)',
      armB.disk.count > 0, true);
  arm('ARM B: the new field says the FALLBACK engaged (fallback) on disk',
      Object.keys(armB.disk.found.src), ['fallback']);
  // NON-VACUITY: same ROUTE set, DIFFERENT SOURCE set. (The line COUNTS differ
  // legitimately — the stamp-less arm closes more lines at the natural cadence
  // — so the claim is about which VALUES each field takes, not how many.)
  arm('NON-VACUITY: the two arms carry the SAME route value(s)',
      Object.keys(armA.disk.found.route).sort(), Object.keys(armB.disk.found.route).sort());
  arm('NON-VACUITY: and DIFFERENT sources (the change proved something)',
      Object.keys(armA.disk.found.src).join() === Object.keys(armB.disk.found.src).join(), false);
  // COMPAT: the OLD `route=… start=…` capture is untouched.
  arm('COMPAT: the old route=… start=… capture still yields route final and a start',
      (() => {
        const l = armA.disk.lines[0] || {};
        const t = /\s*<!--\s*(route=\S+)(?:\s+start=([\d.]+))?/.exec(' ' + '<!-- ' + l.tail + ' -->');
        return t ? [t[1], t[2] !== undefined] : null;
      })(),
      ['route=final', true]);

  const ok = arms.every(Boolean);
  console.log(`\nRESULT: ${ok ? 'GREEN' : 'RED'} — ${arms.filter(Boolean).length}/${arms.length} arm(s)`);
  return ok ? 0 : 1;
}

process.exit(main());
