'use strict';

/**
 * _s2-bar-dom-oracle.js -- THE BAR AND THE LOOSE CAPTION, ON A REAL DOM.
 *
 * WHY THIS EXISTS. Every other gate on this strip is a TEXT oracle: it reads
 * panel.css and panel.js and asserts that a rule or a call site is PRESENT. Two of
 * the owner's four demands cannot be decided that way, because they are not
 * properties of a source line:
 *
 *   "ele nao deve mostrar legenda de jeito nenhum"  ->  is there caption TEXT inside
 *       the bar node, after a real caption event, or not?
 *   "liga ela NA TELA ... como se nao houvesse painel"  ->  does the overlay paint the
 *       SAME words the panel's own row carries, and does it still paint when the
 *       panel is not there at all?
 *
 * So this probe parses the real panel.html, prepends the real panel.css, runs the
 * document's OWN <script src> list in order against a bridge stub, and then pushes
 * real caption events through the panel's own choke point. panel.js is not modified,
 * stubbed or re-implemented. No window, no WebView2, no audio, no network.
 *
 * ARMS
 *   A  THE BAR CARRIES NO CAPTION TEXT (strip surface), with the PANEL surface as the
 *      live control: the same two tokens must be FOUND there. An arm that cannot find
 *      the words anywhere proves nothing, so the control is part of the arm.
 *   B  THE LIVE BUTTON PUTS THE SAME LINE ON THE SCREEN: it flips data-float, the
 *      overlay becomes display:block, its live line EQUALS the panel's own newest
 *      caption row word for word, the overlay is NOT a descendant of <main class=panel>,
 *      the window-height call reaches the bridge, and a second caption lands while the
 *      panel node is DETACHED from the document (the owner's "como se nao houvesse
 *      painel"), with the previous line kept one back.
 *
 * NEGATIVE ARM -- how to show this probe can say NO. Six mutants, one at a time, each
 * on a reset copy of app/panel, driven by the same checks:
 *
 *   node _main/_s2-bar-dom-oracle.js            expect GREEN, rc=0
 *   node _main/_s2-bar-dom-oracle.js --neg-arm  expect every mutant RED, rc=0
 *
 * Exit codes: 0 as specified above | 1 a check failed | 2 setup error (jsdom absent,
 * a panel file missing, a mutant anchor absent).
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (err) {
  console.log('SETUP ERROR: jsdom is required for this probe (' + (err && err.message) + ').');
  process.exit(2);
}

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const SHIPPED = path.join(REPO, 'app', 'panel');

/* Two tokens that exist nowhere in the panel's own bytes, so finding them in a node
   can only mean a caption event put them there. Asserted below, not assumed. */
const TOKEN1 = 'quixotescamente';
const TOKEN2 = 'vulcanizadissimo';

const rows = [];
let arm = '';

function check(name, real, want, control) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  const differs = control === undefined || JSON.stringify(real) !== JSON.stringify(control);
  const good = ok && differs;
  rows.push({ arm: arm, name: name, ok: good });
  console.log('[' + (good ? 'PASS' : 'FAIL') + '] ' + name);
  console.log('       real    = ' + JSON.stringify(real));
  console.log('       want    = ' + JSON.stringify(want));
  if (control !== undefined) console.log('       control = ' + JSON.stringify(control));
}

function scriptSources(html) {
  /* The panel's OWN order, defer or not: the earlier probe's regex required the tag to
     end immediately after src, so it silently SKIPPED every deferred script -- and
     caption-float.js is one of them. */
  return Array.from(html.matchAll(/<script\s+src="([^"]+)"[^>]*><\/script>/g)).map(function (m) { return m[1]; });
}

