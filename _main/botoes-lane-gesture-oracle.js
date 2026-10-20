/* botoes-lane-gesture-oracle.js -- THE DRAG GESTURE, ON A REAL DOM.
 *
 * WHY A SECOND FILE. `_main/botoes-lane-oracle.js` reads the BYTES and proves the
 * gesture is DECLARED. That is not the same claim as "the gesture WORKS": a script
 * whose pointermove handler never fires, or whose storage write is unreachable,
 * passes every byte check in the other file. So this probe parses the REAL
 * `panel.html`, runs the REAL scripts (including the EXTERNAL `strip-drag.js` -- the
 * gesture was inline until 2026-10-13 and the panel's own CSP blocked it), and pushes
 * real pointer events through it.
 *
 * WHAT IT DOES NOT DO: no browser, no WebView2, no shell, no window. jsdom only.
 * The window move itself is the shell half and is NOT measured here -- the probe
 * asserts the PAGE half.
 *
 * TWO HOSTS, BECAUSE THERE ARE TWO CODE PATHS (owner, 2026-10-17, verbatim:
 * *"mover os paineis e extremamente ruim e nao otimizado, parece q foi implementado
 * completamente errado"*). THE OS NOW MOVES THE WINDOW: `pointerdown` asks the
 * shell for ONE native drag (`ReleaseCapture()` + `WM_NCLBUTTONDOWN`), and the
 * page computes NOTHING. The old JS drag survives ONLY as the fallback for a
 * host that does not ship `beginWindowDrag` (a browser harness, an older shell)
 * -- `app/panel/strip-drag.js:31` picks the branch, `:67` is the native call,
 * `:92`/`:117-119` are the fallback. The gate measures BOTH, because the product
 * ships both.
 *
 * ARMS
 *   N1 the NATIVE host: one press asks the shell for ONE native window drag
 *   N2 and the page computes NOTHING (no offset, no storage, no bridge move)
 *   N3 a press that starts ON A BUTTON is NOT a drag (the button keeps its click)
 *   N4 the panel's own header drags the PANEL
 *   1  the FALLBACK host: a drag from the grip records an offset
 *   2  the offset is PERSISTED under `sotto:strip-offset` as {x,y,v}
 *   3  the document is painted (`--strip-move-x`/`--strip-move-y`)
 *   4  the bridge is called with (dx, dy, phase) when it has the method
 *   5  a drag that starts ON A BUTTON is NOT a drag (the button keeps its click)
 *   6  a fresh load RESTORES the stored offset before the first paint
 *   7  the CONTROL (fallback): the same document with the pointermove handler
 *      renamed records NOTHING -- the arms above cannot pass for the wrong reason
 *   8  the CONTROL (native): the same document with the bridge call renamed
 *      asks for NO drag
 *
 * Usage:  node _main/botoes-lane-gesture-oracle.js   expect GREEN, rc=0
 * Exit codes: 0 green | 1 a check failed | 2 setup error (jsdom absent).
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

const REPO = path.join(__dirname, '..');
const PANEL = path.join(REPO, 'app', 'panel');

const rows = [];
function check(name, real, want) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  rows.push({ name: name, ok: ok });
  console.log('[' + (ok ? 'PASS' : 'FAIL') + '] ' + name);
  if (!ok) {
    console.log('       real = ' + JSON.stringify(real));
    console.log('       want = ' + JSON.stringify(want));
  }
}

function load(dir, mutate, seed, opts) {
  let html = fs.readFileSync(path.join(dir, 'panel.html'), 'utf8');
  if (mutate) html = mutate(html);
  const dom = new JSDOM(html, {
    url: 'https://sotto.invalid/panel.html',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    /* `beforeParse` runs BEFORE the document parses, so a seed is in localStorage
       by the time the inline gesture reads it — which is the whole point of ARM 6. */
    beforeParse: function (w) {
      if (seed) { for (const k of Object.keys(seed)) w.localStorage.setItem(k, seed[k]); }
    },
  });
  const window = dom.window;
  const doc = window.document;
  const audit = { offsets: [], drags: [] };
  window.sotto = {
    onCaption: function () {}, onStatus: function () {}, onGeometry: function () {},
    hide: function () {}, toggle: function () {}, quit: function () {},
    captionApplied: function () {}, statusApplied: function () {}, ready: function () {}, clearApplied: function () {},
    getInfo: function () { return Promise.resolve({}); },
    HOTKEY: 'Alt+C', platform: 'win32',
    history: {
      append: function () { return Promise.resolve({ entry: null }); },
      tail: function () { return Promise.resolve({ entries: [], root: 'x', canonicalProducer: null }); },
      search: function () { return Promise.resolve({ hits: [] }); },
      root: function () { return Promise.resolve({ root: 'x', canonicalProducer: null }); },
      reveal: function () {},
    },
    setLiveEnabled: function () { return Promise.resolve({}); },
    pause: function () { return Promise.resolve({}); },
    setPanelSurface: function () { return Promise.resolve({}); },
    setStripOffset: function (x, y, phase) { audit.offsets.push([x, y, phase]); },
  };
  /* THE NATIVE HOST (2026-10-17). A shell that owns the window ships
     `beginWindowDrag`, and `strip-drag.js:31` takes the native branch when it
     SEES the method. It is installed ONLY when an arm asks for it, because the
     fallback arms need a host WITHOUT it -- and a harness that always had it
     would measure the fallback branch on paper and the native branch in fact. */
  if (opts && opts.native) {
    window.sotto.beginWindowDrag = function (surface) { audit.drags.push(surface); };
  }
  /* The inline gesture already ran during parsing (runScripts: dangerously); the
     external modules are loaded here, in the document's own order. */
  const srcs = Array.from(html.matchAll(/<script\s+src="([^"]+)"[^>]*><\/script>/g)).map(function (m) { return m[1]; });
  const errors = [];
  for (const src of srcs) {
    const file = path.resolve(dir, src);
    if (!fs.existsSync(file)) { errors.push('missing ' + src); continue; }
    try { window.eval(fs.readFileSync(file, 'utf8')); } catch (err) { errors.push(src + ': ' + (err && err.message)); }
  }
  try { doc.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true })); } catch (err) {}
  function pointer(type, x, y, target) {
    /* THE SCREEN COORDINATES ARE NOT OPTIONAL. The fallback drag measures the
       pointer in SCREEN space -- `event.screenX`/`event.screenY`
       (strip-drag.js:142, :149-150) -- because that is how a WINDOW move is
       measured, not the client box. The synthetic events used to carry
       clientX/clientY only, so every fallback delta was 0 and the drag could
       never cross the 4px threshold: the arms below were reading a drag that
       the harness had itself made impossible. Both pairs are carried now. */
    const ev = new window.MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, screenX: x, screenY: y, button: 0, buttons: 1 });
    (target || window).dispatchEvent(ev);
  }
  return { window: window, document: doc, audit: audit, errors: errors, pointer: pointer };
}

