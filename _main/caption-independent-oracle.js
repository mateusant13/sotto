/* caption-independent-oracle.js -- THE LANE CAPTION GATE (2026-10-12).
 *
 * THE OWNER'S THREE DEMANDS, verbatim, and the check that answers each:
 *   "a porra da legenda, e pra ser independente do painel, nao acoplado."
 *        -> ARM A: the overlay paints with NO panel in the document at all, owns its
 *           own state (show/hide), and -- in the host that owns a caption window --
 *           the PAGE asks the SHELL and paints NOTHING itself. The page's own
 *           overlay is the FALLBACK, for a host with no caption window.
 *   "e eu to vendo div com cor solida inves de invisivel."
 *        -> ARM B: neither the overlay, nor a descendant, paints a background. The
 *           one body is the 4px left bar. The PAGE behind it keeps its own OPAQUE
 *           base -- that is the RENDER PROTECTION, not a defect.
 *
 * RE-BASELINED 2026-10-20 (lane caption). THE CONTRACT MOVED ON 2026-10-17, and the
 * ten arms that were red were measuring a contract the product DELETED on purpose:
 * the caption is a NATIVE WINDOW (`NativeCaptionOverlay`, a topmost Win32 window on
 * the desktop -- panel.js:2702-2710), the page's own overlay is the FALLBACK for a
 * host with no caption window (panel.js:2712-2716), and the panel's dark base is
 * THE RENDER PROTECTION (panel.css:105-127) -- `caption-float.css` DELETED its
 * `html[data-float="on"] { background: transparent }` rule on purpose, because a
 * transparent page inside an opaque WinForms window IS the white slab the owner
 * reported. The arms below measure what the product does TODAY, on BOTH hosts.
 *
 * RE-BASELINED 2026-11-25 (the caption left the page). The shipped panel.html does
 * NOT link `caption-float.js`, `caption-float.css` or `letter-swap.js`: the caption
 * is NativeCaptionOverlay on the desktop and the button's only caption door is
 * `bridge.setLiveEnabled`. A18 therefore checks the PANEL ROW carries the bridge
 * words and that the page paints no overlay -- the behaviour `_s2-bar-dom-oracle.js`
 * arm B7 measures. A21b/A23b are now labelled honestly: they probe the RETIRED
 * module, which this harness loads explicitly (panel.html does not). A21c/A23c
 * assert what the SHIPPED fallback host does: the panel row plus no native door.
 * N13 breaks the row writer and must redden the new arms.
 *   "e nao e pra mudanca de design/tema/template ficar scrollando pra cima. e sempre
 *    mostrando o bottom do historico de transcript."
 *        -> ARM C: after a theme write, a skin write and a stylesheet load, the
 *           transcript container is at scrollTop === scrollHeight.
 *
 * HOW IT MEASURES. jsdom (the same harness _main/_s2-bar-dom-oracle.js uses): the real
 * panel.html, the real panel.css + caption-float.css inlined in that order, the
 * document's OWN script list run in order against a bridge stub, then real caption
 * events and real attribute writes through the panel's own choke points. No window, no
 * WebView2, no audio, no network, no launch of anything.
 *
 * THE CONTROL ARM (--neg-arm) is the point of the file: thirteen mutants, one at a time,
 * each applied to a fresh copy of app/panel, and the SAME checks re-run. Every mutant
 * must go RED. N13 deletes the panel row's word writer, so the rebaselined A18, A21c
 * and A23c claims go RED when the caption stops reaching the shipped row; N5 is the
 * owner's own coupling restored (the module can no longer build its own overlay).
 *
 *   node _main/caption-independent-oracle.js            A18/A21c/A23c GREEN; seven
 *                                                       pre-existing B/C arms RED at HEAD
 *   node _main/caption-independent-oracle.js --neg-arm  every mutant RED, rc=0

 * Exit codes: 0 as above | 1 a check failed | 2 setup error (jsdom absent, a file
 * missing, a mutant anchor absent).
 */
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (err) {
  console.log('SETUP ERROR: jsdom is required for this oracle (' + (err && err.message) + ').');
  process.exit(2);
}

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const PANEL = path.join(REPO, 'app', 'panel');
const NEG = process.argv.indexOf('--neg-arm') >= 0;

const TOKEN_A = 'quixotescamente';
const TOKEN_B = 'vulcanizadissimo';
const TOKEN_C = 'epistemologicamente';

const rows = [];
let arm = '';

function check(name, real, want, control) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  const differs = control === undefined || JSON.stringify(real) !== JSON.stringify(control);
  const good = ok && differs;
  rows.push({ arm: arm, name: name, ok: good, real: JSON.stringify(real), want: JSON.stringify(want) });
  console.log('  [' + (good ? 'PASS' : 'FAIL') + '] ' + name);
  console.log('         real = ' + JSON.stringify(real) + '   want = ' + JSON.stringify(want));
  return good;
}
function checkTrue(name, real) { return check(name, real, true); }

function scriptSources(html) {
  return Array.from(html.matchAll(/<script\s+src="([^"]+)"[^>]*><\/script>/g)).map(function (m) { return m[1]; });
}

function pad2(n) { return String(n).padStart(2, '0'); }
function isoLocal(d) {
  return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate())
    + 'T' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
}

/* A store with real entries, two hours old, so the gallery paints a day bucket and
   the feed can hold rows. Times are LOCAL and built from NOW, so the 24 h range in
   history-gallery.js always contains them. */
function historyEntries(count) {
  const out = [];
  for (let i = 0; i < count; i += 1) {
    const when = new Date(Date.now() - (i + 1) * 60 * 1000);
    const iso = isoLocal(when);
    // THE STORE'S OWN SHAPE: history-gallery.js entryStamp() reads entry.date and
    // entry.time SEPARATELY (history-gallery.js:60-69), so an entry with only an ISO
    // time is dropped as unreadable and the gallery paints nothing.
    out.push({
      date: iso.slice(0, 10),
      time: iso.slice(11),
      text: 'linha numero ' + (i + 1) + ' do historico',
      path: 'H:/sotto/history/x.md',
    });
  }
  return out;
}