function bridgeStub(window) {
  const audit = { surfaces: [], live: [], pause: [] };
  const subs = { caption: [], status: [] };
  const bridge = {
    onCaption: function (cb) { subs.caption.push(cb); },
    onStatus: function (cb) { subs.status.push(cb); },
    onGeometry: function () {},
    hide: function () {}, toggle: function () {}, quit: function () {}, setPointerInteractive: function () {},
    captionApplied: function () {}, statusApplied: function () {}, ready: function () {}, clearApplied: function () {},
    getInfo: function () { return Promise.resolve({ hotkey: 'Alt+C', versions: { shell: 'dom-oracle' } }); },
    HOTKEY: 'Alt+C',
    platform: 'win32',
    history: {
      append: function () { return Promise.resolve({ entry: null }); },
      tail: function () { return Promise.resolve({ entries: [], root: 'H:\\sotto\\history', canonicalProducer: null }); },
      search: function () { return Promise.resolve({ hits: [] }); },
      root: function () { return Promise.resolve({ root: 'H:\\sotto\\history', canonicalProducer: null }); },
      reveal: function () {},
    },
    setLiveEnabled: function (on) { audit.live.push(Boolean(on)); return Promise.resolve({ liveEnabled: Boolean(on) }); },
    pause: function (o) { audit.pause.push(o || {}); return Promise.resolve({ paused: true }); },
    setPanelSurface: function (name, reason) {
      audit.surfaces.push({ surface: String(name), reason: String(reason || '') });
      if (window.SottoSurfaces) window.SottoSurfaces.set(String(name));
      return Promise.resolve({ surface: String(name) });
    },
    __audit: audit,
    __emit: function (kind, payload) { for (const cb of subs[kind]) cb(payload); },
  };
  window.sotto = bridge;
  return bridge;
}

function load(dir) {
  const htmlPath = path.join(dir, 'panel.html');
  const html = fs.readFileSync(htmlPath, 'utf8');
  const dom = new JSDOM(html, {
    url: 'file:///' + htmlPath.replace(/\\/g, '/'),
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  const window = dom.window;
  const style = window.document.createElement('style');
  style.textContent = fs.readFileSync(path.join(dir, 'panel.css'), 'utf8');
  window.document.head.prepend(style);
  const bridge = bridgeStub(window);
  const errors = [];
  for (const src of scriptSources(html)) {
    const file = path.resolve(dir, src);
    if (!fs.existsSync(file)) { errors.push('missing ' + src); continue; }
    try { window.eval(fs.readFileSync(file, 'utf8')); } catch (err) { errors.push(src + ': ' + (err && err.message)); }
  }
  try { window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true })); }
  catch (err) { errors.push('DOMContentLoaded: ' + (err && err.message)); }
  if (!window.SottoFormulation) errors.push('caption-formulation.js did not register window.SottoFormulation');
  const doc = window.document;
  return {
    window: window, document: doc, bridge: bridge, errors: errors,
    id: function (n) { return doc.getElementById(n); },
    caption: function (text, start, end, isFinal) {
      /* A caption event that THROWS inside the panel must be reported as a failed check,
         not kill this process: an uncaught throw here reads as "the mutant went RED"
         when in fact nothing was measured. */
      try {
        bridge.__emit('caption', { text: text, meta: { start: start, end: end, final: Boolean(isFinal) } });
      } catch (err) {
        errors.push('caption emit: ' + (err && err.message));
      }
    },
    status: function (text, kind) { bridge.__emit('status', { text: text, kind: kind || 'busy' }); },
    click: function (el) { el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true })); },
    display: function (el) { return el ? window.getComputedStyle(el).display : 'ABSENT'; },
    text: function (el) { return el ? String(el.textContent).replace(/\s+/g, ' ').trim() : 'ABSENT'; },
    /* The panel row carries the forming cursor as its OWN glyph and the overlay shows the
       sentence without it, so the two surfaces are compared on WORDS. */
    words: function (el) { return this.text(el).replace(/\u258D/g, '').replace(/\s+/g, ' ').trim(); },
  };
}

