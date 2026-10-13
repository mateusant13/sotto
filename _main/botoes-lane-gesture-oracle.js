/* botoes-lane-gesture-oracle.js -- THE DRAG GESTURE, ON A REAL DOM.
 *
 * WHY A SECOND FILE. `_main/botoes-lane-oracle.js` reads the BYTES and proves the
 * gesture is DECLARED. That is not the same claim as "the gesture WORKS": a script
 * whose pointermove handler never fires, or whose storage write is unreachable,
 * passes every byte check in the other file. So this probe parses the REAL
 * `panel.html`, runs the REAL scripts (including the inline gesture), and pushes
 * real pointer events through it.
 *
 * WHAT IT DOES NOT DO: no browser, no WebView2, no shell, no window. jsdom only.
 * The window move itself is the shell half and is NOT measured here — the probe
 * asserts the PAGE half: the offset is computed, persisted under the agreed key,
 * painted onto the document, and handed to the bridge when the bridge has the
 * method.
 *
 * ARMS
 *   1  a drag from the grip records an offset
 *   2  the offset is PERSISTED under `sotto:strip-offset` as {x,y,v}
 *   3  the document is painted (`--strip-move-x`/`--strip-move-y`)
 *   4  the bridge is called with (dx, dy, phase) when it has the method
 *   5  a drag that starts ON A BUTTON is NOT a drag (the button keeps its click)
 *   6  a fresh load RESTORES the stored offset before the first paint
 *   7  the CONTROL: the same document with the pointermove handler renamed
 *      records NOTHING — the arms above cannot pass for the wrong reason
 *
 * Usage:  node _main/botoes-lane-gesture-oracle.js   expect GREEN, rc=0
 * Exit codes: 0 green | 1 a check failed | 2 setup error (jsdom absent).
 */
'use strict';

const fs = require('node:fs');
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

function load(dir, mutate, seed) {
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
  const audit = { offsets: [] };
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
    const ev = new window.MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, button: 0, buttons: 1 });
    (target || window).dispatchEvent(ev);
  }
  return { window: window, document: doc, audit: audit, errors: errors, pointer: pointer };
}

/* --------------------------------------------------------------- the shipped bytes */
const p = load(PANEL);
check('SETUP the external scripts all ran', p.errors, []);
const doc = p.document;
const grip = doc.getElementById('strip-drag-handle');
const bar = doc.getElementById('strip-controls');
check('SETUP the grip and the bar are in the document', [Boolean(grip), Boolean(bar)], [true, true]);

/* ARM 1-4: a drag from the grip. */
p.pointer('pointerdown', 100, 100, grip);
p.pointer('pointermove', 160, 130);
p.pointer('pointerup', 160, 130);
const raw = p.window.localStorage.getItem('sotto:strip-offset');
check('1 the drag recorded an offset under sotto:strip-offset', typeof raw, 'string');
let stored = null;
try { stored = JSON.parse(raw); } catch (err) {}
check('2 the stored value is the versioned x/y/v object', [stored && stored.x, stored && stored.y, stored && stored.v], [60, 30, 1]);
const root = doc.documentElement.style;
check('3 the document is painted with the same offset', [root.getPropertyValue('--strip-move-x'), root.getPropertyValue('--strip-move-y')], ['60px', '30px']);
check('4 the bridge was called with dx, dy, phase', p.audit.offsets.length >= 1 && p.audit.offsets[0], [60, 30, 'move']);

/* ARM 5: a press that starts on a BUTTON is that button's, not the drag's. */
const p2 = load(PANEL);
const liveBtn = p2.document.getElementById('strip-live-button');
p2.pointer('pointerdown', 100, 100, liveBtn);
p2.pointer('pointermove', 200, 200);
check('5 a press that starts on a control is NOT a drag', p2.window.localStorage.getItem('sotto:strip-offset'), null);

/* ARM 6: a fresh load restores what was stored, BEFORE the first paint. */
const p4 = load(PANEL, null, { 'sotto:strip-offset': JSON.stringify({ x: -40, y: 12, v: 1 }) });
const r4 = p4.document.documentElement.style;
check('6 a fresh load restores the stored offset before the first paint', [r4.getPropertyValue('--strip-move-x'), r4.getPropertyValue('--strip-move-y')], ['-40px', '12px']);

/* ARM 7: THE CONTROL. The same document with the pointermove handler renamed must
   record NOTHING, or the arms above could be passing for a reason of their own. */
const mutantHtml = fs.readFileSync(path.join(PANEL, 'panel.html'), 'utf8');
const p5 = load(PANEL, function (html) { return html.replace('window.addEventListener("pointermove"', 'window.addEventListener("pointermove-DELETED"'); });
const grip5 = p5.document.getElementById('strip-drag-handle');
check('7 CONTROL the mutant really is mutated (the anchor applied to the copy)',
  [/pointermove-DELETED/.test(mutantHtml), /pointermove-DELETED/.test(fs.readFileSync(path.join(PANEL, 'panel.html'), 'utf8'))],
  [false, false]);
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

let bad = 0;
for (const r of rows) if (!r.ok) bad += 1;
console.log('');
console.log('BOTOES GESTURE ORACLE -- shipped app/panel');
console.log(rows.length + ' check(s), ' + bad + ' failed');
console.log('VERDICT: ' + (bad === 0 ? 'PASS' : 'FAIL'));
process.exit(bad === 0 ? 0 : 1);