function bridgeStub(window, entries, opts) {
  const subs = { caption: [], status: [] };
  const liveCalls = [];
  const bridge = {
    onCaption: function (cb) { subs.caption.push(cb); },
    onStatus: function (cb) { subs.status.push(cb); },
    onGeometry: function () {},
    hide: function () {}, toggle: function () {}, quit: function () {}, setPointerInteractive: function () {},
    captionApplied: function () {}, statusApplied: function () {}, ready: function () {}, clearApplied: function () {},
    getInfo: function () { return Promise.resolve({ hotkey: 'Alt+C', versions: { shell: 'caption-oracle' } }); },
    HOTKEY: 'Alt+C',
    platform: 'win32',
    history: {
      append: function () { return Promise.resolve({ entry: null }); },
      tail: function () { return Promise.resolve({ entries: entries, root: 'H:/sotto/history', canonicalProducer: 'redux' }); },
      search: function () { return Promise.resolve({ hits: [] }); },
      root: function () { return Promise.resolve({ root: 'H:/sotto/history', canonicalProducer: 'redux' }); },
      reveal: function () {},
    },
    /* ECHOES the requested value, which is what the real shell does (it returns the
       state it confirmed). It used to answer `true` unconditionally, and under the
       caption-OFF contract that made the first click's resolved promise "correct" the
       second click back ON asynchronously -- the stub, not the panel, was moving the
       overlay. An oracle whose stub lies about its own reply cannot decide the state. */
    setLiveEnabled: function (on) { liveCalls.push(Boolean(on)); return Promise.resolve({ liveEnabled: Boolean(on) }); },
    pause: function () { return Promise.resolve({ paused: true }); },
    setPanelSurface: function (name) {
      if (window.SottoSurfaces) window.SottoSurfaces.set(String(name));
      return Promise.resolve({ surface: String(name) });
    },
    __emit: function (kind, payload) { for (const cb of subs[kind]) cb(payload); },
    /* EVERY ASK THE PAGE MADE OF THE SHELL'S CAPTION WINDOW, in order. The native
       contract is "the page asks, the shell moves the window" -- and an arm that
       cannot see the ASK cannot say the page asked. */
    __liveCalls: liveCalls,
  };
  /* THE FALLBACK HOST (2026-10-17). A shell with NO caption window of its own -- a
     browser probe (`_main/panel-caption-button-probe.mjs`) -- does not ship
     `setLiveEnabled`, and there the page's own overlay IS the caption
     (panel.js:2712-2716). The stub can drop the method so the gate measures BOTH
     paths: a harness that always had it measured the fallback branch on paper and
     the native branch in fact. */
  if (opts && opts.noLive) delete bridge.setLiveEnabled;
  window.sotto = bridge;
  return bridge;
}

function loadPanel(dir, opts) {
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
  /* zip-overlay.css IS IN THE POPULATION NOW (2026-10-20). It was NOT, and that is
     exactly why this gate was a FALSE GREEN for the caption-window defect: the
     three rules it carries (the transparent base, the shadow, the display:none)
     lived in THAT sheet, and a harness that never loads it cannot see them.
     Order = the order panel.html loads them (panel.css, caption-float.css,
     then zip-overlay.css last). */
  const zipCssPath = path.join(dir, 'zip-overlay.css');
  const zipCss = fs.existsSync(zipCssPath) ? fs.readFileSync(zipCssPath, 'utf8') : '';
  style.textContent = css + '\n' + floatCss + '\n' + zipCss;
  window.document.head.prepend(style);
  const bridge = bridgeStub(window, historyEntries(12), opts);
  const errors = [];
  for (const src of scriptSources(html)) {
    const file = path.resolve(dir, src);
    if (!fs.existsSync(file)) { errors.push('missing ' + src); continue; }
    try { window.eval(fs.readFileSync(file, 'utf8')); } catch (err) { errors.push(src + ': ' + (err && err.message)); }
  }
  try { window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true })); }
  catch (err) { errors.push('DOMContentLoaded: ' + (err && err.message)); }
  /* 2026-11-25: panel.html no longer loads caption-float.js (the caption on screen
     is NativeCaptionOverlay). THIS gate still tests the module itself, so it loads
     that module explicitly into the harness; A1 now asserts the shipped document
     does NOT link it. The product bytes are read, never edited. */
  try { window.eval(fs.readFileSync(path.join(dir, 'caption-float.js'), 'utf8')); }
  catch (err) { errors.push('caption-float.js (harness-loaded): ' + (err && err.message)); }
  const doc = window.document;
  return {
    window: window, document: doc, bridge: bridge, errors: errors,
    id: function (n) { return doc.getElementById(n); },
    q: function (s) { return doc.querySelector(s); },
    qa: function (s) { return Array.from(doc.querySelectorAll(s)); },
    display: function (el) { return el ? window.getComputedStyle(el).display : 'ABSENT'; },
    bg: function (el) { return el ? window.getComputedStyle(el).backgroundColor : 'ABSENT'; },
    bgImage: function (el) { return el ? window.getComputedStyle(el).backgroundImage : 'ABSENT'; },
    text: function (el) { return el ? String(el.textContent).replace(/\s+/g, ' ').trim() : 'ABSENT'; },
    caption: function (text, start, end, isFinal) {
      try { bridge.__emit('caption', { text: text, meta: { start: start, end: end, final: Boolean(isFinal) } }); }
      catch (err) { errors.push('caption emit: ' + (err && err.message)); }
    },
    click: function (el) { if (el) el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true })); },
    tick: function () { return new Promise(function (r) { setTimeout(r, 0); }); },
    defineScroll: function (el, height, client) {
      if (!el) return false;
      Object.defineProperty(el, 'scrollHeight', { value: height, configurable: true });
      Object.defineProperty(el, 'clientHeight', { value: client, configurable: true });
      return true;
    },
  };
}

function lastRowText(p) {
  /* The provisional caret is a rendering mark from the engine's held tail, not
     one of the words the bridge wrote; the shipped row text is compared without
     it, exactly as `_s2-bar-dom-oracle.js` arm B7 compares its newest row. */
  return p.text(p.q('#caption-list .caption:last-child .caption__text')).replace(/\s*▍$/, '');
}

/* ── THE CSS DECLARATION SCAN (arm B2) ────────────────────────────────────────
 * A real rule parser: comments stripped, selector lists kept whole, nested at-rules
 * walked by depth. Then every rule whose selector can match the overlay or one of its
 * descendants is asked what it paints. The one allowed painter is the left bar. */