function runChecks(dir) {
  const p = load(dir);
  const doc = p.document;
  const strip = p.id('strip-controls') || doc.querySelector('.stripbar');
  const floatEl = p.id('caption-float');
  const panelEl = p.id('panel');

  arm = 'SETUP';
  check('SETUP every script ran without throwing', p.errors, []);
  check('SETUP the bar, the overlay and the panel are all in the document',
    [Boolean(strip), Boolean(floatEl), Boolean(panelEl)], [true, true, true]);
  check('SETUP the two probe tokens are absent from the shipped bytes',
    [p.text(doc.body).indexOf(TOKEN1) >= 0, p.text(doc.body).indexOf(TOKEN2) >= 0], [false, false]);

  /* ---------------- ARM A: NO CAPTION TEXT IN THE BAR ---------------- */
  arm = 'A';
  doc.body.setAttribute('data-surface', 'strip');
  p.caption(TOKEN1 + ' primeira linha', 0, 1, true);
  const barStrip = p.text(strip);
  const foundStrip = [TOKEN1, TOKEN2].filter(function (t) { return barStrip.indexOf(t) >= 0; });
  const captionsEl = doc.querySelector('.captions');
  const listRows = doc.querySelectorAll('#caption-list .caption').length;

  check('A1 the bar contains NO caption text after a real caption event', foundStrip, []);
  check('A2 the caption box is display:none on the strip surface', p.display(captionsEl), 'none');
  check('A3 the bar has no caption NODE in its subtree (not just no text)',
    strip.querySelectorAll('.caption, .caption__text, .caption-float, .captions').length, 0);
  check('A4 the caption really landed (the panel row exists)', listRows >= 1, true);

  /* The CONTROL: the same bytes, the other surface. If the tokens cannot be found on
     the PANEL either, A1 passed for the wrong reason and the arm is vacuous. */
  doc.body.setAttribute('data-surface', 'panel');
  const foundPanel = [TOKEN1, TOKEN2].filter(function (t) { return p.text(doc.body).indexOf(t) >= 0; });
  check('A5 CONTROL: the same token IS on the panel surface', foundPanel, [TOKEN1]);
  doc.body.setAttribute('data-surface', 'strip');

  /* ---------------- ARM B: THE LIVE BUTTON, THE SAME LINE, LOOSE ----------------
     RE-BASELINED 2026-10-13 AGAIN, to the contract the Lead re-applied. The caption
     control IS #strip-live-button and the app ships the caption OFF -- the owner's
     own model: *"primeiro, o painel de baixo. NELE EU ATIVO o segundo overlay, q e a
     legenda independente."* So live starts UNPRESSED, the FIRST click puts the
     caption on the screen and the SECOND takes it off, which is the reverse of the
     interim revision this arm used to assert. The overlay is the module's own state
     (caption-float.js) reached through `applyFloat`, and the button, the attribute
     and the overlay are asserted in the SAME click so one fact cannot drift. */
  arm = 'B';
  const btn = p.id('strip-live-button');
  check('B1 the live button is the caption control and ships UNPRESSED (the caption is OFF)',
    [Boolean(btn), btn ? btn.getAttribute('aria-pressed') : 'ABSENT'], [true, 'false']);
  check('B2 the overlay is hidden before the strip repaints', p.display(floatEl), 'none');
  p.click(btn);
  check('B3 live ON puts the caption on the screen (button, attribute and overlay agree)',
    [btn.getAttribute('aria-pressed'), doc.body.getAttribute('data-float'), p.display(floatEl)],
    ['true', 'on', 'block']);
  p.click(btn);
  check('B4 live OFF takes the caption off the screen (button, attribute and overlay agree)',
    [btn.getAttribute('aria-pressed'), doc.body.getAttribute('data-float'), p.display(floatEl)],
    ['false', 'off', 'none']);
  /* Back ON for the loose-caption half below: B6-B13 are all about the overlay while
     the caption is on screen, and B14 is the click that lowers it again. */
  p.click(btn);
  check('B5 the button reports itself pressed', btn.getAttribute('aria-pressed'), 'true');
  const line = p.id('caption-float-line');
  const newest = doc.querySelector('#caption-list .caption:last-child .caption__text');
  check('B6 the overlay paints the SAME words as the panel row', p.words(line), p.words(newest));
  check('B7 and those words are the caption that was pushed', p.text(line), TOKEN1 + ' primeira linha');
  check('B8 the overlay is NOT a descendant of <main class="panel">', panelEl.contains(floatEl), false);
  check('B9 the overlay is click-through (pointer-events:none)', p.window.getComputedStyle(floatEl).pointerEvents, 'none');
  check('B10 the height change reached the bridge as a strip surface',
    p.bridge.__audit.surfaces.filter(function (s) { return s.surface === 'strip' && s.reason.indexOf('float-on') >= 0; }).length >= 1, true);

  /* THE PANEL IS NOT THERE AT ALL. This is the owner's own sentence: the caption has to
     behave "como se nao houvesse painel pra legenda, como ela tivesse solta". */
  /* CAPTURED BEFORE THE REMOVAL: `document.querySelector` does not descend into a
     detached subtree, so asking the document for the row after the panel is gone
     answers null and the comparison would be against nothing at all. */
  const listEl = p.id('caption-list');
  panelEl.remove();
  p.caption(TOKEN2 + ' segunda linha', 5, 7, true);
  const detachedRow = listEl.querySelector('.caption:last-child .caption__text');
  check('B11 with the panel DETACHED the overlay still mirrors the panel row',
    p.words(line), p.words(detachedRow));
  check('B11b and the new words really arrived', p.words(line).indexOf(TOKEN2) >= 0, true);
  check('B12 and it keeps the previous line one back', p.text(p.id('caption-float-prev')), TOKEN1 + ' primeira linha');
  check('B13 the overlay is still display:block with no panel in the document',
    p.display(floatEl), 'block');
  p.click(btn);
  check('B14 the next click lowers it', [doc.body.getAttribute('data-float'), p.display(floatEl)], ['off', 'none']);

  return rows;
}

