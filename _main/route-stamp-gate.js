'use strict';

/**
 * Sotto — THE ROUTE-STAMP GATE (owner order 2026-10-06).
 *
 *   "o live nvidia do painel do sotto e' pra ser o nvidia funcionando, enquanto
 *    o historico nao e' pra ser NUNCA o historico do live nvidia. e' pra ser do
 *    parakeet redux. e eu to vendo q nao ta desse jeito"
 *
 * THE GAP IT CLOSES (named by lane SottoPanelLiveHistory, `falta-no-gate` +
 * `gate-melhor`): `_main/historico-vs-redux-probe.js` tests the STORE and the
 * TEXT of `panel.js`, but nothing asserted WHERE the route comes from — so a
 * future `routeFor` whose else-half returns `'final'` keeps every fixture arm
 * GREEN (the fixture's `final:false` events still stamp `provisional-draft`)
 * and silently re-merges the two fields, exactly the defect the owner reported.
 *
 * WHAT IT RUNS: the REAL engine (`app/panel/caption-formulation.js`) and the
 * REAL store (`app/panel/history-store.js`), on the REAL recorded stream
 * (`_main/_route-stream-long.jsonl`), in disposable roots under
 * `history-verify/`. Nothing is executed in the DOM and no window is opened.
 *
 *   node _main/route-stamp-gate.js
 *
 *   # the RED half, as its own run and its own exit code, on a COPY:
 *   node _main/route-stamp-gate.js --emit-mutant _main/_route-stamp-red-copy.js
 *   node _main/route-stamp-gate.js --engine _main/_route-stamp-red-copy.js     # rc 1
 *
 * Exit codes: 0 the gate holds, 1 THE GATE IS RED, 2 setup error. Both colours
 * are produced by the SAME command: the green is the live engine, the red is a
 * COPY of the engine mutated in `_main/` and deleted after the run. The live
 * file is only ever READ.
 *
 * THE ONE ARM, AND ITS TWO CONTROLS. The arm is G3:
 *
 *   "a stream that stamps NO `final` key puts ZERO lines on disk at the
 *    worst-case flush cadence (a panel `status-change` after EVERY event)"
 *
 * G3 is only worth having if it can go RED, so the gate evaluates the SAME
 * predicate against two mutations of the SAME file, built from the file itself
 * (never from git — the cure is uncommitted, so `git show HEAD:` is another
 * tree):
 *
 *   G3-live    — the shipped engine      -> disk 0        (must PASS)
 *   G3-defect  — `const route = null`    -> disk == all   (must FAIL: the two
 *                fields AGREE, every live commit is in the history — the defect)
 *   G3-mutant  — `routeFor`'s else-half forced to `return 'final';`
 *                                        -> disk > 0      (must FAIL: the exact
 *                future regression, and it STAYS GREEN on the fixture — which
 *                is why the fixture alone cannot carry this gate)
 *
 * THE SECOND ARM, G4, CLOSES THE `falta-no-gate` THE RECEIPT LEFT OPEN. The
 * replay arm proves the ROUTE reaches the store; it does NOT execute
 * `panel.js` (DOM-bound), so `panel.js recordHistory`'s fail-closed choke point
 * was only ever asserted by a byte-wise `includes()`, which a panel that
 * regains the pre-cure `(meta && meta.route) || 'final'` default could defeat —
 * and the cure's OWN comment writes `(meta && meta.route) ||` and `'final'` on
 * two comment lines, so a raw `includes()` is wrong in BOTH directions. G4
 * NORMALISES the guard first (comments stripped, whitespace collapsed) and then
 * requires BOTH halves: the TEST is exactly `if (route !== 'final') return;`
 * and the route ASSIGNMENT carries no `'final'` literal. The SAME check is run
 * on a COPY of the panel with the permissive default RESTORED, so the
 * regression turns THE GATE RED instead of slipping through:
 *
 *   node _main/route-stamp-gate.js --emit-panel-mutant _main/_panel-red-copy.js
 *   node _main/route-stamp-gate.js --panel _main/_panel-red-copy.js   # rc 1, G4 RED
 */

const fs = require('node:fs');
const path = require('node:path');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const ROOTS = path.join(REPO, 'history-verify');

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

