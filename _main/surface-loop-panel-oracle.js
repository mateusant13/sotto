/* surface-loop-panel-oracle.js -- THE PAGE HALF OF THE SAME LOOP, MEASURED IN THE
 * REAL DOCUMENT.
 *
 * THE SHELL HALF IS _main/surface-loop-oracle.py: it drives the REAL
 * SottoShell.set_panel_surface through the REAL SottoHost.dispatch and proves a
 * repeated (surface, reason) is a no-op. This file closes the loop from the PAGE
 * side, in the one place the page actually lives: the shipped app/panel/panel.html
 * + panel.css + caption-float.css + the document's own script list, loaded in
 * order in jsdom against a bridge stub that behaves like the real shell does (it
 * answers a setPanelSurface ask by setting the document surface AND echoing the
 * geometry back).
 *
 * THE LOOP ITSELF, in this file, is the closed pair the audit measured:
 *
 *   page  applyFloat -> bridge.setPanelSurface('strip', 'strip-float-off')
 *   shell set_panel_surface -> exec_js(SottoSurfaces.set) + send_geometry
 *   page  onGeometry -> setSurface(geometry.surface) -> applySurface -> applyFloat
 *   -> ...
 *
 * Measured 2026-10-13: 30 647 surface applications against FIVE real hotkey
 * transitions, p99 264/s. Two page guards stand in its way, both on the path, and
 * this file says what each one does:
 *
 *   surface.js  set() fires the listeners ONLY when the name moved, and refuses
 *                a name the panel does not own.
 *   panel.js    setSurface() calls applySurface() only when the page's own answer
 *                moved -- `after !== before`.
 *
 * WHAT IS COUNTED, AND WHY IT IS THE RIGHT NUMBER. On the strip surface every
 * applySurface() run ends in exactly one page->shell ask: applySurface ->
 * applyLiveEnabled(liveEnabled, {silent:true}) -> applyFloat ->
 * bridge.setPanelSurface('strip', 'strip-float-off') (panel.js:2337-2339, gated
 * on currentSurface() === 'strip'). So the ask count IS the paint count there,
 * and it is the audit's own metric: 30 647 asks against 5 real transitions. The
 * stub counts the page's asks separately from this file's own driver calls, by
 * re-entrancy: a call made while the stub is already running is the page's.
 *
 * RE-ANCHORED 2026-10-20 (lane caption). THE ASK IS GONE, AND THAT IS THE
 * PRODUCT'S DOING, NOT A DECAY. On 2026-10-17 the caption became a NATIVE WINDOW
 * (`NativeCaptionOverlay`) and the three writes that used to resize the panel
 * were DELETED: `applyFloat` returns at its first line when the shell owns the
 * caption window (panel.js:2729) and asks the shell for NOTHING. So the
 * page->shell ask count is identically ZERO on the shipped page, and a metric
 * that is zero cannot tell the shipped page from a page whose guards are gone:
 * arm A was RED for a reason that had nothing to do with the switch.
 *
 * WHAT THE TWO GUARDS ACTUALLY PROTECT, AND WHAT IS COUNTED NOW: a REPEAT. A
 * genuine switch repaints the page; a repeat must not. The page's repaint is
 * `applySurface()`, which ends in `applyLiveEnabled()` -> `paintLiveLamps()` --
 * ONE write of `aria-label` on `#live-lamp`, which is the DOM boundary this
 * file counts (the prototype's `setAttribute` is wrapped in the harness, which
 * is an INSTRUMENT, never a product change). The ask count is KEPT, and it is
 * now the SECOND claim of arm A: the page opens NOTHING on the shell.
 *
 * ARMS
 *   A GENUINE-SWITCH a real surface switch still repaints (and asks nothing).
 *   B ECHO-STORM     200 identical geometry echoes produce no further repaint.
 *   C PAGE-REASK     the page's own re-ask for the same surface repaints nothing.
 *   D REFUSAL        an unknown name changes nothing and repaints nothing.
 *   E FIX-POINT      the closed loop, 200 rounds: one repaint in round one, none after.
 *
 * THE NEGATIVE ARM (--neg-arm) IS THE POINT OF THE FILE: app/panel is copied to a
 * scratch directory, ONE page guard is deleted from the copy, and the SAME arms
 * re-run. Two mutants, one per page guard, and BOTH are load-bearing -- MEASURED
 * after this file's metric moved (see the RE-ANCHORED note above):
 *   M1 surface.js  the `if (value !== previous)` change-guard is deleted, so a
 *                listener fires on EVERY set. MEASURED 2026-10-20: 3 of 6 arms
 *                RED -- the echo storm goes from 0 to 200 repaints, the page's own
 *                re-ask from 0 to 2 and the closed loop from 0 to 400.
 *   M2 panel.js    the `after !== before` guard in setSurface() is deleted, so the
 *                page repaints on every echo even when its own answer did not
 *                move. MEASURED 2026-10-20: 4 of 6 arms RED -- the echo storm
 *                0 -> 200, the re-ask 0 -> 1, the refusal 0 -> 1, the closed
 *                loop 0 -> 200. The claim that surface.js already covered this
 *                one was WRONG and is retracted here: setSurface() calls
 *                applySurface() itself, so the guard it lost is the one that
 *                stopped the loop on the echo path. Both halves of the page guard
 *                are therefore gated.
 *
 * AND THE RUNAWAY IS A NUMBER, NOT A HANG. The stub carries a depth cap and a
 * breaker, and every arm asserts `capped === 0`, so the shipped page is GREEN and
 * a mutant is RED with the runaway counted. NOTE WHAT CHANGED ON 2026-10-20: the
 * runaway is no longer a BRIDGE RECURSION -- the page asks the shell for nothing
 * any more (the caption window belongs to the shell), so `capped` stays 0 in every
 * arm, mutant or not, and the number that goes wrong is the REPAINT COUNT
 * (0 -> 200, measured). The cap is kept because it still bounds the one thing
 * that could still recurse: a page that asked the shell again.
 *
 *   node _main/surface-loop-panel-oracle.js            expect VERDICT: PASS
 *   node _main/surface-loop-panel-oracle.js --neg-arm  expect M1 RED, rc=0
 */