/* --------------------------------------------------------------- the shipped bytes */
/* ARM N: THE NATIVE HOST -- THE OS MOVES THE WINDOW (owner, 2026-10-17). This is
   the path the SHIPPED shell takes: `sotto_webview.py` ships `beginWindowDrag`
   (:4561 answers it, :5307 is the offset handler) and `strip-drag.js:31` sees it.
   The arms below are the ones the gate did NOT have while it still measured only
   the JS drag. */
const pn = load(PANEL, null, null, { native: true });
check('SETUP the external scripts all ran (the native host)', pn.errors, []);
const gripN = pn.document.getElementById('strip-drag-handle');
pn.pointer('pointerdown', 100, 100, gripN);
pn.pointer('pointermove', 160, 130);
pn.pointer('pointerup', 160, 130);
check('N1 the native host asks the shell for ONE native window drag of the strip',
  [pn.audit.drags.length, pn.audit.drags[0]], [1, 'strip']);
check('N2 and the page computes NOTHING itself (no offset, no storage, no bridge move)',
  [pn.window.localStorage.getItem('sotto:strip-offset'), pn.audit.offsets.length,
   pn.document.documentElement.style.getPropertyValue('--strip-move-x')], [null, 0, '']);
const pn2 = load(PANEL, null, null, { native: true });
pn2.pointer('pointerdown', 100, 100, pn2.document.getElementById('strip-live-button'));
check('N3 a press that starts on a CONTROL is NOT a drag (the control keeps its click)',
  pn2.audit.drags.length, 0);