// The engine the LIVE arm is run against. Default: the repo's own file. Pointing
// it at a MUTATED COPY is how the RED half is produced as its own run and its
// own exit code — never by writing to the live file:
//
//   node _main/route-stamp-gate.js                          -> GREEN, rc 0
//   node _main/route-stamp-gate.js --engine <mutant copy>   -> RED,   rc 1
const engineUnderTest = path.resolve(flagValue('--engine') || enginePath);
const testingLive = engineUnderTest === enginePath;

// The panel the G4 CHOKE-POINT arm is checked against. Default: the repo's own
// file. Pointing it at a COPY with the pre-cure guard restored is how the RED
// half of THAT arm is produced — exactly as `--engine` does for the replay arm:
//
//   node _main/route-stamp-gate.js --emit-panel-mutant _main/_panel-red-copy.js
//   node _main/route-stamp-gate.js --panel _main/_panel-red-copy.js            # rc 1
const panelUnderTest = path.resolve(flagValue('--panel') || panelPath);
const testingLivePanel = panelUnderTest === panelPath;

// ── THE MUTATIONS, as source-level expressions of the file under test ────────
// Both are asserted PRESENT before use, so a refactor of the engine turns this
// into a SETUP ERROR (rc 2) instead of a vacuous PASS.
const ROUTE_CALL = 'const route = routeFor(reason);';
const ROUTE_DEFECT =
  "const route = null; /* GATE-DEFECT: the vacuous engine — the defect the owner saw */";