'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (err) {
  console.log('SETUP ERROR: jsdom is required (' + (err && err.message) + ').');
  process.exit(2);
}

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const PANEL = path.join(REPO, 'app', 'panel');
const NEG = process.argv.indexOf('--neg-arm') >= 0;
const SCRATCH = 'I:/cc-tmp/surface-loop-panel-neg';
const NL = String.fromCharCode(10);

let arm = '';
const rows = [];

function check(name, real, want) {
  const good = JSON.stringify(real) === JSON.stringify(want);
  rows.push({ arm: arm, name: name, ok: good, real: JSON.stringify(real), want: JSON.stringify(want) });
  console.log('  [' + (good ? 'PASS' : 'FAIL') + '] ' + name);
  console.log('         real = ' + JSON.stringify(real) + '   want = ' + JSON.stringify(want));
  return good;
}
function checkTrue(name, real) { return check(name, real, true); }

function scriptSources(html) {
  return Array.from(html.matchAll(/<script\s+src="([^"]+)"[^>]*><\/script>/g))
    .map(function (m) { return m[1]; });
}

/* A store with real entries, so the history gallery can paint while the surface
 * arms run -- a page that throws on load would be testing nothing. */
function historyEntries(count) {
  const out = [];
  for (let i = 0; i < count; i += 1) {
    const when = new Date(Date.now() - (i + 1) * 60 * 1000);
    const iso = when.toISOString();
    out.push({ date: iso.slice(0, 10), time: iso.slice(11, 19),
                text: 'linha numero ' + (i + 1), path: 'H:/sotto/history/x.md' });
  }
  return out;
}

/* The bridge, shaped like the real shell: a setPanelSurface ask is answered by
 * setting the document surface AND echoing the geometry back -- the echo is the
 * second half of the closed loop, and a stub that omitted it would be testing a
 * loop that does not exist. */
