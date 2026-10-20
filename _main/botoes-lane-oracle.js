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
 *   M5 the NATIVE drag pointerdown binding is deleted (from strip-drag.js)
 *   M6 the caption-float.css link is deleted
 *   M7 the strip shows its caption box again
 *   M8 the removed Linhar button comes back
 *
 * Usage:
 *   node _main/botoes-lane-oracle.js            expect GREEN, rc=0
 *   node _main/botoes-lane-oracle.js --neg-arm  expect every mutant RED, rc=1 BY DESIGN
 *
 * Exit codes
 *   0  the GREEN arm passed -- OR, in the negative arm, a mutant SURVIVED (the gate
 *      is blind there; that is a FAILURE of the negative arm, not a pass)
 *   1  the GREEN arm failed -- OR, in the negative arm, EVERY mutant was caught
 *      (BY DESIGN: the negative arm has to fail, so this is its success)
 *   2  setup error: an anchor is missing or ambiguous, or a mutant changed nothing
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
  /* THE SET MOVED (2026-10-20, rev 38764ad): the strip's caption-size button came
   * BACK, as ONE button (`#strip-font-scale-button` -- the PAIR that the panel's own
   * `#font-scale-button` is, the same 2026-10-18 ruling), so the bare minimum is
   * FIVE controls and not four. WHAT THIS ARM STILL FORBIDS is what the owner
   * ordered out: the theme pill (the theme-list chevron is gone from the strip) and
   * the "Linhar" door (A7). THE SET IS STILL PINNED EXACTLY, so a NEW control on the
   * strip is still a RED here -- the arm is not weakened, it is re-based. */
  check('A4 the strip is down to the bare-minimum button set (no theme pill, no Linhar door, ONE caption-size button)',
    stripButtons.join(','),
    'strip-live-button,strip-open-button,strip-font-scale-button,strip-hide-button,strip-pause-button');
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
  /* THE ORDER, READ OFF panel.css. THE SELECTOR SHAPE MOVED (2026-10-20): the X and
   * the readout are now pinned as `html body[data-surface="strip"] .stripbar #id`
   * with `!important`, because `button-contract.css` (the LAST sheet, every rule
   * `!important`) pins the SAME row with its OWN numbers -- and the owner found the
   * X painted in the MIDDLE of the row (verbatim, 2026-10-19: *"por que o botao de x
   * dos paineis ta no meio e nao na direita? arruma."*). The OLD regex only knew
   * `body[data-surface="strip"] #id { order: N; }`, so it read NOTHING for the X: D1
   * and D2 went RED on the shipped bytes, and the M4 mutant ("hide stops being the
   * rightmost control") had NOTHING to flip -- which is why M4 died with a SETUP
   * ERROR instead of proving anything. The selector is now read WHOLE and the id is
   * taken out of it, so the arm reads the numbers the file actually ships. */
  const orders = {};
  const re = /body\[data-surface="strip"\]\s+([^{}]*?)\s*\{\s*order:\s*(\d+)\s*(?:!important)?\s*;\s*\}/g;
  let m;
  while ((m = re.exec(css)) !== null) {
    const sel = m[1];
    const id = /#([A-Za-z0-9_-]+)/.exec(sel);
    const key = id ? '#' + id[1]
                   : (/\.stripbar__brand/.test(sel) ? '.stripbar__brand' : sel.trim());
    orders[key] = parseInt(m[2], 10);
  }
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
  /* THE BINDING NAMED HERE IS THE LIVE ONE. `strip-drag.js` grew a SECOND
   * `bar.addEventListener("pointerdown", ...)` on 2026-10-17 (the native drag):
   * the real shell SHIPS `beginWindowDrag` (`sotto_webview.py:4560`), so the native
   * branch is the one that runs and the JS gesture below it is the FALLBACK for a
   * host without it. The old E1 only asked "is there a pointerdown binding on the
   * bar", and the M5 mutant deleted the FIRST one -- which left the fallback, kept
   * E1 GREEN, and made the mutant DECORATIVE (it proved nothing). This arm now
   * names the native binding, which is what a real shell actually drags with. */
  check('E1 the page binds a pointerdown gesture on the strip bar (the NATIVE drag the real shell takes)',
    /getElementById\("strip-controls"\)/.test(drag) &&
    /bar\.addEventListener\("pointerdown", function \(event\) \{ start\("strip", event\); \}\)/.test(drag), true);
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
  /* THE COLOUR CHANGED (2026-10-15, rev 8b601e0): the ON state was RED, and the
   * Lead turned it GREEN with a written reason -- *"vermelho num indicador quer
   * dizer erro, e 'live' nao e um erro"*. THE OWNER'S REQUIREMENT WAS NEVER A HUE,
   * it was *"deve ser CLARO quando ta live e quando nao ta"* -- so this arm now
   * asserts the REQUIREMENT and not the hue: the ON state is painted DIFFERENTLY
   * from the OFF state. (G4 still pins the OFF state to the neutral grey.) */
  const onBorder = /#strip-live-button\[aria-pressed="true"\]\s*\{\s*border-color:\s*([^;]+);/.exec(css);
  const offBorder = /#strip-live-button\[aria-pressed="false"\]\s*\{\s*border-color:\s*([^;]+);/.exec(css);
  const onColour = onBorder ? onBorder[1].trim() : 'ABSENT';
  const offColour = offBorder ? offBorder[1].trim() : 'ABSENT';
  check('G3 the ON state is painted DIFFERENTLY from the OFF state (the owner: CLARO)',
    onColour !== 'ABSENT' && offColour !== 'ABSENT' && onColour !== offColour, true);
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
    anchor: 'id="strip-live-button"',
    apply: function (t) {
      return t.replace(/<button\r?\n\s*type="button"\r?\n\s*class="strip-button strip-button--toggle"\r?\n\s*id="strip-live-button"[\s\S]*?<\/button>\r?\n/, '');
    } },
  { tag: 'M2 the live OFF state loses its word', file: 'panel.css',
    anchor: '  content: "off";',
    apply: function (t) { return t.replace('  content: "off";', '  content: "live";'); } },
  { tag: 'M3 the right panel caption label comes back', file: 'panel.html',
    anchor: '<div class="captions__bar">',
    apply: function (t) {
      return t.replace('<div class="captions__bar">', '<div class="captions__bar">\r\n          <span class="history__label" id="live-label">Live</span>');
    } },
  { tag: 'M4 hide stops being the rightmost control on the strip', file: 'panel.css',
    /* THE ANCHOR MOVED (2026-10-20): the X is now pinned as
     * `html body[data-surface="strip"] .stripbar #strip-hide-button { order: 98 !important; }`
     * -- one more class and `!important`, so it beats `button-contract.css`. The old
     * anchor (`body[data-surface="strip"] #strip-hide-button { order: 5; }`) matched
     * 0 times and the mutant died with a SETUP ERROR instead of proving anything.
     * The MUTATION is the same one this instrument documents: the X is no longer
     * the rightmost control of the row. */
    anchor: 'html body[data-surface="strip"] .stripbar #strip-hide-button { order: 98 !important; }',
    apply: function (t) {
      return t.replace('html body[data-surface="strip"] .stripbar #strip-hide-button { order: 98 !important; }',
                       'html body[data-surface="strip"] .stripbar #strip-hide-button { order: 0 !important; }');
    } },
  { tag: 'M5 the NATIVE drag pointerdown binding is deleted (from strip-drag.js)', file: 'strip-drag.js',
    /* THE ANCHOR MOVED (2026-10-17): `strip-drag.js` grew a SECOND pointerdown
     * binding -- the native drag, which is the one the real shell uses (the shell
     * ships `beginWindowDrag`, `sotto_webview.py:4560`). The old anchor matched 2
     * lines, `replace` took the first, and the FALLBACK binding was left: E1 stayed
     * GREEN and the mutant proved NOTHING. The anchor below is the NATIVE binding
     * (unique), and E1 now names it -- so the mutant is honest. */
    anchor: 'bar.addEventListener("pointerdown", function (event) { start("strip", event); });',
    apply: function (t) {
      return t.replace('bar.addEventListener("pointerdown", function (event) { start("strip", event); });',
                       'void 0; /* m5: the NATIVE drag binding is GONE -- the defect */');
    } },
  { tag: 'M6 the caption-float.css link is deleted', file: 'panel.html',
    anchor: '<link rel="stylesheet" href="caption-float.css" />',
    apply: function (t) { return t.replace('<link rel="stylesheet" href="caption-float.css" />', ''); } },
  { tag: 'M7 the strip shows its caption box again', file: 'panel.css',
    anchor: 'body[data-surface="strip"] .captions {\r\n  display: none;',
    apply: function (t) { return t.replace('body[data-surface="strip"] .captions {\r\n  display: none;', 'body[data-surface="strip"] .captions {\r\n  display: block;'); } },
  { tag: 'M8 the removed Linhar button comes back (the owner moved the control to live)', file: 'panel.html',
    anchor: 'id="strip-open-button"',
    apply: function (t) { return t.replace('id="strip-open-button"', 'id="strip-float-button"'); } },
];