function report(label) {
  console.log('');
  console.log('S2 BAR / LOOSE CAPTION DOM ORACLE -- ' + label);
  let bad = 0;
  for (const r of rows) { if (!r.ok) bad += 1; }
  console.log(rows.length + ' check(s), ' + bad + ' failed');
  if (bad) {
    console.log('failing:');
    for (const r of rows) { if (!r.ok) console.log('  [' + r.arm + '] ' + r.name); }
  }
  console.log('VERDICT: ' + (bad === 0 ? 'PASS' : 'FAIL'));
  return bad;
}

/* ------------------------------- NEGATIVE ARM ------------------------------- */
if (process.argv.indexOf('--neg-arm') >= 0) {
  const TMP = process.env.TMPDIR && fs.existsSync(process.env.TMPDIR) ? process.env.TMPDIR : os.tmpdir();
  const scratch = fs.mkdtempSync(path.join(TMP, 'sotto-s2-dom-neg-'));
  /* The WHOLE directory, not four files: the document loads eleven scripts and a thin
     copy leaves `window.SottoFormulation` undefined, which throws before any check and
     would have made the mutant look RED for the wrong reason. */
  const copyAll = function () {
    fs.rmSync(scratch, { recursive: true, force: true });
    fs.mkdirSync(scratch, { recursive: true });
    fs.cpSync(SHIPPED, scratch, { recursive: true });
    /* VERIFIED, because a half-copied tree makes a mutant fail for a reason that is not
       the mutation -- measured 2026-10-12: one run lost a module and the panel threw
       before any check. */
    for (const f of ['panel.html', 'panel.css', 'panel.js', 'caption-float.js', 'caption-formulation.js']) {
      const a = fs.readFileSync(path.join(SHIPPED, f));
      const b = fs.readFileSync(path.join(scratch, f));
      if (!a.equals(b)) { console.error('SETUP ERROR: scratch copy of ' + f + ' differs from the shipped bytes'); process.exit(2); }
    }
  };
  const muts = [
    { tag: 'N1 the strip shows its caption box again',
      file: 'panel.css',
      apply: function (t) { return t.replace(/body\[data-surface="strip"\] \.captions \{\s*display: none;/, 'body[data-surface="strip"] .captions { display: block;'); } },
    /* N2 RE-BASELINED 2026-10-13: the overlay's visibility is now the MODULE's own
       inline style (caption-float.js paint()), set through panel.js syncCaptionFloat,
       so the old "delete the CSS display:block rule" mutant no longer moves it. This
       neuters the panel -> overlay call instead, which is the new contract. */
    { tag: 'N2 the live button no longer moves the overlay (the panel->overlay call is neutered)',
      file: 'panel.js',
      apply: function (t) { return t.replace("api.setFloat(state === 'on');", 'void 0;'); } },
    { tag: 'N3 the overlay push is inert',
      file: 'caption-float.js',
      apply: function (t) { return t.replace('push: push', 'push: function () {}'); } },
    { tag: 'N4 the overlay is fed different words than the panel row',
      file: 'panel.js',
      /* BOTH push sites, or the control lies: the forming push runs after the commit push,
         so mutating only the commit site leaves the correct sentence on screen and the
         mutant reads GREEN for a reason that has nothing to do with the arm. */
      apply: function (t) {
        return t
          .replace("window.SottoCaptionFloat.push((confWords.join(' ') + ' ' + provWords.join(' ')).trim(), null)", "window.SottoCaptionFloat.push('MUTANTE-A', null)")
          .replace('window.SottoCaptionFloat.push(text, meta || null)', "window.SottoCaptionFloat.push('MUTANTE-B', meta || null)");
      } },
    /* N5/N6 ARE THE CONTROLS THE 2026-10-13 RE-BASELINE NEEDED, and they break the
       NEW contract, not the old "Linhar button" one. N5 deletes the ONE call that
       makes live-on mean caption-on-screen, so the button/attribute and the overlay
       must disagree on every click (B3/B4/B13/B14). N6 restores the interim default
       (`liveEnabled = true`), so the arm's OWN "ships UNPRESSED" claim (B1) and the
       first-click direction (B3/B4/B5/B14) must go RED. */
    { tag: 'N5 the live button no longer drives the overlay (applyFloat call deleted)',
      file: 'panel.js',
      apply: function (t) { return t.replace(/  applyFloat\(liveEnabled\);\r?\n/, ''); } },
    { tag: 'N6 the caption ships ON again (liveEnabled defaults true)',
      file: 'panel.js',
      apply: function (t) { return t.replace('let liveEnabled = false;', 'let liveEnabled = true;'); } },
  ];
  let wrong = 0;
  for (const m of muts) {
    copyAll();
    const file = path.join(scratch, m.file);
    const before = fs.readFileSync(file, 'utf8');
    const after = m.apply(before);
    if (after === before) { console.error('SETUP ERROR: mutant anchor did nothing in ' + m.file + ': ' + m.tag); process.exit(2); }
    fs.writeFileSync(file, after, 'utf8');
    rows.length = 0;
    /* `runChecks` returns the ROW LIST; the count is a filter, not the array. Comparing
       the array itself to 0 is always false, which made every mutant print GREEN. */
    const bad = runChecks(scratch).filter(function (r) { return !r.ok; }).length;
    const red = bad > 0;
    if (!red) wrong += 1;
    console.log('  ' + (red ? 'RED  ' : 'GREEN') + '  ' + m.tag + '  -> ' + bad + ' failing check(s)');
  }
  fs.rmSync(scratch, { recursive: true, force: true });
  console.log('');
  console.log(wrong === 0 ? 'NEG-ARM VERDICT: PASS -- every mutant went RED.' : 'NEG-ARM VERDICT: FAIL -- ' + wrong + ' mutant(s) stayed GREEN.');
  process.exit(wrong === 0 ? 0 : 1);
}

const bad = runChecks(SHIPPED);
process.exit(report('shipped app/panel') === 0 ? 0 : 1);