function bridgeStub(window, entries) {
  const subs = { caption: [], status: [], geometry: [] };
  const state = { pageAsks: 0, driverAsks: 0, inEcho: 0, depth: 0, capped: 0, repaints: 0 };
  const fireGeometry = function (payload) {
    state.inEcho += 1;
    try {
      for (const cb of subs.geometry) { try { cb(payload); } catch (err) { /* one listener */ } }
    } finally { state.inEcho -= 1; }
  };
  const bridge = {
    onCaption: function (cb) { subs.caption.push(cb); },
    onStatus: function (cb) { subs.status.push(cb); },
    onGeometry: function (cb) { subs.geometry.push(cb); },
    hide: function () {}, toggle: function () {}, quit: function () {},
    setPointerInteractive: function () {},
    captionApplied: function () {}, statusApplied: function () {}, ready: function () {},
    clearApplied: function () {},
    getInfo: function () {
      return Promise.resolve({ hotkey: 'Alt+C', versions: { shell: 'surface-loop-panel-oracle' } });
    },
    HOTKEY: 'Alt+C', platform: 'win32',
    history: {
      append: function () { return Promise.resolve({ entry: null }); },
      tail: function () {
        return Promise.resolve({ entries: entries, root: 'H:/sotto/history',
                              canonicalProducer: 'redux' });
      },
      search: function () { return Promise.resolve({ hits: [] }); },
      root: function () {
        return Promise.resolve({ root: 'H:/sotto/history', canonicalProducer: 'redux' });
      },
      reveal: function () {},
    },
    setLiveEnabled: function (on) { return Promise.resolve({ liveEnabled: Boolean(on) }); },
    pause: function () { return Promise.resolve({ paused: true }); },
    setPanelSurface: function (name, reason) {
      /* THE SHELL'S OWN ANSWER, in the shell's own shape: the document surface is
         set first (the shell waits for the script), then the geometry is sent
         back. Both halves are what the real sotto_webview.py does. */
      /* THE PAGE'S ASK, counted where it happens: any ask made while a geometry
         echo is being dispatched came from the page (applyFloat, or
         caption-float.js setFloat). An ask made with no echo in flight is this
         FILE's driver. The first draft keyed on the wrong frame and read the
         page's own ask as its own -- measured, and that is why this is here. */
      if (state.inEcho > 0) state.pageAsks += 1; else state.driverAsks += 1;
      /* THE BREAKER: once the loop has run away ONCE, the measurement is made and
         the stub stops echoing, so a mutant finishes in a second instead of
         exploring an exponential tree. `capped` is the fact every arm asserts.
         A CIRCUIT BREAKER, not a fix: it lives in the ORACLE, never in the
         product. */
      if (state.capped > 0) {
        return Promise.resolve({ surface: String(name), reason: reason, capped: true });
      }
      /* THE CAP IS THE INSTRUMENT, not a convenience: with the page guard deleted
         the two sides drive each other without bound, and an oracle that hangs
         reports nothing. The cap turns the runaway into `capped`, a number every
         arm asserts is 0 -- so the shipped page is GREEN and the mutant is RED
         instead of a 300 s timeout. */
      state.depth += 1;
      if (state.depth > 12) {
        state.capped += 1;
        state.depth -= 1;
        return Promise.resolve({ surface: String(name), reason: reason, capped: true });
      }
      try {
        const surface = window.SottoSurfaces ? window.SottoSurfaces.set(String(name)) : null;
        fireGeometry({ width: 1040, height: 150, surface: String(surface), reason: reason });
        return Promise.resolve({ surface: String(surface), reason: reason });
      } finally { state.depth -= 1; }
    },
    __emit: function (kind, payload) {
      if (kind === 'geometry') return fireGeometry(payload);
      for (const cb of subs[kind]) { try { cb(payload); } catch (err) {} }
    },
  };
  window.sotto = bridge;
  bridge.state = state;
  return bridge;
}

/* The REAL document: the shipped markup, the shipped stylesheets in the shipped
 * order, and the document's OWN script list run in order. Nothing is copied,
 * nothing is transcribed -- the same harness the caption lane proved. */