const ELSE_RE = /return PANEL_DEADLINE_REASON\.test\([\s\S]*?: 'final';/;
const ELSE_MUTANT =
  "return 'final'; /* GATE-MUTANT: the else-half forced to 'final' (the named regression) */";

// ── THE SOURCE MUTATION ──────────────────────────────────────────────────────
// `caption-formulation.js routeSourceFor` names WHICH branch decided the route:
// `'worker-stamped'`, `'panel-deadline'` or (the de-landing, announced)
// `'fallback'`. The gate REQUIRES that `src=` on every `route=final` line and
// RECOMPUTES it from the arm's own input. The mutant below forces the
// derivation to a CONSTANT, so `src=` is still written — it just LIES (always
// `'worker-stamped'`), and the fallback can no longer say it engaged. It is the
// same mutation `_main/silent-fallback-probe.js --emit-mutant` writes, asserted
// PRESENT before use so a refactor is a SETUP ERROR (rc 2), never a vacuous pass.
const SOURCE_EXPR = "return route === 'final' ? 'fallback' : 'panel-deadline';";
const SOURCE_MUTANT =
  "return 'worker-stamped'; /* GATE-MUTANT-SRC: the source forced constant */";

// The panel's own choke point, as `panel.js recordHistory` writes it, read as
// SHAPE (normalised) rather than as bytes. The cure's OWN comment
// (`panel.js:331-334`) writes `(meta && meta.route) ||` and `'final'` on two
// comment lines, so a raw `includes("|| 'final'")` matches the COMMENT — and a
// `includes("const route = meta && meta.route;")` is defeated by a single
// reformat. Normalise first, then compare the shape.
const PANEL_TEST_RE = /if\s*\(\s*route\s*!==\s*'final'\s*\)\s*(?:\{\s*return\s*;?\s*\}|return\s*;)/;
const PANEL_ASSIGN_RE = /const route = ([^;]*);/;
const PANEL_PERMISSIVE_ASSIGN =
  "const route = (meta && meta.route) || 'final'; /* GATE-MUTANT-PANEL: the pre-cure guard */";

/**
 * The recorded stream: `{"type":"caption","text":…,"final":true|false,…}`.
 *
 * `final` is carried as it ARRIVES — including `undefined` when the key is
 * absent. Coercing it to `row.final === true` (as the house probe does) would
 * erase the very case this gate exists for: "the worker stamps no route".
 */
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
 * A COPY of the engine with ONE expression replaced, written into `_main/` and
 * required from there. The live file is never opened for writing.
 */
function engineCopy(name, replace) {
  const src = fs.readFileSync(enginePath, 'utf8');
  const { text, bit, matches } = replace(src);
  if (!bit) return { error: `${name}: the expression to replace is not in the engine` };
  const tmp = path.join(HERE, `_route-stamp-${name}-engine.js`);
  fs.writeFileSync(tmp, text, 'utf8');
  delete require.cache[tmp];
  const mod = require(tmp);
  if (!mod || typeof mod.createEngine !== 'function') {
    return { error: `${name}: the copy does not export createEngine` };
  }
  return { mod, tmp, matches, changed: text !== src };
}

function withRouteCallDefect(src) {
  const matches = src.split(ROUTE_CALL).length - 1;
  if (matches !== 1) return { text: src, bit: false, matches };
  return { text: src.replace(ROUTE_CALL, ROUTE_DEFECT), bit: true, matches };
}

function withElseMutant(src) {
  const matches = src.match(new RegExp(ELSE_RE.source, 'g')) || [];
  if (matches.length !== 1) return { text: src, bit: false, matches: matches.length };
  return { text: src.replace(ELSE_RE, ELSE_MUTANT), bit: true, matches: 1 };
}

/**
 * `routeSourceFor`'s derivation forced to a CONSTANT — the input the new `src=`
 * arm must go RED on. Asserted to appear EXACTLY once, so a refactor of
 * `routeSourceFor` is a SETUP ERROR rather than a vacuous pass.
 */
function withSourceMutant(src) {
  const matches = src.split(SOURCE_EXPR).length - 1;
  if (matches !== 1) return { text: src, bit: false, matches };
  return { text: src.replace(SOURCE_EXPR, SOURCE_MUTANT), bit: true, matches: 1 };
}

/**
 * The panel source with the guard's ASSIGNMENT replaced by the pre-cure
 * permissive one — the exact input that must leave the G4 arm RED. `--emit-panel-mutant`
 * writes it into `_main/` as a COPY; the live panel is never opened for writing.
 */
function withPermissivePanel(src) {
  const matches = src.match(new RegExp(PANEL_ASSIGN_RE.source, 'g')) || [];
  if (matches.length !== 1) return { text: src, bit: false, matches: matches.length };
  return { text: src.replace(PANEL_ASSIGN_RE, PANEL_PERMISSIVE_ASSIGN), bit: true, matches: 1 };
}

/**
 * The panel's choke point, decided from its SOURCE (it is DOM-bound and is
 * never executed). Normalise FIRST — strip `//`-to-EOL comments, collapse ALL
 * whitespace to single spaces — so the guard is compared by SHAPE and not by
 * byte layout; otherwise the cure's own comment (`panel.js:331-334`, which
 * writes `(meta && meta.route) ||` and `'final'` on two comment lines) would
 * match a raw `includes("|| 'final'")` and redden a fail-closed panel.
 *
 * FAIL-CLOSED requires BOTH halves:
 *   (a) the guard TEST matches `PANEL_TEST_RE` — `if (route !== 'final')`
 *       whose body is `return;`, bare or wrapped in `{ }` (a raw `includes()`
 *       here turned a brace reformat into a FALSE RED), and
 *   (b) the route ASSIGNMENT carries no `'final'` literal — the shipped
 *       `meta && meta.route` has none; the pre-cure `(meta && meta.route) ||
 *       'final'` has one. (Requiring the `'final'` literal to be ABSENT, rather
 *       than merely `|| 'final'`, also catches `const route = 'final';`.)
 * A panel whose choke point cannot be READ — assignment absent or ambiguous —
 * is reported NOT fail-closed: an unreadable guard is a RED, never a pass.
 */
function panelGuardVerdict(src) {
  const n = src.split(/\r?\n/).map((l) => l.replace(/\/\/.*$/, '')).join('\n')
    .replace(/\s+/g, ' ').trim();
  const assigns = n.match(new RegExp(PANEL_ASSIGN_RE.source, 'g')) || [];
  const m = PANEL_ASSIGN_RE.exec(n);
  const assignment = assigns.length === 1 && m ? m[1] : null;
  const test = PANEL_TEST_RE.test(n);
  const failClosed = assigns.length === 1 && test && !/['"]final['"]/.test(assignment);
  return { assignment, test, failClosed };
}

/**
 * `route=` on every line of every `.md` under `root`, as a histogram — plus the
 * per-line `src=` and the raw tail, so the gate can REQUIRE the source the new
 * `routeSourceFor` writes (M9). The `route` capture is kept BYTE-IDENTICAL to
 * the earlier version (`/\s*<!--\s*(route=\S+)/`, route token FIRST in the
 * tail) so no existing arm's `found` histogram can move; `src=` is parsed out
 * of the same `<!-- … -->` tail separately.
 */
function routesOnDisk(root) {
  const found = {};
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
        const routeTok = /\s*<!--\s*(route=\S+)/.exec(m[2]);
        const route = routeTok ? routeTok[1].slice('route='.length) : null;
        const tailM = /\s*<!--\s*(.*?)\s*-->\s*$/.exec(m[2]);
        const kv = {};
        if (tailM) for (const tok of tailM[1].split(/\s+/)) {
          const eq = tok.indexOf('=');
          if (eq > 0) kv[tok.slice(0, eq)] = tok.slice(eq + 1);
        }
        found[route] = (found[route] || 0) + 1;
        lines.push({ route, src: kv.src || null, tail: tailM ? tailM[1] : null });
      }
    }
  }
  return { found, count: Object.values(found).reduce((a, b) => a + b, 0), lines };
}