function parseCss(css) {
  const src = css.replace(/\/\*[\s\S]*?\*\//g, ' ');
  const out = [];
  let i = 0, buf = '', depth = 0, sel = null;
  const flush = function () {
    if (sel == null) return;
    const decls = {};
    for (const d of buf.split(';')) {
      const c = d.indexOf(':');
      if (c > 0) decls[d.slice(0, c).trim().toLowerCase()] = d.slice(c + 1).trim();
    }
    out.push({ selector: sel.trim(), members: sel.split(',').map(function (s) { return s.trim(); }), decls: decls });
    sel = null; buf = '';
  };
  while (i < src.length) {
    const ch = src[i];
    if (ch === '{') { depth += 1; if (depth === 1) { sel = buf; buf = ''; } i += 1; continue; }
    if (ch === '}') { depth -= 1; if (depth === 0) flush(); i += 1; continue; }
    if (depth === 1) buf += ch; else if (depth === 0) buf += ch;
    i += 1;
  }
  return out;
}

const PAINT_PROPS = ['background', 'background-color', 'background-image', 'box-shadow', 'backdrop-filter', 'outline'];
const PAINT_OK = ['none', 'transparent', 'inherit', 'initial', 'unset'];

function memberTouchesFloat(member) {
  return member.indexOf('.caption-float') >= 0 || member.indexOf('#caption-float') >= 0;
}
/* A selector with NO class, id or attribute constraint: only these can match an
   element inside the overlay without naming it. '.listening span' cannot — the
   overlay has no .listening ancestor — so it is not this overlay's business. */
function memberIsConstraintFree(member) {
  return /^(\*|html|body|div|p|span)(\s*[>+~]?\s*(\*|html|body|div|p|span))*$/.test(member);
}
function memberIsLed(member) {
  return member.indexOf('.caption-float__led') >= 0;
}
/* THE PANEL'S OWN METER PLATE (2026-11-25). `panel.css:3319-3336` gives
   `.caption-float__meter` a plate and `.caption-float__meter-fill` the theme
   gradient ON PURPOSE -- the listening meter is panel chrome, hidden until
   `.is-on` sets `opacity: 1`, and it is NOT the caption text. The retired
   `caption-float.css` used to neutralise these two rules, and `panel.html` no
   longer loads that sheet, so crediting it as the cure was fiction. They are
   ALLOWED here by name, exactly like the left bar; B4/B5 still measure that the
   meter is invisible and takes no room in the panel. */
function memberIsMeter(member) {
  return member.indexOf('.caption-float__meter') >= 0;
}
/* THE PAGE'S OWN BASE (html / body). 2026-10-17: the caption is a native window,
   so the page behind it is the panel, and the panel's base is the render
   protection. A rule that paints <html>/<body> is the page's own business, not
   the overlay's -- and B3/B3b hold the base to its real contract. */
function memberIsPageBase(member) {
  const key = targetKey(member);
  return key === 'html' || key === 'body';
}
function paintsValue(prop, value) {
  const v = String(value).trim().toLowerCase();
  if (PAINT_OK.indexOf(v) >= 0) return false;
  if (prop === 'outline' && (v === '0' || v === '0px' || v === 'hidden' || v === 'none 0')) return false;
  return true;
}
/** [ids, classes+attributes+pseudo-classes, elements+pseudo-elements] of one member. */
function specificity(member) {
  const ids = (member.match(/#[A-Za-z0-9_-]+/g) || []).length;
  const classes = (member.match(/\.[A-Za-z0-9_-]+|\[[^\]]+\]|:(?!:)[a-z-]+/g) || []).length;
  const elements = (member.match(/(^|[\s>+~])([a-z][a-z0-9-]*|\*)/g) || []).length;
  return [ids, classes, elements];
}
function specGte(a, b) {
  for (let i = 0; i < 3; i += 1) { if (a[i] !== b[i]) return a[i] > b[i]; }
  return true;
}
/** The class/id token a member's LAST compound constrains (the element it paints). */
function targetToken(member) {
  const last = member.split(/[\s>+~]+/).pop();
  const m = last.match(/[.#][A-Za-z0-9_-]+/);
  return m ? m[0] : null;
}
/** Does a candidate rule target the SAME element as the offender? */
function keyMatches(member, key) {
  if (key === null) return false;
  if (key === '*') return true;
  if (key.charAt(0) === '.' || key.charAt(0) === '#') return member.indexOf(key) >= 0;
  return new RegExp('(^|[\\s>+~])' + key + '([\\s>+~.#:\\[]|$)').test(member);
}
/** The element key of a member's last compound: '.cls', '#id' or a bare tag name. */
function targetKey(member) {
  const token = targetToken(member);
  if (token) return token;
  const last = member.split(/[\s>+~]+/).pop()
    .replace(/\[[^\]]*\]/g, '')
    .replace(/::?[a-z-]+(\([^)]*\))?/g, '');
  return last === '' ? null : last.toLowerCase();
}

/* THE POPULATION: the stylesheets the DOCUMENT actually loads. panel.html's own
   links, plus the lazy manifest lazy-assets.js injects on a theme/template switch,
   plus this lane's own file. The skin stylesheets under skins/ are attached inside a
   SHADOW ROOT (skin-host.js:88-91), so a rule like 'body { background: #0a0d10 }' in
   one of them matches nothing on this page and is not this overlay's business. */
function documentSheets(dir) {
  const html = fs.readFileSync(path.join(dir, 'panel.html'), 'utf8');
  const names = new Set();
  for (const m of html.matchAll(/<link[^>]+rel="stylesheet"[^>]*href="([^"]+)"/g)) names.add(m[1]);
  const lazyPath = path.join(dir, 'lazy-assets.js');
  if (fs.existsSync(lazyPath)) {
    for (const m of fs.readFileSync(lazyPath, 'utf8').matchAll(/'([^']+\.css)'/g)) names.add(m[1]);
  }
  /* 2026-11-25: this line forced `caption-float.css` into the population even
     though `panel.html` does not link it any more (the in-page float caption left
     this document). A sheet the document does NOT load cannot paint it, so forcing
     it made B2 report an offender the page never sees. The population is now
     exactly what `panel.html` (plus the lazy manifest) loads. */
  const out = [];
  for (const n of names) {
    const p = path.join(dir, n);
    if (fs.existsSync(p)) out.push(p);
  }
  return out;
}

function cssFiles(dir) {
  const out = [];
  (function walk(d) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) { if (e.name === 'fonts' || e.name === '_fonts') continue; walk(p); }
      else if (/\.css$/.test(e.name)) out.push(p);
    }
  })(dir);
  return out;
}

/*
 * THE CLAIM THIS MEASURES: every rule that paints on the overlay or a descendant is
 * either (a) this lane's own rule on the LEFT BAR — the one body the owner asked for
 * — or (b) neutralised by a rule in caption-float.css that targets the same element
 * with the same property and a specificity at least as high. jsdom does NOT resolve
 * var(), so a var()-valued background is invisible to the computed-style arm (B1);
 * this scan is what covers it, by proving the override exists in the cascade.
 */
function paintScan(dir) {
  const ownPath = path.join(dir, 'caption-float.css');
  const sheets = documentSheets(dir);
  /* THE NEUTRALISER IS ANY RULE THE DOCUMENT REALLY LOADS (2026-11-25). This used to
     search `caption-float.css` only, and `panel.html` no longer links that sheet --
     so a paint that the loaded sheets DO neutralise (`.caption-float__meter` is
     transparent in the resolved style, arm B4) was counted as an offender while a
     rule in a file the page never loads was counted as its cure. The scan now walks
     the loaded sheets in document order and applies the cascade it can defend: a
     later rule of equal specificity wins, an earlier rule only wins if it is more
     specific. */
  const flat = [];
  for (const f of sheets) {
    for (const rule of parseCss(fs.readFileSync(f, 'utf8'))) {
      for (const member of rule.members) flat.push({ file: f, member: member, decls: rule.decls });
    }
  }
  const offends = function (item, prop) {
    if (!(prop in item.decls)) return false;
    return paintsValue(prop, item.decls[prop]);
  };
  const neutralises = function (item, prop) {
    const direct = item.decls[prop];
    if (direct !== undefined && !paintsValue(prop, direct)) return true;
    const shorthand = item.decls.background;
    return shorthand !== undefined && !paintsValue('background', shorthand);
  };
  const offenders = [];
  const covered = [];
  const allowed = [];
  const scanned = flat.length;
  for (let i = 0; i < flat.length; i += 1) {
    const item = flat[i];
    if (!memberTouchesFloat(item.member) && !memberIsConstraintFree(item.member)) continue;
    /* THE PAGE'S OWN BASE IS NOT THE OVERLAY'S BUSINESS (2026-10-17). The caption
       is a NATIVE WINDOW; the page behind it is the PANEL, and the panel's dark
       base is THE RENDER PROTECTION (panel.css:105-127). So the base is not an
       offender; the compensating arms are B3 (body IS opaque) and B3b (nothing may
       make it transparent again). */
    if (memberIsPageBase(item.member)) continue;
    for (const prop of PAINT_PROPS) {
      if (!offends(item, prop)) continue;
      const entry = path.basename(item.file) + ' :: ' + item.member + ' { ' + prop + ': ' + item.decls[prop] + ' }';
      // THE ALLOWED PAINTERS, whichever sheet declares them: the 4px left bar and
      // the panel's own listening meter (see `memberIsMeter`).
      if (memberIsLed(item.member) || memberIsMeter(item.member)) { allowed.push(entry); continue; }
      const token = targetKey(item.member);
      const mine = specificity(item.member);
      let neutral = false;
      for (let j = 0; j < flat.length && !neutral; j += 1) {
        if (j === i) continue;
        const cand = flat[j];
        if (!keyMatches(cand.member, token)) continue;
        if (!specGte(specificity(cand.member), mine)) continue;
        const same = JSON.stringify(specificity(cand.member)) === JSON.stringify(mine);
        // Equal specificity: only a LATER rule in document order can win.
        if (same && j < i) continue;
        if (neutralises(cand, prop)) neutral = true;
      }
      if (neutral) covered.push(entry); else offenders.push(entry);
    }
  }
  return { offenders: offenders, covered: covered, allowed: allowed, scanned: scanned,
           sheets: sheets.map(function (f) { return path.basename(f); }) };
}