function loadPanel(dir) {
  const htmlPath = path.join(dir, 'panel.html');
  const html = fs.readFileSync(htmlPath, 'utf8');
  const dom = new JSDOM(html, {
    url: 'file:///' + htmlPath.replace(/\\/g, '/'),
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  const window = dom.window;
  const style = window.document.createElement('style');
  const css = fs.readFileSync(path.join(dir, 'panel.css'), 'utf8');
  const floatCssPath = path.join(dir, 'caption-float.css');
  const floatCss = fs.existsSync(floatCssPath) ? fs.readFileSync(floatCssPath, 'utf8') : '';
  style.textContent = css + '\n' + floatCss;
  window.document.head.prepend(style);
  const bridge = bridgeStub(window, historyEntries(12));
  const state = bridge.state;
  /* THE PAGE'S REPAINT, COUNTED AT THE DOM BOUNDARY. `applySurface()` ends in
     `applyLiveEnabled()` -> `paintLiveLamps()`, and that is ONE write of
     `aria-label` on `#live-lamp` per repaint -- the one DOM write a surface
     switch always makes and a repeat must not. The page no longer ASKS the shell
     anything when it repaints (the caption window belongs to the shell now,
     panel.js:2729), so the ask count is zero on the shipped page and cannot
     tell the shipped page from an unguarded one. The repaint count is what the
     two page guards actually protect.
     THE WRAP IS IN THE HARNESS, NEVER IN THE PRODUCT: this file measures the
     shipped bytes, it does not change them. */
  const realSetAttribute = window.Element.prototype.setAttribute;
  window.Element.prototype.setAttribute = function (name, value) {
    if (name === 'aria-label' && this.id === 'live-lamp') state.repaints += 1;
    return realSetAttribute.call(this, name, value);
  };
  const errors = [];
  for (const src of scriptSources(html)) {
    const file = path.resolve(dir, src);
    if (!fs.existsSync(file)) { errors.push('missing ' + src); continue; }
    try { window.eval(fs.readFileSync(file, 'utf8')); }
    catch (err) { errors.push(src + ': ' + (err && err.message)); }
  }
  try { window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true })); }
  catch (err) { errors.push('DOMContentLoaded: ' + (err && err.message)); }
  return { window: window, document: window.document, bridge: bridge, errors: errors };
}

function surfaceOf(document) {
  return document.body ? String(document.body.dataset.surface) : 'ABSENT';
}

/* This file's own calls are wrapped in drive() so they read as the driver's in the
 * log; the COUNT is decided by the echo flag in the stub, which is the honest
 * marker: a page ask only ever happens inside a geometry dispatch. */
function drive(state, fn) {
  state.driverCalls = (state.driverCalls || 0) + 1;
  try { return fn(); } finally { state.driverCalls -= 1; }
}

function echo(bridge, surface) {
  bridge.__emit('geometry', { width: 1040, height: 150, surface: surface, reason: 'strip-float-off' });
}