let wrong = 0;
for (const m of muts) {
  copyAll();
  const file = path.join(scratch, m.file);
  const before = fs.readFileSync(file, 'utf8');
  /* THE ANCHOR MUST BE UNIQUE, AND ITS COUNT IS PRINTED. An anchor that appears
   * twice (or not at all) makes the mutation land somewhere this instrument does
   * not document -- and a DECORATIVE mutant is worse than no mutant at all: a
   * green arm then looks proven and proves nothing. */
  const hits = before.split(m.anchor).length - 1;
  if (hits !== 1) {
    console.error('SETUP ERROR: the anchor of ' + m.tag + ' appears ' + hits
                  + ' time(s) in ' + m.file + ' (wanted exactly 1)');
    process.exit(2);
  }
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
if (wrong === 0) {
  console.log('NEG-ARM VERDICT: PASS -- every mutant went RED.');
  /* rc=1 BY DESIGN: the negative arm has to FAIL -- a green here would mean the
   * instrument cannot say NO. rc=0 is what a SURVIVING mutant gets, because a
   * gate that is blind there has not proved anything. */
  console.log('VERDICT: NEG-ARM PASS -- rc=1 by design (the negative arm must fail).');
  process.exit(1);
}
console.log('NEG-ARM VERDICT: FAIL -- ' + wrong + ' mutant(s) stayed GREEN: the gate is BLIND there.');
console.log('VERDICT: NEG-ARM FAIL -- a mutant SURVIVED; rc=0 says "the arm ran, and it found nothing".');
process.exit(0);