const pn3 = load(PANEL, null, null, { native: true });
pn3.pointer('pointerdown', 100, 100, pn3.document.querySelector('.panel__header'));
check('N4 the panel own header drags the PANEL (one drag, of the panel)',
  [pn3.audit.drags.length, pn3.audit.drags[0]], [1, 'panel']);

/* ARM 1-4: the FALLBACK host -- a shell without `beginWindowDrag` (a browser
   harness, an older shell). The JS drag is the product's own fallback and is
   still shipped, so it is still measured. */
const p = load(PANEL);
check('SETUP the external scripts all ran', p.errors, []);
const doc = p.document;
const grip = doc.getElementById('strip-drag-handle');
const bar = doc.getElementById('strip-controls');
check('SETUP the grip and the bar are in the document', [Boolean(grip), Boolean(bar)], [true, true]);

p.pointer('pointerdown', 100, 100, grip);
p.pointer('pointermove', 160, 130);
p.pointer('pointerup', 160, 130);
const raw = p.window.localStorage.getItem('sotto:strip-offset');
check('1 the FALLBACK host records the offset under sotto:strip-offset', typeof raw, 'string');
let stored = null;
try { stored = JSON.parse(raw); } catch (err) {}
check('2 the stored value is the versioned x/y/v object', [stored && stored.x, stored && stored.y, stored && stored.v], [60, 30, 1]);
const root = doc.documentElement.style;
check('3 the document is painted with the same offset', [root.getPropertyValue('--strip-move-x'), root.getPropertyValue('--strip-move-y')], ['60px', '30px']);
check('4 the bridge was called with dx, dy, phase', p.audit.offsets.length >= 1 && p.audit.offsets[0], [60, 30, 'move']);

/* ARM 5: a press that starts on a BUTTON is that button's, not the drag's.
   (FALLBACK host -- the native host measures the same boundary in N3.) */
const p2 = load(PANEL);
const liveBtn = p2.document.getElementById('strip-live-button');
p2.pointer('pointerdown', 100, 100, liveBtn);
p2.pointer('pointermove', 200, 200);
check('5 a press that starts on a control is NOT a drag', p2.window.localStorage.getItem('sotto:strip-offset'), null);

/* ARM 6: a fresh load restores what was stored, BEFORE the first paint.
   (FALLBACK host -- the native host has no offset to restore.) */
const p4 = load(PANEL, null, { 'sotto:strip-offset': JSON.stringify({ x: -40, y: 12, v: 1 }) });
const r4 = p4.document.documentElement.style;
check('6 a fresh load restores the stored offset before the first paint', [r4.getPropertyValue('--strip-move-x'), r4.getPropertyValue('--strip-move-y')], ['-40px', '12px']);

/* ARM 7: THE CONTROL. The same document with the pointermove handler renamed must
   record NOTHING, or the arms above could be passing for a reason of their own.

   RE-BASELINED 2026-10-13: the gesture moved OUT of \'panel.html\' into its own file
   (the panel's CSP blocks inline script), so the mutation is applied to a COPY of
   \'strip-drag.js\' in a scratch tree and the copy is loaded whole. The shipped bytes
   are read first and must NOT carry the marker -- the old check asserted the string
   was absent from BOTH files, which was vacuous (it proved only that the mutation had
   not been written anywhere) and let this control pass while it mutated nothing. */