function runArms(dir, label) {
  const page = loadPanel(dir);
  const document = page.document, bridge = page.bridge;
  const errors = page.errors;
  const state = bridge.state;
  const out = [];
  const push = function (name, ok, detail) {
    out.push({ arm: 'PAGE', name: name, ok: !!ok, detail: detail || '' });
    console.log('  [' + (ok ? 'PASS' : 'FAIL') + '] ' + name + (detail ? ' -- ' + detail : ''));
  };

  if (errors.length) {
    push('the shipped scripts all load', false, errors.join('; '));
    return out;
  }
  push('the shipped scripts all load', true,
        scriptSources(fs.readFileSync(path.join(dir, 'panel.html'), 'utf8')).length
        + ' scripts, 0 errors');

  /* A -- a real switch repaints: the document moves to the strip and the page
     paints it -- and it asks the shell for NOTHING, because the caption window
     belongs to the shell now (panel.js:2729). The cure is a guard on a REPEAT,
     never a suppression of the switch: so the repaint must HAPPEN here. */
  const beforeA = state.repaints;
  const beforeAAsks = state.pageAsks;
  drive(state, function () { echo(bridge, 'strip'); });
  push('A GENUINE-SWITCH a real surface switch still repaints',
        state.repaints - beforeA > 0 && state.pageAsks - beforeAAsks === 0
        && surfaceOf(document) === 'strip' && state.capped === 0,
        'repaints=' + (state.repaints - beforeA) + ' asks=' + (state.pageAsks - beforeAAsks)
        + ' surface=' + surfaceOf(document)
        + ' -- the cure is a guard on a REPEAT, never a suppression of the switch');

  /* B -- the echo storm repaints nothing. */
  const beforeB = state.repaints;
  const beforeBAsks = state.pageAsks;
  for (let i = 0; i < 200; i += 1) drive(state, function () { echo(bridge, 'strip'); });
  push('B ECHO-STORM 200 identical echoes repaint nothing',
        state.repaints - beforeB === 0 && state.pageAsks - beforeBAsks === 0
        && surfaceOf(document) === 'strip' && state.capped === 0,
        'repaints=' + (state.repaints - beforeB) + ' asks=' + (state.pageAsks - beforeBAsks) + ' over 200 echoes');

  /* C -- the page's own re-ask for the same surface repaints nothing more. */
  const beforeC = state.repaints;
  const beforeCAsks = state.pageAsks;
  drive(state, function () { bridge.setPanelSurface('strip', 'strip-float-off'); });
  push('C PAGE-REASK the page own re-ask repaints nothing more',
        state.repaints - beforeC === 0 && state.pageAsks - beforeCAsks === 0 && state.capped === 0,
        'repaints=' + (state.repaints - beforeC) + ' asks=' + (state.pageAsks - beforeCAsks) + ' capped=' + state.capped);

  /* D -- an unknown name is refused and repaints nothing. */
  const beforeD = state.repaints;
  const beforeDAsks = state.pageAsks;
  drive(state, function () { echo(bridge, 'nonsense'); });
  push('D REFUSAL an unknown name changes nothing',
        state.repaints - beforeD === 0 && state.pageAsks - beforeDAsks === 0
        && surfaceOf(document) === 'strip' && state.capped === 0,
        'repaints=' + (state.repaints - beforeD) + ' asks=' + (state.pageAsks - beforeDAsks) + ' surface=' + surfaceOf(document));

  /* E -- the closed loop, 200 rounds: round one repaints, the rest must not. */
  const beforeE = state.repaints;
  const beforeEAsks = state.pageAsks;
  for (let i = 0; i < 200; i += 1) {
    drive(state, function () { bridge.setPanelSurface('strip', 'strip-float-off'); });
  }
  const asked = state.repaints - beforeE;
  push('E FIX-POINT the closed loop repaints nothing after the switch',
        asked === 0 && state.pageAsks - beforeEAsks === 0 && state.capped === 0, 'repaints=' + asked + ' asks=' + (state.pageAsks - beforeEAsks) + ' capped=' + state.capped + ' over 200 rounds of the closed loop '
        + ' (the page is already on that surface; a guarded loop adds no traffic)');

  return out;
}

/* THE MUTANTS -- the page's cure, removed from a COPY of app/panel.
 *
 * M1  surface.js   the change-guard. Shipped:
 *
 *       document.body.dataset.surface = value;
 *       if (value !== previous) {
 *         for (var i = 0; i < listeners.length; i += 1) { ... }
 *       }
 *
 *     Mutant: the `if` is deleted, so EVERY set fires every listener. That is the
 *     pre-fix shape, and it is what the echo storm needs to re-paint and re-ask.
 *
 * M2  panel.js     the `after !== before` guard in setSurface(). Mutant: the guard
 *     line is replaced by an unconditional applySurface(). MEASURED: also
 *     load-bearing (5 of 6 arms RED). setSurface() is the function the geometry
 *     echo lands in, and it calls applySurface() itself, so the guard it lost is
 *     the one that stopped the echo from re-entering the pipeline. */
const MUTANTS = [
  {
    file: 'surface.js',
    label: 'M1 surface.js change-guard deleted (listeners fire on every set)',
    old: '    if (value !== previous) {' + NL + '      for (var i = 0; i < listeners.length; i += 1) {' + NL + '        try { listeners[i](value, previous); } catch (err) { /* one listener cannot break the switch */ }' + NL + '      }' + NL + '    }',
    neu: '    for (var i = 0; i < listeners.length; i += 1) {' + NL + '      try { listeners[i](value, previous); } catch (err) { /* one listener cannot break the switch */ }' + NL + '    }',
  },
  {
    file: 'panel.js',
    label: 'M2 panel.js after!==before guard deleted (load-bearing: 4 of 6 arms RED, MEASURED 2026-10-20)',
    old: '  if (!window.SottoSurfaces || after !== before) applySurface();',
    neu: '  applySurface();',
  },
];

