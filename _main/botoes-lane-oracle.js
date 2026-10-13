/* botoes-lane-oracle.js -- THE BOTTOM PANEL, THE LIVE BUTTON, THE X AND THE DRAG.
 *
 * THE OWNER'S ORDER (2026-10-12), verbatim, and this file is one check per clause:
 *   *"a porra do painel, e pra ser minimo."*
 *   *"o painel de baixo tem que ser movivel pra cima ou pra baixo ou pros lados."*
 *   *"tira o botao da direita de mostrar legenda."*
 *   *"o botao de mostrar a legenda ao vivo deve ser o live. e deve ser CLARO
 *     quando ta live e quando nao ta."*
 *   *"o botao de x pra dar hide introduzido em lugar aleatorio e estupido. bota
 *     ele na direita dos botoes."*
 *   *"o painel de baixo, ta errado. ele nao deve mostrar legenda de jeito nenhum.
 *     ele deve ser menor ainda, mais estreito, do tamanho dos botoes. os botoes
 *     tem que ser mais claros."*
 *   *"o painel de baixo, deve conter apenas o bare minimum."*
 *
 * WHAT THIS READS: THE BYTES of `app/panel/panel.html`, `app/panel/panel.css` and the
 * strip's own gesture file `app/panel/strip-drag.js`. The gesture was an INLINE
 * <script> until 2026-10-13 and the panel's own CSP (`script-src 'self'`, no
 * 'unsafe-inline') BLOCKED it, so the bytes MOVED to an external file; this oracle
 * reads where they are NOW. No browser, no shell, no worker, no network. Every check
 * names its instrument (a regex over those files) and prints the number it read, so a
 * GREEN here is a statement about the shipped files and not an impression.
 *
 * ARMS
 *   A  MINIMUM       the strip node census, and the caption box is display:none
 *   B  LIVE          the live button is THE control, and it carries its state
 *   C  NO RIGHT DOOR the right panel carries no caption-display control
 *   D  X RIGHT       the X is the rightmost CONTROL on both surfaces
 *   E  MOVABLE       the gesture exists in `strip-drag.js` and the contract is written
 *   F  THE LINK      panel.html links caption-float.css AFTER panel.css
 *   G  CLARITY       the two live states differ in WORD and in COLOUR
 *
 * NEGATIVE ARM -- how this file proves it can say NO. The whole `app/panel` tree is
 * copied to a scratch directory, ONE behaviour is deleted from the copy, and the SAME
 * checks run against it. Every mutant must go RED, or the green above is worth
 * nothing. Eight mutants, one per arm:
 *   M1 the live button is deleted
 *   M2 the live OFF state loses its word (both states say the same thing)
 *   M3 the right panel caption label comes back
 *   M4 hide stops being the rightmost control on the strip
 *   M5 the drag gesture pointerdown binding is deleted (from strip-drag.js)
 *   M6 the caption-float.css link is deleted
 *   M7 the strip shows its caption box again
 *   M8 the removed Linhar button comes back
 *
 * Usage:
 *   node _main/botoes-lane-oracle.js            expect GREEN, rc=0
 *   node _main/botoes-lane-oracle.js --neg-arm  expect every mutant RED, rc=0
 *
 * Exit codes: 0 as specified above | 1 a check failed | 2 setup error.
 */
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const SHIPPED = path.join(REPO, 'app', 'panel');
const NEG = process.argv.indexOf('--neg-arm') >= 0;

const rows = [];
let arm = '';

function check(name, real, want) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  rows.push({ arm: arm, name: name, ok: ok, real: real, want: want });
  console.log('[' + (ok ? 'PASS' : 'FAIL') + '] ' + name);
  if (!ok) {
    console.log('       real = ' + JSON.stringify(real));
    console.log('       want = ' + JSON.stringify(want));
  }
}

function read(dir, name) { return fs.readFileSync(path.join(dir, name), 'utf8'); }

/* The ids that live INSIDE the strip section, in document order. */
function stripIds(html) {
  const bar = html.match(/<section class="stripbar"[\s\S]*?<\/section>/);
  if (!bar) return null;
  return Array.from(bar[0].matchAll(/id="([^"]+)"/g)).map(function (m) { return m[1]; });
}