/**
 * Replay `events` through `engineMod` and hand every commit to the REAL store
 * under `root`. `panelAccepts` is `panel.js recordHistory`'s choke point as the
 * arm under test writes it. `flushEvery` fires the panel's worst-case
 * `status-change` flush after EVERY event.
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

  return {
    commits,
    handed: commits.reduce((a, c) => ((a[c.route] = (a[c.route] || 0) + 1), a), {}),
    panelAccepted: accepted.length,
    disk: routesOnDisk(root),
  };
}

/** The ONE arm, as a function of one replay result: NO `final` -> NOTHING on disk. */
function armNoFinalWritesNothing(r) {
  return r.disk.count === 0;
}

/**
 * THE SOURCE, RECOMPUTED BY THE GATE ITSELF — never read back from the engine.
 *
 * From today the gate requires `src=` on every `route=final` line, and it does
 * not take the value on trust: `expectedSrc` is the ONLY source that arm's own
 * INPUT can legitimately produce, so any line whose `src=` differs — INCLUDING a
 * line with NO `src=` at all (`null !== expectedSrc`) — is a REFUSAL.
 *
 *   a stream where NO event carried a `final` stamp can reach `route=final` ONLY
 *   through `routeFor`'s else-half, so `src=fallback` is the ONLY honest value;
 *   a `worker-stamped` there is exactly the lie
 *   `silent-fallback-probe.js --emit-mutant` manufactures;
 *
 *   a stream whose `final` votes are present (the fixture) reaches `route=final`
 *   only from a stamped buffer, so `src=worker-stamped` is the only honest value.
 *
 * Returns the mismatching `src=` values (`null` for an absent field), so an
 * empty array is the PASS and a non-empty one names the offending lines.
 */
function srcMismatches(r, expectedSrc) {
  return r.disk.lines
    .filter((l) => l.route === 'final')
    .filter((l) => l.src !== expectedSrc)
    .map((l) => l.src);
}