function applyMutant(panelDir, mutant) {
  const target = path.join(panelDir, mutant.file);
  const text = fs.readFileSync(target, 'utf8');
  if (text.split(mutant.old).length - 1 !== 1) {
    return 'anchor appears ' + (text.split(mutant.old).length - 1) + ' times, not once';
  }
  fs.writeFileSync(target, text.replace(mutant.old, mutant.neu));
  return null;
}

/* THE COPY IS RECURSIVE, and the first draft was not: app/panel holds themes/ and
 * skins/ subdirectories, the document loads themes/themes.js and friends, and a
 * flat copy made every mutant RED for the wrong reason -- a missing script, not a
 * deleted guard. That is a false red, and a false red is worse than none. */
function copyTree(from, to) {
  if (!fs.existsSync(to)) fs.mkdirSync(to, { recursive: true });
  for (const f of fs.readdirSync(from)) {
    const src = path.join(from, f);
    const dst = path.join(to, f);
    const st = fs.statSync(src);
    if (st.isDirectory()) copyTree(src, dst);
    else if (/\.(js|css|html)$/.test(f)) fs.copyFileSync(src, dst);
  }
}

function freshCopy() {
  copyTree(PANEL, SCRATCH);
  return SCRATCH;
}

function summary(label, arms) {
  const green = arms.filter(function (a) { return a.ok; }).length;
  const red = arms.length - green;
  console.log('');
  console.log(label + ': ' + green + ' green / ' + red + ' red');
  arms.forEach(function (a) { if (!a.ok) console.log('    RED    ' + a.name + ' -- ' + a.detail); });
  return { green: green, red: red, arms: arms };
}

console.log('ORACLE surface-loop panel (the page half of the JS<->Python surface loop)');
console.log('  document  ' + PANEL);
console.log('  arms      A switch / B echo-storm / C page re-ask / D refusal / E closed loop');
console.log('  counter   the page REPAINTS (applySurface -> applyLiveEnabled -> the live lamp); the');
  console.log('            page->shell setPanelSurface asks are counted too, and are 0 by design');

const shipped = summary('SHIPPED app/panel', runArms(PANEL, 'shipped'));

let verdict = shipped.red === 0 ? 'PASS' : 'FAIL';
let exit = shipped.red === 0 ? 0 : 1;

if (NEG) {
  console.log('');
  console.log('--- negative arm: the page cure removed from a COPY of app/panel ---');
  const arms = [];
  MUTANTS.forEach(function (m) {
    const dir = freshCopy();
    const problem = applyMutant(dir, m);
    if (problem) {
      console.log('  SETUP ERROR (' + m.file + '): ' + problem);
      process.exit(2);
    }
    arms.push({ mutant: m.label, run: runArms(dir, m.file) });
  });
  arms.forEach(function (a) {
    const r = summary(a.mutant, a.run);
    console.log('    ' + (r.red > 0 ? 'RED-as-expected' : 'INERT (no arm moved)') + ': ' + r.red + ' red');
  });
  const moved = arms.map(function (a) {
    return a.run.filter(function (x) { return !x.ok; }).length;
  });
  const allMoved = moved.every(function (n) { return n > 0; });
  if (allMoved) {
    console.log('');
    console.log('VERDICT: PASS -- both page guards are load-bearing: deleting either one turns');
    console.log('the echo into a repeat the arms count (the repaint count, measured) and the arms');
    console.log('report RED. Measured red counts per mutant: ' + moved.join(', ') + '.');
  } else {
    console.log('');
    console.log('VERDICT: FAIL -- a page mutant did not move any arm, so this file cannot');
    console.log('distinguish the shipped guard from an unguarded page. red counts: ' + moved.join(', '));
    verdict = 'FAIL';
    exit = 1;
  }
}

console.log('');
console.log('VERDICT: ' + verdict + ' (shipped ' + shipped.green + '/' + shipped.arms.length + ' green);');
process.exit(exit);