const TMP = process.env.TMPDIR && fs.existsSync(process.env.TMPDIR) ? process.env.TMPDIR : os.tmpdir();
const negDir = fs.mkdtempSync(path.join(TMP, 'sotto-gesture-neg-'));
fs.cpSync(PANEL, negDir, { recursive: true });
const dragSrc = fs.readFileSync(path.join(PANEL, 'strip-drag.js'), 'utf8');
const dragMut = dragSrc.replace('window.addEventListener("pointermove"',
                                'window.addEventListener("pointermove-DELETED"');
if (dragMut === dragSrc) { console.error('SETUP ERROR: the pointermove anchor is absent from strip-drag.js'); process.exit(2); }
fs.writeFileSync(path.join(negDir, 'strip-drag.js'), dragMut, 'utf8');
check('7 CONTROL the mutant really is mutated (the anchor applied to the copy)',
  [/pointermove-DELETED/.test(dragMut), /pointermove-DELETED/.test(dragSrc)],
  [true, false]);
const p5 = load(negDir);
const grip5 = p5.document.getElementById('strip-drag-handle');
p5.pointer('pointerdown', 100, 100, grip5);
p5.pointer('pointermove', 200, 200);
p5.pointer('pointerup', 200, 200);
check('7b CONTROL the mutant records NO position and tells the bridge NO move',
  [p5.window.localStorage.getItem('sotto:strip-offset'), p5.audit.offsets.filter(function (o) { return o[2] === 'move'; }).length],
  [null, 0]);
/* The mutant's paint stays at the RESTORE value (0px, written once at load): the
   drag itself changed nothing. A live drag would have left 100px here. */
check('7c CONTROL the mutant still PAINTS the un-dragged position (0px, not 100px)',
  [p5.document.documentElement.style.getPropertyValue('--strip-move-x'), p5.document.documentElement.style.getPropertyValue('--strip-move-y')],
  ['0px', '0px']);

/* ARM 8: THE CONTROL OF THE NATIVE PATH. Since 2026-10-17 the native drag IS
   the shipped path, and a gate that only controls the fallback could go green
   with the native call broken. The same copy, with the bridge call renamed, must
   ask for NO drag at all -- and the page must not throw out of the document
   (`strip-drag.js:67-71` catches a refused drag). */
const dragMutNative = dragSrc.replace('bridge.beginWindowDrag(surface);',
                                      'bridge.beginWindowDrag_DELETED(surface);');
if (dragMutNative === dragSrc) { console.error('SETUP ERROR: the beginWindowDrag anchor is absent from strip-drag.js'); process.exit(2); }
fs.writeFileSync(path.join(negDir, 'strip-drag.js'), dragMutNative, 'utf8');
check('8 CONTROL the native mutant really is mutated (the anchor applied to the copy)',
  [/beginWindowDrag_DELETED/.test(dragMutNative), /beginWindowDrag_DELETED/.test(dragSrc)],
  [true, false]);
const p6 = load(negDir, null, null, { native: true });
const grip6 = p6.document.getElementById('strip-drag-handle');
p6.pointer('pointerdown', 100, 100, grip6);
p6.pointer('pointermove', 200, 200);
p6.pointer('pointerup', 200, 200);
check('8b CONTROL the native mutant asks for NO window drag and the page still loads',
  [p6.audit.drags.length, p6.errors], [0, []]);
fs.rmSync(negDir, { recursive: true, force: true });

let bad = 0;
for (const r of rows) if (!r.ok) bad += 1;
console.log('');
console.log('BOTOES GESTURE ORACLE -- shipped app/panel');
console.log(rows.length + ' check(s), ' + bad + ' failed');
console.log('VERDICT: ' + (bad === 0 ? 'PASS' : 'FAIL'));
process.exit(bad === 0 ? 0 : 1);