/* The FEED render path, read out of the real file by brace matching: the check is
   that it pins to the bottom and never writes 0. */
function functionSource(text, name) {
  const at = text.indexOf('function ' + name + '(');
  if (at < 0) return null;
  let i = text.indexOf('{', at), depth = 0;
  for (; i < text.length; i += 1) {
    if (text[i] === '{') depth += 1;
    else if (text[i] === '}') { depth -= 1; if (depth === 0) return text.slice(at, i + 1); }
  }
  return null;
}

async function runChecks(dir) {
  const p = loadPanel(dir);
  const doc = p.document;
  const win = p.window;
  const floatEl = p.id('caption-float');
  const panelEl = p.id('panel');
  const api = win.SottoCaptionFloat;

  arm = 'SETUP';
  check('SETUP every script ran without throwing', p.errors, []);
  checkTrue('SETUP the overlay, the panel and the strip bar are in the document',
    Boolean(floatEl) && Boolean(panelEl) && Boolean(p.id('strip-live-button')));
  checkTrue('SETUP the two probe tokens are absent from the shipped bytes',
    p.text(doc.body).indexOf(TOKEN_A) < 0 && p.text(doc.body).indexOf(TOKEN_B) < 0);
  checkTrue('SETUP caption-float.js registered window.SottoCaptionFloat', Boolean(api));
  checkTrue('SETUP caption-float.css exists and is non-empty',
    fs.existsSync(path.join(dir, 'caption-float.css')) && fs.readFileSync(path.join(dir, 'caption-float.css'), 'utf8').length > 500);

  /* ── A. INDEPENDENT OF THE PANEL ─────────────────────────────────────────── */
  arm = 'A';
  /* The module links its OWN stylesheet when it registers, so the live DOM has a
     link even though the SHIPPED document does not. Measure the shipped bytes. */
  const shippedHtml = fs.readFileSync(path.join(dir, 'panel.html'), 'utf8');
  const linkedInHtml = shippedHtml.indexOf('href="caption-float.css"') >= 0;
  check('A1 the shipped panel.html no longer links caption-float.css (the harness loads the module)',
    linkedInHtml, false);
  check('A2 the overlay is hidden before anyone asks for it', p.display(floatEl), 'none');

  /* THE PANEL IS GONE. The owner: the caption has to be able to sit on the screen
     "sem o painel estar montado nem visivel". */
  panelEl.remove();
  doc.body.setAttribute('data-surface', 'strip');
  api.show();
  /* RE-BASELINED 2026-10-13: the app ships the caption OFF, so the module's own
     state is false when this arm runs and show() is a REAL transition (its documented
     return is "did the state change"). The claim is that the overlay is PAINTED, which
     state().painted and the resolved display both measure -- it does not depend on
     which way show() came. */
  check('A3 show() with the panel DETACHED paints the overlay',
    [api.state().painted, p.display(floatEl)], [true, 'block']);
  api.push(TOKEN_B, null);
  check('A4 and it paints the text', p.text(p.id('caption-float-line')), TOKEN_B);
  check('A5 the module knows it is standalone', api.state().standalone, true);

  /* A DOCUMENT WITH NO PANEL AT ALL, which is the honest form of the demand: only
     caption-float.js, a body, and the shell bridge. */
  const soloDom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
    url: 'file:///sotto-standalone/index.html', runScripts: 'outside-only', pretendToBeVisual: true,
  });
  const soloWin = soloDom.window;
  const soloErrors = [];
  bridgeStub(soloWin, []);
  try { soloWin.eval(fs.readFileSync(path.join(dir, 'caption-float.js'), 'utf8')); }
  catch (err) { soloErrors.push(String(err && err.message)); }
  const soloApi = soloWin.SottoCaptionFloat;
  check('A6 a document with no panel loads the module', soloErrors, []);
  const soloLinks = function () {
    return Array.from(soloWin.document.querySelectorAll('link[rel="stylesheet"]')).filter(function (l) {
      return String(l.getAttribute('href') || '').indexOf('caption-float.css') >= 0;
    });
  };
  check('A6b the module INJECTS its stylesheet where the document does not link it',
    [soloLinks().length, soloLinks().length === 1 ? String(soloLinks()[0].getAttribute('href')) : 'ABSENT'],
    [1, 'caption-float.css']);
  soloWin.eval(fs.readFileSync(path.join(dir, 'caption-float.js'), 'utf8'));
  check('A6c and a second load of the module does not add a second link', soloLinks().length, 1);
  checkTrue('A7 the module CREATES the overlay it does not find',
    Boolean(soloWin.document.getElementById('caption-float')));
  soloApi.push(TOKEN_C, null);
  soloApi.show();
  const soloHost = soloWin.document.getElementById('caption-float');
  const soloLine = soloWin.document.getElementById('caption-float-line');
  check('A8 and paints it, with no panel and no strip surface',
    [soloHost ? soloWin.getComputedStyle(soloHost).display : 'ABSENT',
     soloLine ? String(soloLine.textContent) : 'ABSENT'],
    ['block', TOKEN_C]);
  check('A9 with no panel it feeds itself from the shell bridge', soloApi.state().feed, 'self');
  soloWin.sotto.__emit('caption', { text: TOKEN_A + ' pela ponte', meta: { start: 1 } });
  const soloLine2 = soloWin.document.getElementById('caption-float-line');
  check('A10 a bridge caption reaches the standalone overlay',
    soloLine2 ? String(soloLine2.textContent) : 'ABSENT', TOKEN_A + ' pela ponte');
  check('A11 the standalone overlay mirrors its state onto <html> (the shell reads it there)',
    soloWin.document.documentElement.getAttribute('data-float'), 'on');
  const soloHost2 = soloWin.document.getElementById('caption-float');
  check('A12 the standalone overlay hides again on hide()',
    [soloApi.hide(), soloHost2 ? soloWin.getComputedStyle(soloHost2).display : 'ABSENT'],
    [true, 'none']);

  /* BACK IN THE PANEL DOCUMENT: the button, the state, and the one feed. */
  const p2 = loadPanel(dir);
  const doc2 = p2.document;
  const floatEl2 = p2.id('caption-float');
  doc2.body.setAttribute('data-surface', 'strip');
  const btn = p2.id('strip-live-button');
  /* RE-BASELINED 2026-10-13 AGAIN, to the contract the Lead re-applied. The caption
     control IS #strip-live-button and the app ships the caption OFF (the owner turns
     the second overlay on FROM the bottom panel: *"NELE EU ATIVO o segundo
     overlay"*). So A13 asserts UNPRESSED, A13b is the click that puts the caption ON,
     the panel-surface arm runs while it is ON, and A13c is the click that takes it
     OFF again -- the reverse of the interim revision. */
  check('A13 the live button is the caption control and ships UNPRESSED (the caption is OFF)',
    btn ? btn.getAttribute('aria-pressed') : 'ABSENT', 'false');
  /* RE-BASELINED 2026-10-20 (lane caption). THE CONTRACT MOVED ON 2026-10-17: the
     caption is a NATIVE WINDOW and the PAGE's own overlay is the fallback. With a
     shell that owns a caption window, `applyFloat` returns at its first line
     (panel.js:2729) and the page paints NOTHING; the only door to the caption is
     `requestCaptionOverlay` -> `bridge.setLiveEnabled` (panel.js:2218-2240). The
     old arms demanded "clicking live ON puts the caption on the strip screen" and
     "the page writes data-float" -- a contract the product DELETED on purpose --
     and the button is now painted from the SHELL's own account
     (`data-caption-window` on <html>, panel.js:700, :2450-2468), never from a
     local wish. The arms below measure what the page does TODAY. */
  p2.click(btn);
  await p2.tick();
  check('A13b clicking live ON asks the SHELL for its caption window and the PAGE paints nothing',
    [p2.bridge.__liveCalls.slice(), btn.getAttribute('aria-pressed'),
     doc2.body.getAttribute('data-float'), p2.display(floatEl2)],
    [[true], 'false', null, 'none']);
  /* THE SHELL'S OWN ACCOUNT. This is the write the shell makes when the window is
     really up; the button is painted FROM it, which is why the page's own state
     never has to be a guess. */
  doc2.documentElement.setAttribute('data-caption-window', 'on');
  await p2.tick();
  check('A13c the shell own write paints the button ON and the PAGE still paints no overlay',
    [btn.getAttribute('aria-pressed'), doc2.body.getAttribute('data-float'), p2.display(floatEl2)],
    ['true', null, 'none']);
  check('A14 the page NEVER floats itself (documentElement[data-float] is the module own state, not the caption)',
    doc2.documentElement.getAttribute('data-float'), 'off');
  check('A15 and the page writes no float attribute on its own body (the caption is not in this window)',
    doc2.body.getAttribute('data-float'), null);
  check('A16 with a panel mounted the module does NOT feed itself (no double paint)',
    p2.window.SottoCaptionFloat.state().feed, 'panel');
  checkTrue('A17 the overlay is not inside the panel div', !p2.id('panel').contains(floatEl2));
  p2.caption(TOKEN_A + ' uma linha', 0, 1, true);
  check('A18 one bridge caption lands in the PANEL row once (the native window is the only caption on screen)',
    [lastRowText(p2), p2.display(floatEl2), p2.bridge.__liveCalls.slice()],
    [TOKEN_A + ' uma linha', 'none', [true]]);
  doc2.body.setAttribute('data-surface', 'panel');
  await p2.tick();
  check('A19 on the FULL panel surface the page paints no overlay either (the caption is the shell own window)',
    [doc2.body.getAttribute('data-float'), p2.display(floatEl2)], [null, 'none']);
  doc2.body.setAttribute('data-surface', 'strip');
  await p2.tick();
  check('A20 and on the strip the page still paints no overlay (the caption lives in the shell own window)',
    p2.display(floatEl2), 'none');
  p2.click(btn);
  await p2.tick();
  check('A13d clicking live OFF asks the shell to take the caption window down',
    [p2.bridge.__liveCalls.slice(), btn.getAttribute('aria-pressed'), p2.display(floatEl2)],
    [[true, false], 'true', 'none']);
  doc2.documentElement.setAttribute('data-caption-window', 'off');
  await p2.tick();
  check('A13e and the shell own write paints the button OFF again',
    [btn.getAttribute('aria-pressed'), p2.display(floatEl2)], ['false', 'none']);
  /* A22 -- ADDED 2026-10-20. THE STRIP MUST NOT RESERVE A HEIGHT FOR A CAPTION
     THAT IS NOT PAINTED.
     `documentElement[data-float]` is what the SHELL reads to size the strip
     (sotto_webview.py:6527 and :6579). The page's overlay is not painted in this
     document -- the shell owns the caption window (`data-caption-window` is
     present), so the overlay stays hidden -- and therefore the strip must be told
     "off", or the window grows a strip for a caption that is not there.
     The attribute follows WHAT IS PAINTED (`want`), not the module's own switch
     (`on`). N11 puts the switch back and this arm must go RED. */
  check('A22 the strip is NOT told to reserve a height for a caption this document does not paint',
    [doc2.documentElement.getAttribute('data-float'), p2.display(floatEl2)], ['off', 'none']);

  /* THE FALLBACK HOST. A shell with NO caption window of its own -- a browser
     probe (`_main/panel-caption-button-probe.mjs`) -- does not ship
     `setLiveEnabled`. The retired page overlay is NOT linked by the shipped
     document; this harness still loads the module explicitly to probe the module
     itself (A21b/A23b). What SHIPS in this host is the panel row (A21c/A23c) and
     the strip attribute, not a caption painted by this document. N7 still has
     teeth here: with `applyFloat(liveEnabled)` deleted, the attribute never comes
     up, while the row alone would still carry the words. */
  const p3 = loadPanel(dir, { noLive: true });
  const doc3 = p3.document;
  const floatEl3 = p3.id('caption-float');
  doc3.body.setAttribute('data-surface', 'strip');
  const btn3 = p3.id('strip-live-button');
  check('A21 THE FALLBACK host ships the caption OFF', btn3.getAttribute('aria-pressed'), 'false');
  p3.click(btn3);
  await p3.tick();
  check('A21b MODULE PROBE: the harness-loaded retired module follows the fallback button (not a shipped caption)',
    [btn3.getAttribute('aria-pressed'), doc3.body.getAttribute('data-float'), p3.display(floatEl3)],
    ['true', 'on', 'block']);
  p3.caption(TOKEN_A + ' fallback', 0, 1, true);
  check('A21c SHIPPED fallback: the PANEL row carries the caption and no native door was asked',
    [lastRowText(p3), p3.bridge.__liveCalls.length], [TOKEN_A + ' fallback', 0]);
  /* A23 -- ADDED 2026-10-20. THE ATTRIBUTE FOLLOWS WHAT IS PAINTED, NOT THE SWITCH.
     This is the state where the two DIFFER, and it is reachable: the fallback
     host with the FULL PANEL surface. The module's switch is ON (`on === true`,
     the button is pressed and `body[data-float]` is "on"), but the overlay must
     NOT paint -- the panel surface already shows the same words, so a second copy
     would be painted on top of them.
     `documentElement[data-float]` is what the SHELL reads to size the strip
     (sotto_webview.py:6527 and :6579), so it must say what is ON THE SCREEN.
     Before this rule it followed the module's own switch, and the strip was told
     to reserve a height for a caption that was not painted.
     N11 puts the switch back and this arm must go RED. */
  doc3.body.setAttribute('data-surface', 'panel');
  await p3.tick();
  check('A23 the strip is NOT told to reserve a height for a caption this document does not paint',
    [doc3.documentElement.getAttribute('data-float'), p3.display(floatEl3)], ['off', 'none']);
  doc3.body.setAttribute('data-surface', 'strip');
  await p3.tick();
  check('A23b MODULE PROBE: the harness-loaded retired module follows its switch again (not a shipped caption)',
    [doc3.documentElement.getAttribute('data-float'), p3.display(floatEl3)], ['on', 'block']);
  check('A23c SHIPPED fallback: the PANEL row still carries the caption on both surfaces',
    [lastRowText(p3), p3.bridge.__liveCalls.length], [TOKEN_A + ' fallback', 0]);

  /* ── B. NOTHING PAINTS ───────────────────────────────────────────────────── */
  arm = 'B';
  const subtree = [floatEl2].concat(floatEl2 ? Array.from(floatEl2.querySelectorAll('*')) : []).filter(Boolean);
  const painters = subtree.filter(function (el) {
    const bg = p2.window.getComputedStyle(el).backgroundColor;
    const img = p2.window.getComputedStyle(el).backgroundImage;
    return (bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') || (img !== 'none' && img !== '');
  }).map(function (el) { return '.' + String(el.className || el.tagName); });
  check('B1 NO element of the overlay paints a background (jsdom, resolved values)',
    painters, []);
  const scan = paintScan(dir);
  check('B2 every painting rule on the overlay or a descendant is neutralised (the PAGE own base is the render protection, not an offender)',
    scan.offenders, []);
  checkTrue('B2b and the left bar really does paint something', scan.allowed.length >= 1);
  /* B2c -- RE-AIMED 2026-11-25. It used to prove that `caption-float.css` covered
     panel.css's meter plate, and that sheet is no longer linked by this document, so
     the check was asking about a file the page does not load. What has to be true
     instead is that B2 is not green by starvation: the scan really walked the
     shipped sheets, and the retired float sheet is NOT one of them. */
  check('B2c the scan really walked the shipped sheets, and the retired float sheet is not among them',
    [scan.scanned > 100, scan.sheets.indexOf('caption-float.css') < 0], [true, true]);
  console.log('         shipped sheet population: ' + scan.sheets.join(', '));
  /* B3 -- RE-AIMED 2026-11-25 against the bytes that ship. `panel.css` puts the
     render protection on **body** and says so in the comment that owns the rule
     (`app/panel/panel.css:105-127`: "body carries the SAME dark base as its own
     background UNDERNEATH... it is the failure mode, made visible so it can never
     be white"). `html` is deliberately transparent: it is the window host, and a
     transparent `html` inside an OPAQUE WinForms window is not a slab because body
     paints under everything. The arm therefore holds the pair it can prove: `html`
     transparent, `body` OPAQUE; B3b is what forbids an UNSCOPED transparency from
     reaching the base, and B1/B2 are what forbid the overlay from painting. */
  const baseIs = function (v) { return (v === 'rgba(0, 0, 0, 0)' || v === 'transparent') ? 'TRANSPARENT' : 'OPAQUE'; };
  check('B3 the page base is html TRANSPARENT under an OPAQUE body (the render protection is body)',
    [baseIs(p2.bg(doc2.documentElement)), baseIs(p2.bg(doc2.body))], ['TRANSPARENT', 'OPAQUE']);
  /* B3d/B3e -- ADDED 2026-10-20, after the caption-window defect was measured.
     THE SHADOW IS THE OVERLAY'S BUSINESS, NOT THE PANEL'S. The rule that kills the
     text-shadow belongs to the CAPTION DOCUMENT: the overlay has no plate under the
     words, so a shadow reads as a dark halo around every letter (owner, 2026-10-17).
     The PANEL's inline caption DOES have a plate -- so ITS shadow stays, and it has
     to stay even when the shell has written `data-caption-window="off"` on this very
     document, which is what it does on EVERY LIVE switch (sotto_webview.py:8722-8724).
     Before the fix, the rule was scoped to `data-caption-window`, so it reached the
     panel too and took the shadow off the inline caption. */
  const hasShadow = function (v) { return Boolean(v) && v !== 'none' && v !== 'rgba(0, 0, 0, 0)'; };
  check('B3d the PANEL own inline caption KEEPS its shadow (the no-shadow rule is the caption document only)',
    [hasShadow(p2.window.getComputedStyle(p2.id('caption-float-line')).textShadow)], [true]);
  /* B3e -- and the CAPTION document, the one that carries the marker, has no shadow. */
  const p4 = loadPanel(dir);
  p4.document.documentElement.setAttribute('data-caption-doc', '1');
  check('B3e the CAPTION document line has NO shadow (the overlay has no plate under the words)',
    [hasShadow(p4.window.getComputedStyle(p4.id('caption-float-line')).textShadow)], [false]);
  /* B3b -- RE-BASELINED 2026-10-20 (lane caption). The old arm asked "does any sheet
     paint <html>/<body> HARDER than caption-float.css's transparency rule?" -- and
     that rule was DELETED on 2026-10-17, so the arm was asking about a rule that no
     longer exists and counted the panel's own dark base as an offender. THE
     CONTRACT TODAY: the panel's base is OPAQUE on purpose, the ONE place a
     transparent <html>/<body> is allowed is the CAPTION WINDOW (scoped to the
     attribute that marks that document), and an UNSCOPED transparency would take the
     panel's page with it -- the white slab, again. So the arm asks exactly that,
     over the whole document sheet population. */
  const pagePainters = [];
  for (const f of documentSheets(dir)) {
    for (const rule of parseCss(fs.readFileSync(f, 'utf8'))) {
      const bg = rule.decls.background;
      if (bg === undefined) continue;
      const v = String(bg).trim().toLowerCase();
      if (!(v === 'transparent' || v === 'none' || v === 'rgba(0, 0, 0, 0)')) continue;
      for (const member of rule.members) {
        const key = targetKey(member);
        if (key !== 'html' && key !== 'body') continue;
        /* THE CAPTION WINDOW IS ALLOWED ITS OWN TRANSPARENCY -- but only if the rule
           is scoped to the marker that says "THIS document is the caption window".
           THE OLD TOKEN WAS `data-caption-window`, AND THAT WAS THE HOLE (measured
           2026-10-20): the SHELL writes `data-caption-window` on the PANEL document
           on every LIVE switch (sotto_webview.py:8722-8724, with "on" and with
           "off"), so a rule scoped to it ALSO matched the panel -- and took the
           panel's render protection (panel.css:105-127) away for the rest of the
           session. The marker that really marks the caption document is
           `data-caption-doc`, and only caption.html carries it. */
        if (member.indexOf('data-caption-doc') >= 0) continue;
        pagePainters.push(path.basename(f) + ' :: ' + member + ' { background: ' + bg + ' }');
      }
    }
  }
  check('B3b the only TRANSPARENT <html>/<body> is scoped to the caption window (the panel own render protection holds)',
    pagePainters, []);
  check('B4 the meter plate and its fill paint nothing',
    [p2.bg(p2.id('caption-float-meter')), p2.bgImage(p2.id('caption-float-meter')),
     p2.bg(p2.id('caption-float-meter-fill'))],
    ['rgba(0, 0, 0, 0)', 'none', 'rgba(0, 0, 0, 0)']);
  check('B5 and the meter takes no room any more', p2.window.getComputedStyle(p2.id('caption-float-meter')).height, '0px');
  check('B6 the overlay is click-through', p2.window.getComputedStyle(floatEl2).pointerEvents, 'none');

  /* ── C. THE TRANSCRIPT IS AT THE BOTTOM AFTER A THEME CHANGE ─────────────── */
  arm = 'C';
  const list = p2.id('history-list');
  await p2.tick();
  await p2.tick();
  /* C1 -- RE-AIMED 2026-11-25. The `#history-gallery` day bucket this arm used to
     click is RETIRED: `panel.html` does not link `history-gallery.js` and the
     document carries no gallery markup, so the fixture could never exist again and
     the arm was red at HEAD for a page that no longer ships. The population door
     that ships is the worker's history replay into `#history-list`, and what has to
     stay true is that the retired module is NOT wired back in. */
  check('C1 the feed is populated by the shipped door and the retired gallery module is not linked',
    [p2.qa('#history-list .hist').length > 0,
     fs.readFileSync(path.join(dir, 'panel.html'), 'utf8').indexOf('history-gallery.js') < 0],
    [true, true]);
  const rowCount = p2.qa('#history-list .hist').length;
  checkTrue('C2 and the rows are in the list', rowCount > 0);
  p2.defineScroll(list, 1200, 300);
  /* THE BOTTOM IS `scrollHeight - clientHeight`, not `scrollHeight`:
     `pinHistoryToBottom` (`app/panel/panel.js:2006-2014`) assigns exactly that, and
     the arm now compares against the same arithmetic instead of a literal that
     stopped describing the pin. */
  const feedBottom = function () { return list.scrollHeight - list.clientHeight; };

  const theme = function () { doc2.documentElement.setAttribute('data-theme', 'theme-3'); };
  const settle = async function () { await p2.tick(); await p2.tick(); };

  list.scrollTop = 0;
  theme();
  await settle();
  check('C3 after a THEME write the feed is at the bottom', list.scrollTop, feedBottom());

  list.scrollTop = 0;
  doc2.body.setAttribute('data-skin', '1');
  await settle();
  check('C4 after a SKIN/template write the feed is at the bottom', list.scrollTop, feedBottom());

  list.scrollTop = 0;
  const link = doc2.createElement('link');
  link.rel = 'stylesheet';
  link.href = 'themes/cinematic.css';
  doc2.head.appendChild(link);
  link.dispatchEvent(new win.Event('load'));
  await settle();
  check('C5 after a STYLESHEET lands the feed is at the bottom', list.scrollTop, feedBottom());

  const live = p2.id('captions-body');
  p2.defineScroll(live, 900, 200);
  p2.caption(TOKEN_B + ' linha viva', 5, 6, true);
  live.scrollTop = 0;
  theme();
  await settle();
  check('C6 the LIVE box is at the bottom after a theme write', live.scrollTop, 900);

  const feedSrc = functionSource(fs.readFileSync(path.join(dir, 'panel.js'), 'utf8'), 'renderFeed');
  checkTrue('C7 renderFeed exists in the shipped panel.js', Boolean(feedSrc));
  check('C8 renderFeed pins to the bottom and never writes scrollTop = 0',
    [/pinHistoryToBottom\(\s*(true)?\s*\)/.test(feedSrc), /historyList\.scrollTop\s*=\s*0\s*;/.test(feedSrc)],
    [true, false]);

  const panelSrc = fs.readFileSync(path.join(dir, 'panel.js'), 'utf8');
  checkTrue('C9 the theme/skin/stylesheet guard is ARMED from the init block',
    /^wireThemeScrollGuard\(\);$/m.test(panelSrc));
  checkTrue('C10 the guard observes data-theme on <html> and data-skin on <body>',
    panelSrc.indexOf("attributeFilter: ['data-theme']") >= 0
      && panelSrc.indexOf("'data-skin', 'data-skin-theme'") >= 0);

  return rows;
}