function main() {
  if (!fs.existsSync(enginePath) || !fs.existsSync(storePath) || !fs.existsSync(panelUnderTest)) {
    console.log('SETUP ERROR: engine, store or panel missing');
    return 2;
  }
  if (!fs.existsSync(streamPath)) {
    console.log(`SETUP ERROR: no stream at ${streamPath}`);
    return 2;
  }
  const events = readStream(streamPath);
  if (!events.length) {
    console.log(`SETUP ERROR: ${streamPath} carries no caption event`);
    return 2;
  }

  // THE PANEL CHOKE POINT, read from SOURCE (never executed — DOM-bound) and
  // compared by SHAPE, not by bytes. G4 asserts the guard is fail-closed; the
  // CONTROL asserts the SAME check on a panel with the per-cure `|| 'final'`
  // default RESTORED is RED. The mutant is built from the LIVE panel so it
  // stays a control for the CHECK, independent of which panel is under test.
  const panelSrc = fs.readFileSync(panelUnderTest, 'utf8');
  const livePanelSrc = fs.readFileSync(panelPath, 'utf8');
  const panelVerdict = panelGuardVerdict(panelSrc);
  const panelMutant = withPermissivePanel(livePanelSrc);

  // `--emit-panel-mutant <path>`: write the permissive panel COPY the G4 RED
  // half is run against. Its own exit code, never a write to the live panel.
  const emitPanelPath = flagValue('--emit-panel-mutant');
  if (emitPanelPath) {
    const out = path.resolve(emitPanelPath);
    if (out === panelPath) {
      console.log('SETUP ERROR: --emit-panel-mutant refuses to write over the live panel');
      return 2;
    }
    if (!panelMutant.bit) {
      console.log('SETUP ERROR: the guard assignment is not a single `const route = …;` in panel.js');
      return 2;
    }
    fs.writeFileSync(out, panelMutant.text, 'utf8');
    console.log(`WROTE ${out}`);
    console.log("  the panel `|| 'final'` pre-cure COPY (the live panel is untouched)");
    console.log(`  run it RED:  node _main/route-stamp-gate.js --panel ${path.relative(REPO, out)}`);
    return 0;
  }

  const live = require(engineUnderTest);
  const defect = engineCopy('defect', withRouteCallDefect);
  const mutant = engineCopy('mutant', withElseMutant);
  const srcMutant = engineCopy('srcmutant', withSourceMutant);
  for (const [name, made] of [['defect', defect], ['mutant', mutant], ['srcmutant', srcMutant]]) {
    if (made.error) {
      console.log(`SETUP ERROR: ${made.error}`);
      return 2;
    }
  }

  // `--emit-mutant <path>`: write the mutant COPY the control arms use, so an
  // operator can run the gate against it and get the RED as its own exit code.
  // It writes a NEW file and never the live engine.
  const emitPath = flagValue('--emit-mutant');
  if (emitPath) {
    const out = path.resolve(emitPath);
    if (out === enginePath) {
      console.log('SETUP ERROR: --emit-mutant refuses to write over the live engine');
      return 2;
    }
    fs.copyFileSync(mutant.tmp, out);
    fs.rmSync(defect.tmp, { force: true });
    fs.rmSync(mutant.tmp, { force: true });
    fs.rmSync(srcMutant.tmp, { force: true });
    console.log(`WROTE ${out}`);
    console.log('  the `routeFor`-else mutant COPY (the live engine is untouched)');
    console.log(`  run it RED:  node _main/route-stamp-gate.js --engine ${path.relative(REPO, out)}`);
    return 0;
  }

  const panelClosed = (c) => c.route === 'final';
  const panelPermissive = (c) => (c.route || 'final') === 'final';

  // THE SAME ARM, three engines. The stream is the fixture with the `final` key
  // REMOVED — the pipeline as it stands, where nothing stamps a route.
  const noFinal = events.map((e) => ({ ...e, final: undefined }));
  const armLive = run(live, path.join(ROOTS, 'route-stamp-arm-live'), noFinal, panelClosed, true);
  const armDefect = run(defect.mod, path.join(ROOTS, 'route-stamp-arm-defect'), noFinal, panelPermissive, true);
  const armMutant = run(mutant.mod, path.join(ROOTS, 'route-stamp-arm-mutant'), noFinal, panelClosed, true);

  // The fixture, live and mutated: the reason the fixture ALONE is not a gate.
  const fixLive = run(live, path.join(ROOTS, 'route-stamp-fix-live'), events, panelClosed, true);
  const fixMutant = run(mutant.mod, path.join(ROOTS, 'route-stamp-fix-mutant'), events, panelClosed, true);

  // THE FALLBACK CADENCE — the SAME no-stamp stream, at the NATURAL cadence (no
  // per-event flush), which is the live pipeline as it stands: the audio's own
  // boundaries and the terminal flush close the lines, and every `route=final`
  // among them is manufactured by `routeFor`'s else-half. This is the ONLY arm
  // where `src=fallback` is legitimate, so it is the arm the new `src=`
  // requirement is proven ON (the all-status-change arm above hands NOTHING to
  // the panel, so a `src=` requirement there would be vacuous).
  const armFbLive = run(live, path.join(ROOTS, 'route-stamp-arm-fb-live'), noFinal, panelClosed, false);
  const armFbMutant = run(srcMutant.mod, path.join(ROOTS, 'route-stamp-arm-fb-mutant'), noFinal, panelClosed, false);

  // The fixture under the SOURCE mutant: `routeSourceFor` is a constant there
  // too, but on the fixture the honest value IS the constant, so this run must
  // stay GREEN — the check refuses the LIE, not the field.
  const fixSrcMutant = run(srcMutant.mod, path.join(ROOTS, 'route-stamp-fix-srcmutant'), events, panelClosed, true);

  // ORIGIN, proven rather than asserted: the route follows `meta.final`, and the
  // worker's vote WINS over the panel's own deadline reason in BOTH directions.
  const MINI = [
    { ev: { text: 'alpha beta', start: 0, end: 1, final: false }, flush: 'status-change', want: 'provisional-draft' },
    { ev: { text: 'gamma delta', start: 1.5, end: 2.5, final: false }, flush: 'stream-end', want: 'provisional-draft' },
    { ev: { text: 'epsilon zeta', start: 3, end: 4, final: true }, flush: 'status-change', want: 'final' },
  ];
  const originCommits = [];
  const originEngine = live.createEngine({
    onCommit: (text, reason, meta) => originCommits.push((meta && meta.route) || null),
    onProvisional: () => {},
  });
  for (const m of MINI) {
    originEngine.ingest(m.ev.text, { start: m.ev.start, end: m.ev.end, final: m.ev.final });
    originEngine.flush(m.flush);
  }
  const originWant = MINI.map((m) => m.want);

  fs.rmSync(defect.tmp, { force: true });
  fs.rmSync(mutant.tmp, { force: true });
  fs.rmSync(srcMutant.tmp, { force: true });

  // ── REPORT ────────────────────────────────────────────────────────────────
  console.log(`stream    : ${path.relative(REPO, streamPath)} — ${events.length} event(s)` +
    ` (final:true ${events.filter((e) => e.final === true).length},` +
    ` final:false ${events.filter((e) => e.final === false).length})`);
  console.log(`engine    : ${path.relative(REPO, engineUnderTest)}` +
    (testingLive ? '' : `   === ENGINE UNDER TEST: NOT the live file (${path.relative(REPO, enginePath)}) — RED is expected ===`));
  console.log(`store     : ${path.relative(REPO, storePath)}`);
  console.log(`panel     : ${path.relative(REPO, panelUnderTest)}` +
    `   choke(assignment=${JSON.stringify(panelVerdict.assignment)} test=${panelVerdict.test} fail-closed=${panelVerdict.failClosed})` +
    (testingLivePanel ? '' : `   === PANEL UNDER TEST: NOT the live file (${path.relative(REPO, panelPath)}) — its arm is expected RED ===`));

  const colour = (r) => `${r.commits.length} commit(s) ${JSON.stringify(r.handed)},` +
    ` panel accepted ${r.panelAccepted}, on disk ${r.disk.count} — ${JSON.stringify(r.disk.found)}`;

  console.log('\n--- THE ARM: a stream with NO `final` key, worst-case `status-change` flush after EVERY event ---');
  console.log(`  LIVE   (shipped engine)                    : ${colour(armLive)}`);
  console.log(`  DEFECT (const route = null — the owner saw): ${colour(armDefect)}`);
  console.log(`  MUTANT (routeFor else -> 'final')          : ${colour(armMutant)}`);

  console.log('\n--- the FIXTURE (final:true/false present), same flush cadence ---');
  console.log(`  LIVE   : ${colour(fixLive)}`);
  console.log(`  MUTANT : ${colour(fixMutant)}`);

  console.log('\n--- THE FALLBACK CADENCE: the SAME no-`final` stream at the NATURAL cadence — the else-half manufactures every `final` ---');
  console.log(`  LIVE    (shipped engine)                   : ${colour(armFbLive)} — routes ${JSON.stringify(armFbLive.disk.found)}`);
  console.log(`  MUTANT  (routeSourceFor -> constant)       : ${colour(armFbMutant)}`);

  const arms = [];
  function arm(name, real, want) {
    const ok = JSON.stringify(real) === JSON.stringify(want);
    arms.push(ok);
    console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}`);
    console.log(`       real = ${JSON.stringify(real)}`);
    console.log(`       want = ${JSON.stringify(want)}`);
    return ok;
  }

  console.log('\n--- the gate, both colours of the SAME command ---');
  arm('G1 ORIGIN: the engine stamps the route from `meta.final`, and the worker\'s vote beats the panel deadline',
    originCommits, originWant);
  arm('G2 FIXTURE: the history carries ONLY the worker-closed line',
    { onDisk: fixLive.disk.found, provisionalHanded: fixLive.handed['provisional-draft'] || 0 },
    { onDisk: { final: 130 }, provisionalHanded: 1091 });
  const g3Live = arm('G3 THE ARM: a stream with NO `final` key writes NOTHING on disk',
    armNoFinalWritesNothing(armLive), true);
  arm('CONTROL: the SAME arm on the defect (`route = null`) is RED — the two sides AGREE',
    armNoFinalWritesNothing(armDefect), false);
  arm('CONTROL: the SAME arm on the mutant (`routeFor` else -> \'final\') is RED — the named regression',
    armNoFinalWritesNothing(armMutant), false);
  arm('CONTROL: that mutant STAYS GREEN on the fixture — why the fixture alone is not a gate',
    fixMutant.disk.found, { final: 130 });
  arm('CONTROL: the defect merges the two fields (every commit is a history line)',
    armDefect.disk.count === armDefect.commits.length && armDefect.disk.count > 0, true);
  arm('CONTROL: the gate is not vacuous — BOTH mutations bit the engine source, once each',
    { defectChanged: defect.changed, defectMatches: defect.matches,
      mutantChanged: mutant.changed, mutantMatches: mutant.matches },
    { defectChanged: true, defectMatches: 1, mutantChanged: true, mutantMatches: 1 });

  // G4 — the panel's choke point, in the SAME command and RED-able the same way.
  // A direct regression of the pre-cure `|| 'final'` turns the arm RED instead
  // of slipping through the byte-wise `includes()` the earlier version used.
  const g4Panel = arm('G4 PANEL CHOKE: `panel.js recordHistory` is FAIL-CLOSED (guard normalised, not byte-matched)',
    panelVerdict.failClosed, true);
  arm("CONTROL: the SAME panel check on the pre-cure guard (`|| 'final'` restored) is RED — the named regression",
    panelMutant.bit ? panelGuardVerdict(panelMutant.text).failClosed : null, false);
  arm('CONTROL: the panel mutant bit the panel source exactly once (the check is not vacuous)',
    { panelChanged: panelMutant.bit && panelMutant.text !== livePanelSrc, panelMatches: panelMutant.matches },
    { panelChanged: true, panelMatches: 1 });

  // G5 — THE SOURCE IS REQUIRED, and RECOMPUTED by the gate. Every `route=final`
  // line must carry the `src=` that arm's own input can legitimately produce: the
  // fallback arm (no stamp anywhere) may only read `fallback`; the fixture may
  // only read `worker-stamped`. A line with NO `src=` (a plumbing regression) or
  // a WRONG one (the constant-derivation mutant) is a REFUSAL. The probe
  // `_main/silent-fallback-probe.js` is the same check as a standalone file; it
  // is also run by `_main/_cura-oracle-suite.py`.
  const g5Src = arm('G5 SRC REQUIRED: every `route=final` line names the `src=` the SAME command RECOMPUTES',
    { fallbackArm: srcMismatches(armFbLive, 'fallback'), fixture: srcMismatches(fixLive, 'worker-stamped') },
    { fallbackArm: [], fixture: [] });
  arm('CONTROL: the fallback arm at the natural cadence DID produce `route=final` lines (the check is not vacuous)',
    armFbLive.disk.found.final > 0, true);
  arm('CONTROL: the SAME `src=` check on the constant-derivation mutant (`routeSourceFor` forced constant) is RED — the fallback that cannot say it engaged',
    srcMismatches(armFbMutant, 'fallback').length > 0, true);
  arm('CONTROL: that mutant is GREEN on the fixture — the check refuses only the LIE, not the field',
    srcMismatches(fixSrcMutant, 'worker-stamped'), []);
  arm('CONTROL: the `src=` mutant bit the engine source exactly once (the check is not vacuous)',
    { srcChanged: srcMutant.changed, srcMatches: srcMutant.matches },
    { srcChanged: true, srcMatches: 1 });
  // The refusal is not only "the WRONG src": a `route=final` line with NO `src=`
  // at all (a plumbing regression — e.g. this replay dropping `routeSource` on
  // the way to the store) is named by the SAME recomputation, `null !== expected`.
  arm('CONTROL: the recomputation REFUSES a `route=final` line with NO `src=` (and ignores a provisional line)',
    srcMismatches({ disk: { lines: [
      { route: 'final', src: null },
      { route: 'final', src: 'worker-stamped' },
      { route: 'provisional-draft', src: null },
    ] } }, 'fallback'),
    [null, 'worker-stamped']);

  const ok = arms.every(Boolean) && g3Live && g4Panel && g5Src;
  console.log(`\nGATE: ${ok ? 'PASS' : 'RED'} — ${arms.filter(Boolean).length}/${arms.length} arm(s)` +
    (ok ? ' (live GREEN, and every arm RED on its own mutation)' : ''));
  return ok ? 0 : 1;
}

process.exit(main());