function runChecks(dir) {
  rows.length = 0;
  const html = read(dir, 'panel.html');
  const css = read(dir, 'panel.css');
  /* THE GESTURE LIVES IN ITS OWN FILE since 2026-10-13 (the panel's CSP blocks inline
     script; see the file header). E1-E8 below read THESE bytes. */
  const drag = read(dir, 'strip-drag.js');
  const ids = stripIds(html);

  /* ------------------------------------------------------------------ A: MINIMUM */
  arm = 'A';
  check('A1 the strip section exists and is parseable', Array.isArray(ids) && ids.length > 0, true);
  check('A2 the strip carries NO caption node',
    /class="caption(?:__|\b)|id="caption-list"|class="captions"/.test(html.match(/<section class="stripbar"[\s\S]*?<\/section>/)[0]), false);
  check('A3 the strip surface hides the caption box',
    /body\[data-surface="strip"\] \.captions \{\s*display:\s*none/.test(css), true);
  const stripButtons = ids.filter(function (id) { return /^strip-.*button$/.test(id); });
  check('A4 the strip is down to the bare-minimum button set (no theme pill, no font dial)',
    stripButtons.join(','),
    'strip-live-button,strip-open-button,strip-hide-button,strip-pause-button');
  check('A5 the transparency button the owner ordered out is STILL out',
    /strip-transparency-button/.test(html), false);
  check('A7 the separate Linhar button is GONE (the LIVE button is the caption control)',
    /id="strip-float-button"/.test(html), false);
  const height = /--strip-height:\s*([^;]+);/.exec(css);
  check('A6 the strip height is the button row (40px), not the old 100px',
    height ? height[1].trim() : 'ABSENT', '40px');

  /* ------------------------------------------------------------------ B: LIVE */
  arm = 'B';
  const live = html.match(/<button(?:(?!<\/button>)[\s\S])*?id="strip-live-button"(?:(?!<\/button>)[\s\S])*?<\/button>/);
  check('B1 the live button is the strip toggle', Boolean(live), true);
  check('B2 it carries aria-pressed (the state a screen reader announces)',
    live ? /aria-pressed="(true|false)"/.test(live[0]) : false, true);
  check('B3 its word is the owner own word: live',
    live ? /<span class="strip-button__label" id="strip-live-label">live<\/span>/.test(live[0]) : false, true);

  /* ------------------------------------------------------------------ C: NO RIGHT DOOR */
  arm = 'C';
  check('C1 the right panel caption label is GONE',
    /id="live-label"/.test(html), false);
  check('C2 the caption box still names itself for the accessibility tree',
    /<section class="captions"[^>]*aria-label="[^"]+"/.test(html), true);
  /* C3 asks the NARROW question: is there an INTERACTIVE caption display
     control left anywhere? The caption BOX (`#captions`, `#caption-list`) and the
     floated overlay (`#caption-float*`) are not controls — they are the product and
     the third overlay, and both are supposed to be there. So the check is: no
     <button> whose id names a caption, and no `#live-label` span. */
  const captionButtons = Array.from(html.matchAll(/<button[^>]*id="([^"]+)"[^>]*>/g))
    .map(function (m) { return m[1]; })
    .filter(function (id) { return /caption|legenda|live-label/i.test(id); });
  check('C3 no other node is a caption display toggle',
    [captionButtons.join(','), /id="live-label"/.test(html)], ['', false]);

  /* ------------------------------------------------------------------ D: X RIGHT */
  arm = 'D';
  const orders = {};
  const re = /body\[data-surface="strip"\]\s+(#[A-Za-z0-9_-]+|\.stripbar__brand)\s*\{\s*order:\s*(\d+)\s*;\s*\}/g;
  let m;
  while ((m = re.exec(css)) !== null) orders[m[1]] = parseInt(m[2], 10);
  const buttonOrders = Object.keys(orders).filter(function (k) { return /button$/.test(k); });
  const maxButton = buttonOrders.reduce(function (a, k) { return Math.max(a, orders[k]); }, -1);
  check('D1 hide is the rightmost CONTROL on the strip',
    orders['#strip-hide-button'] === maxButton && buttonOrders.length >= 4,
    true);
  check('D2 only the state READOUT stands after hide',
    orders['#strip-state'] > orders['#strip-hide-button'], true);
  const ctrl = html.match(/<div class="panel__controls">[\s\S]*?<\/div>/);
  const ctrlIds = ctrl ? Array.from(ctrl[0].matchAll(/id="([^"]+)"/g)).map(function (x) { return x[1]; }) : [];
  check('D3 the right panel X is the LAST control in document order',
    ctrlIds[ctrlIds.length - 1], 'hide-button');
  const panelOrder = /\.panel__controls #hide-button \{\s*order:\s*(\d+)\s*;/.exec(css);
  check('D4 the right panel X carries the highest declared order',
    panelOrder ? parseInt(panelOrder[1], 10) : 'ABSENT', 7);

  /* ------------------------------------------------------------------ E: MOVABLE */
  arm = 'E';
  check('E1 the page binds a pointerdown gesture on the strip bar',
    /getElementById\("strip-controls"\)/.test(drag) &&
    /bar\.addEventListener\("pointerdown"/.test(drag), true);
  check('E2 it tracks the pointer and computes an offset',
    /addEventListener\("pointermove"/.test(drag) && /start\.ox \+ dx/.test(drag), true);
  check('E3 the position is PERSISTED under a named key',
    /var KEY = "sotto:strip-offset"/.test(drag), true);
  check('E4 the stored value is a versioned x/y object',
    /JSON\.stringify\(\{ x: Math\.round\(off\.x\), y: Math\.round\(off\.y\), v: 1 \}\)/.test(drag), true);
  check('E5 the shell is told, and the call is OPTIONAL (probed, not assumed)',
    /typeof bridge\.setStripOffset === "function"/.test(drag), true);
  check('E6 the page also paints the offset, so the bar follows with or without the shell',
    /--strip-move-x/.test(css) && /--strip-move-y/.test(css), true);
  check('E7 the double-move guard exists (the shell sets data-strip-moved)',
    /body\[data-surface="strip"\]\[data-strip-moved\] \.panel \{\s*transform:\s*none/.test(css), true);
  check('E8 the stored offset is READ BACK before the first paint',
    /var offset = read\(\);\r?\n\s*paint\(offset\);/.test(drag), true);
  check('E9 the drag handle exists and is not a focus stop',
    /id="strip-drag-handle"[^>]*aria-hidden="true"/.test(html), true);

  /* ------------------------------------------------------------------ F: THE LINK */
  arm = 'F';
  const panelCss = html.indexOf('href="panel.css"');
  const floatCss = html.indexOf('href="caption-float.css"');
  check('F1 caption-float.css is linked', floatCss >= 0, true);
  check('F2 and it is linked AFTER panel.css', panelCss >= 0 && floatCss > panelCss, true);

  /* ------------------------------------------------------------------ G: CLARITY */
  arm = 'G';
  check('G1 the OFF state has its own word',
    /#strip-live-button \.strip-button__label::after \{\r?\n\s*content: "off"/.test(css), true);
  check('G2 the ON state has its own word',
    /#strip-live-button\[aria-pressed="true"\] \.strip-button__label::after \{\r?\n\s*content: "live"/.test(css), true);
  check('G3 the ON state is painted red',
    /#strip-live-button\[aria-pressed="true"\] \{\r?\n\s*border-color:\s*rgba\(229, 72, 77/.test(css), true);
  check('G4 the OFF state is painted NEUTRAL (the red is gone)',
    /#strip-live-button\[aria-pressed="false"\] \{\r?\n\s*border-color:\s*rgba\(148, 163, 184/.test(css), true);
  check('G5 the two state rules can never contradict: both key on the SAME attribute',
    (css.match(/#strip-live-button\[aria-pressed=/g) || []).length >= 4, true);
  check('G6 the hidden DOM label is still in the accessibility tree (font-size, not display:none)',
    /#strip-live-button \.strip-button__label \{\r?\n\s*font-size: 0/.test(css), true);

  return rows;
}

function report(label) {
  let bad = 0;
  for (const r of rows) if (!r.ok) bad += 1;
  console.log('');
  console.log('BOTOES LANE ORACLE -- ' + label);
  console.log(rows.length + ' check(s), ' + bad + ' failed');
  if (bad) {
    console.log('failing:');
    for (const r of rows) if (!r.ok) console.log('  [' + r.arm + '] ' + r.name);
  }
  console.log('VERDICT: ' + (bad === 0 ? 'PASS' : 'FAIL'));
  return bad;
}

if (!NEG) {
  runChecks(SHIPPED);
  process.exit(report('shipped app/panel') === 0 ? 0 : 1);
}

/* ------------------------------- NEGATIVE ARM ------------------------------- */
const TMP = process.env.TMPDIR && fs.existsSync(process.env.TMPDIR) ? process.env.TMPDIR : os.tmpdir();
const scratch = fs.mkdtempSync(path.join(TMP, 'sotto-botoes-neg-'));

function copyAll() {
  fs.rmSync(scratch, { recursive: true, force: true });
  fs.mkdirSync(scratch, { recursive: true });
  fs.cpSync(SHIPPED, scratch, { recursive: true });
  for (const f of ['panel.html', 'panel.css', 'strip-drag.js']) {
    const a = fs.readFileSync(path.join(SHIPPED, f));
    const b = fs.readFileSync(path.join(scratch, f));
    if (!a.equals(b)) { console.error('SETUP ERROR: scratch copy of ' + f + ' differs'); process.exit(2); }
  }
}

const muts = [
  { tag: 'M1 the live button is deleted', file: 'panel.html',
    apply: function (t) {
      return t.replace(/<button\r?\n\s*type="button"\r?\n\s*class="strip-button strip-button--toggle"\r?\n\s*id="strip-live-button"[\s\S]*?<\/button>\r?\n/, '');
    } },
  { tag: 'M2 the live OFF state loses its word', file: 'panel.css',
    apply: function (t) { return t.replace('  content: "off";', '  content: "live";'); } },
  { tag: 'M3 the right panel caption label comes back', file: 'panel.html',
    apply: function (t) {
      return t.replace('<div class="captions__bar">', '<div class="captions__bar">\r\n          <span class="history__label" id="live-label">Live</span>');
    } },
  { tag: 'M4 hide stops being the rightmost control on the strip', file: 'panel.css',
    apply: function (t) {
      return t.replace('body[data-surface="strip"] #strip-hide-button { order: 5; }',
                       'body[data-surface="strip"] #strip-hide-button { order: 0; }');
    } },
  { tag: 'M5 the drag gesture pointerdown binding is deleted (from strip-drag.js)', file: 'strip-drag.js',
    apply: function (t) { return t.replace('bar.addEventListener("pointerdown", function (event) {', 'void function (event) {'); } },
  { tag: 'M6 the caption-float.css link is deleted', file: 'panel.html',
    apply: function (t) { return t.replace('<link rel="stylesheet" href="caption-float.css" />', ''); } },
  { tag: 'M7 the strip shows its caption box again', file: 'panel.css',
    apply: function (t) { return t.replace('body[data-surface="strip"] .captions {\r\n  display: none;', 'body[data-surface="strip"] .captions {\r\n  display: block;'); } },
  { tag: 'M8 the removed Linhar button comes back (the owner moved the control to live)', file: 'panel.html',
    apply: function (t) { return t.replace('id="strip-open-button"', 'id="strip-float-button"'); } },
];

let wrong = 0;
for (const m of muts) {
  copyAll();
  const file = path.join(scratch, m.file);
  const before = fs.readFileSync(file, 'utf8');
  const after = m.apply(before);
  if (after === before) { console.error('SETUP ERROR: mutant anchor did nothing in ' + m.file + ': ' + m.tag); process.exit(2); }
  fs.writeFileSync(file, after, 'utf8');
  const quiet = console.log;
  console.log = function () {};
  const bad = runChecks(scratch).filter(function (r) { return !r.ok; }).length;
  console.log = quiet;
  const red = bad > 0;
  if (!red) wrong += 1;
  console.log('  ' + (red ? 'RED  ' : 'GREEN') + '  ' + m.tag + '  -> ' + bad + ' failing check(s)');
}
fs.rmSync(scratch, { recursive: true, force: true });
console.log('');
console.log(wrong === 0 ? 'NEG-ARM VERDICT: PASS -- every mutant went RED.' : 'NEG-ARM VERDICT: FAIL -- ' + wrong + ' mutant(s) stayed GREEN.');
process.exit(wrong === 0 ? 0 : 1);