function report(label) {
  console.log('');
  console.log('CAPTION INDEPENDENCE / NO-PAINT / SCROLL ORACLE -- ' + label);
  let bad = 0;
  for (const r of rows) { if (!r.ok) bad += 1; }
  console.log(rows.length + ' check(s), ' + bad + ' failed');
  if (bad) {
    console.log('failing:');
    for (const r of rows) { if (!r.ok) console.log('  [' + r.arm + '] ' + r.name + '  real=' + r.real + ' want=' + r.want); }
  }
  console.log('VERDICT: ' + (bad === 0 ? 'PASS' : 'FAIL'));
  return bad;
}

/* ─────────────────────────────── NEGATIVE ARM ─────────────────────────────── */
async function negArm() {
  const TMP = process.env.TMPDIR && fs.existsSync(process.env.TMPDIR) ? process.env.TMPDIR : os.tmpdir();
  const scratch = fs.mkdtempSync(path.join(TMP, 'sotto-caption-neg-'));
  const FILES = ['panel.html', 'panel.css', 'panel.js', 'caption-float.js', 'caption-float.css', 'zip-overlay.css'];
  const copyAll = function () {
    fs.rmSync(scratch, { recursive: true, force: true });
    fs.mkdirSync(scratch, { recursive: true });
    fs.cpSync(PANEL, scratch, { recursive: true });
    for (const f of FILES) {
      const a = fs.readFileSync(path.join(PANEL, f));
      const b = fs.readFileSync(path.join(scratch, f));
      if (!a.equals(b)) { console.error('SETUP ERROR: scratch copy of ' + f + ' differs from the shipped bytes'); process.exit(2); }
    }
  };
  const muts = [
    { tag: 'N12 caption-float.css is linked again by panel.html',
      file: 'panel.html',
      apply: function (t) { return t.replace('    <link rel="stylesheet" href="panel.css" />', '    <link rel="stylesheet" href="panel.css" />\n    <link rel="stylesheet" href="caption-float.css" />'); } },
    { tag: 'N1 the theme/skin guard is never armed (panel.js)',
      file: 'panel.js',
      apply: function (t) { return t.replace('wireThemeScrollGuard();', 'void 0;'); } },
    { tag: 'N2 the pin writes the TOP instead of the bottom (panel.js)',
      file: 'panel.js',
      apply: function (t) { return t.replace('  box.scrollTop = box.scrollHeight, pinnedHeight = box.scrollHeight;', '  box.scrollTop = 0, pinnedHeight = box.scrollHeight;'); } },
    /* N3 -- RE-ANCHORED AGAIN 2026-11-25. The 2026-10-20 form INJECTED the deleted
       rule into `caption-float.css`, and that sheet is no longer loaded by
       `panel.html` (nor was its injected selector ever matched: the shell writes
       `data-float` on `#caption-float`, not on `<html>/<body>`). So the mutant had
       NO reachable effect and stayed GREEN the moment the seven standing reds were
       fixed -- a decorative mutant. THE DEFEIT IT DESCRIBES is still the right one:
       the page loses the opaque base and the white slab comes back. The live owner
       of that base is `panel.css:105-127` (body carries the render protection), so
       the mutation is made THERE: body's own background goes transparent. B3 must
       go RED, and B3b must name the unscoped transparency. */
    { tag: 'N3 the render protection is undone (body drops its opaque base) (panel.css)',
      file: 'panel.css',
      apply: function (t) {
        return t.replace('re-expose the white) and `overflow: hidden` keeps the rounded shape. */\r\n  background: rgba(11, 15, 20, 0.98);',
                         're-expose the white) and `overflow: hidden` keeps the rounded shape. */\r\n  background: transparent;');
      } },
    { tag: 'N4 the meter plate comes back (caption-float.css)',
      file: 'caption-float.css',
      apply: function (t) {
        return t.replace('#caption-float .caption-float__meter {\r\n  height: 0;\r\n  margin: 0;\r\n}',
          '#caption-float .caption-float__meter {\r\n  height: 3px;\r\n  background: rgba(255, 255, 255, 0.16);\r\n}');
      } },
    { tag: 'N5 the overlay can no longer build itself (the shipped coupling) (caption-float.js)',
      file: 'caption-float.js',
      apply: function (t) { return t.replace('      d.body.appendChild(host);', '      return false;'); } },
    /* N6 -- RE-ANCHORED 2026-10-20 (lane caption). The anchor said
       `on ? 'on' : 'off'`, and the shipped line says `want ? 'on' : 'off'`: the
       attribute now follows WHAT IS PAINTED (`want`), not the module's own
       switch (`on`) -- because the SHELL reads `documentElement[data-float]` to
       size the strip (sotto_webview.py:6527 and :6579), and a strip must not
       reserve a height for a caption this document does not paint. The old
       anchor was ABSENT, so the negative arm died with "SETUP ERROR: mutant
       anchor absent" (rc=2) -- a broken instrument, not a red one. The MUTATION
       is the same defect the old one described (the shell cannot see the float
       state) and A11 must still go RED. */
    { tag: 'N6 the shell cannot see the float state on <html> (caption-float.js)',
      file: 'caption-float.js',
      apply: function (t) { return t.replace("      d.documentElement.setAttribute('data-float', want ? 'on' : 'off');", '      void 0;'); } },
    /* N11 -- 2026-10-20. THE ATTRIBUTE FOLLOWS THE SWITCH AGAIN. This is the
       defect the new rule exists to prevent: the strip is told "on" for a caption
       the page does not paint, so the shell reserves a height for a caption that
       is not there. A22 must go RED. */
    { tag: 'N11 the strip is told to reserve a height for a caption the page does not paint (caption-float.js)',
      file: 'caption-float.js',
      apply: function (t) { return t.replace("      d.documentElement.setAttribute('data-float', want ? 'on' : 'off');", "      d.documentElement.setAttribute('data-float', on ? 'on' : 'off');"); } },
    /* N7/N8 ARE THE CONTROLS THE 2026-10-13 RE-BASELINE NEEDED, and they break the
       NEW contract. N7 deletes the ONE call that makes live-on mean caption-on-screen,
       so A13b/A13c and the panel-surface arms must go RED. N8 restores the interim
       default (`liveEnabled = true`), so A13's own "ships UNPRESSED" claim and the
       click direction must go RED. Both are ONE-LINE mutations of TODAY'S panel.js. */
    { tag: 'N7 the live button no longer drives the overlay (applyFloat call deleted) (panel.js)',
      file: 'panel.js',
      apply: function (t) { return t.replace(/  applyFloat\(liveEnabled\);\r?\n/, ''); } },
    /* N8 -- RE-ANCHORED 2026-10-20 (lane caption). The old mutation was
       `let liveEnabled = false;` -> `true`, and it is INERT under the native
       contract: the page's `liveEnabled` is no longer the caption's state, it is
       a mirror of the SHELL's account (`data-caption-window`), and
       `watchCaptionWindowState()` overwrites it at init with what the shell said
       -- which is "nothing yet". The caption's state moved to the shell, so the
       defect moved with it: the page BELIEVING the window is already up. The
       mutation is that belief, and A13 ("ships UNPRESSED") and A21 (the fallback
       host ships OFF) must go RED. */
    { tag: 'N8 the caption ships ON again (the page believes the window is already up) (panel.js)',
      file: 'panel.js',
      apply: function (t) { return t.replace("return document.documentElement.getAttribute(CAPTION_WINDOW_ATTR) === 'on';", 'return true;'); } },
    /* N9 -- 2026-10-20. THE DEFECT, AS A MUTANT. The pre-fix bytes scoped the three
       caption-window rules to `html[data-caption-window]` -- the attribute the SHELL
       writes on the PANEL document on every LIVE switch, with "on" and with "off".
       So the caption-document-only rules also matched the panel, and the panel lost
       its render protection (panel.css:105-127). The mutation below reproduces those
       bytes EXACTLY, and B3 (the panel's base, measured with the attribute present,
       because arm A13e left `data-caption-window="off"` on this document) must go RED.
       Before 2026-10-20 this mutant could not go red: the harness did not load
       zip-overlay.css, so the rule was not in the population at all. */
    { tag: 'N9 the caption-window rules go back to the attribute the shell writes on the PANEL (zip-overlay.css)',
      file: 'zip-overlay.css',
      apply: function (t) {
        return t
          .replace('html[data-caption-window="on"]:not([data-caption-doc]) #caption-float',
                   'html[data-caption-window="on"] #caption-float')
          .replace(/html\[data-caption-doc\]/g, 'html[data-caption-window]');
      } },
    /* N10 -- 2026-10-20. THE SAME HOLE, IN ONE RULE. The text-shadow rule alone goes
       back to `data-caption-window`, so it reaches the panel and takes the shadow off
       the inline caption -- the one that HAS a plate under the words. B3d must go RED
       while B3 (the base) stays GREEN: two defects, one rule each. */
    { tag: 'N10 the no-shadow rule goes back to the attribute the shell writes on the PANEL (zip-overlay.css)',
      file: 'zip-overlay.css',
      apply: function (t) {
        return t.replace('html[data-caption-doc] #caption-float .caption-float__line',
                         'html[data-caption-window] #caption-float .caption-float__line');
      } },
    { tag: 'N13 the panel row stops painting its own caption words',
      file: 'panel.js',
      apply: function (t) { return t.replace('span.replaceChildren(document.createTextNode(word));', 'void 0;'); } },
  ];
  let wrong = 0;
  for (const m of muts) {
    copyAll();
    const file = path.join(scratch, m.file);
    const before = fs.readFileSync(file, 'utf8');
    const after = m.apply(before);
    if (after === before) { console.error('SETUP ERROR: mutant anchor absent in ' + m.file + ' (' + m.tag + ')'); process.exit(2); }
    fs.writeFileSync(file, after);
    rows.length = 0;
    const all = await runChecks(scratch);
    const bad = all.filter(function (r) { return !r.ok; });
    const red = bad.length > 0;
    if (!red) wrong += 1;
    console.log('  ' + (red ? 'RED  ' : 'GREEN') + '  ' + m.tag + ' -> ' + bad.length + ' failing check(s)'
      + (bad.length ? ': ' + bad.slice(0, 5).map(function (x) { return x.name.split(' ')[0]; }).join(' | ') : ''));
  }
  fs.rmSync(scratch, { recursive: true, force: true });
  console.log('');
  console.log(wrong === 0
    ? 'NEG-ARM VERDICT: PASS -- every mutant went RED.'
    : 'NEG-ARM VERDICT: FAIL -- ' + wrong + ' mutant(s) stayed GREEN.');
  process.exit(wrong === 0 ? 0 : 1);
}

if (NEG) {
  negArm().catch(function (err) {
    console.error('SETUP ERROR: ' + (err && err.stack ? err.stack : err));
    process.exit(2);
  });
}

if (!NEG) {
  runChecks(PANEL).then(function (all) {
    const bad = report('PRISTINE (the shipped bytes)');
    process.exit(bad === 0 ? 0 : 1);
  }).catch(function (err) {
    console.error('SETUP ERROR: ' + (err && err.stack ? err.stack : err));
    process.exit(2);
  });
}
