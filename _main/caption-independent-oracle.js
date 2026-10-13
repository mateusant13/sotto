/* caption-independent-oracle.js -- THE LANE CAPTION GATE (2026-10-12).
 *
 * THE OWNER'S THREE DEMANDS, verbatim, and the check that answers each:
 *   "a porra da legenda, e pra ser independente do painel, nao acoplado."
 *        -> ARM A: the overlay paints with NO panel in the document at all, owns its
 *           own state (show/hide), and the shell's own geometry read
 *           (documentElement[data-float]) sees it.
 *   "e eu to vendo div com cor solida inves de invisivel."
 *        -> ARM B: neither the overlay, nor a descendant, nor the page behind it
 *           paints a background. The one body is the 4px left bar.
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
 * THE CONTROL ARM (--neg-arm) is the point of the file: eight mutants, one at a time,
 * each applied to a fresh copy of app/panel, and the SAME checks re-run. Every mutant
 * must go RED. One of them (N5) is the owner's own coupling restored: the module is
 * mutated so it can no longer create the overlay it does not find, which is exactly
 * the shipped behaviour this lane replaced.
 *
 *   node _main/caption-independent-oracle.js            expect VERDICT: PASS, rc=0
 *   node _main/caption-independent-oracle.js --neg-arm  expect every mutant RED, rc=0
 *
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

function bridgeStub(window, entries) {
  const subs = { caption: [], status: [] };
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
    setLiveEnabled: function (on) { return Promise.resolve({ liveEnabled: Boolean(on) }); },
    pause: function () { return Promise.resolve({ paused: true }); },
    setPanelSurface: function (name) {
      if (window.SottoSurfaces) window.SottoSurfaces.set(String(name));
      return Promise.resolve({ surface: String(name) });
    },
    __emit: function (kind, payload) { for (const cb of subs[kind]) cb(payload); },
  };
  window.sotto = bridge;
  return bridge;
}

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
  const errors = [];
  for (const src of scriptSources(html)) {
    const file = path.resolve(dir, src);
    if (!fs.existsSync(file)) { errors.push('missing ' + src); continue; }
    try { window.eval(fs.readFileSync(file, 'utf8')); } catch (err) { errors.push(src + ': ' + (err && err.message)); }
  }
  try { window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true })); }
  catch (err) { errors.push('DOMContentLoaded: ' + (err && err.message)); }
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
  names.add('caption-float.css');
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
  const own = fs.existsSync(ownPath) ? parseCss(fs.readFileSync(ownPath, 'utf8')) : [];
  const offenders = [];
  const covered = [];
  const allowed = [];
  let scanned = 0;
  for (const f of documentSheets(dir)) {
    const isOwn = path.resolve(f) === path.resolve(ownPath);
    for (const rule of parseCss(fs.readFileSync(f, 'utf8'))) {
      scanned += 1;
      for (const member of rule.members) {
        if (!memberTouchesFloat(member) && !memberIsConstraintFree(member)) continue;
        for (const prop of PAINT_PROPS) {
          if (!(prop in rule.decls)) continue;
          if (!paintsValue(prop, rule.decls[prop])) continue;
          const entry = path.basename(f) + ' :: ' + member + ' { ' + prop + ': ' + rule.decls[prop] + ' }';
          // THE ONE ALLOWED PAINTER, whichever sheet declares it: the 4px left bar.
          if (memberIsLed(member)) { allowed.push(entry); continue; }
          if (isOwn) { offenders.push(entry); continue; }
          const token = targetKey(member);
          const mine = specificity(member);
          const neutral = own.some(function (r) {
            return r.members.some(function (m2) {
              // The KEY is what decides: a candidate must target the SAME element
              // (the same class/id, or the same page element for html/body).
              if (!keyMatches(m2, token)) return false;
              if (!specGte(specificity(m2), mine)) return false;
              const direct = r.decls[prop];
              if (direct !== undefined && !paintsValue(prop, direct)) return true;
              const shorthand = r.decls.background;
              return shorthand !== undefined && !paintsValue('background', shorthand);
            });
          });
          if (neutral) covered.push(entry); else offenders.push(entry);
        }
      }
    }
  }
  return { offenders: offenders, covered: covered, allowed: allowed, scanned: scanned };
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
  const floatLinks = p.qa('link[rel="stylesheet"]').filter(function (l) {
    return String(l.getAttribute('href') || '').indexOf('caption-float.css') >= 0;
  });
  check('A1 the panel document carries exactly ONE link to caption-float.css',
    [floatLinks.length, floatLinks.length === 1], [1, true]);
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
  p2.click(btn);
  check('A13b clicking live ON puts the caption on the strip screen',
    [btn.getAttribute('aria-pressed'), doc2.body.getAttribute('data-float'), p2.display(floatEl2)],
    ['true', 'on', 'block']);
  check('A14 the shell geometry read (documentElement[data-float]) sees it',
    doc2.documentElement.getAttribute('data-float'), 'on');
  check('A15 and the panel attribute is still written for its own CSS',
    doc2.body.getAttribute('data-float'), 'on');
  check('A16 with a panel mounted the module does NOT feed itself (no double paint)',
    p2.window.SottoCaptionFloat.state().feed, 'panel');
  checkTrue('A17 the overlay is not inside the panel div', !p2.id('panel').contains(floatEl2));
  p2.caption(TOKEN_A + ' uma linha', 0, 1, true);
  check('A18 one bridge caption paints the overlay once, with the panel text',
    p2.text(p2.id('caption-float-line')), TOKEN_A + ' uma linha');
  doc2.body.setAttribute('data-surface', 'panel');
  await p2.tick();
  check('A19 on the FULL panel surface the overlay never paints over it',
    [doc2.body.getAttribute('data-float'), p2.display(floatEl2)], ['on', 'none']);
  doc2.body.setAttribute('data-surface', 'strip');
  await p2.tick();
  check('A20 and it comes back on the strip', p2.display(floatEl2), 'block');
  p2.click(btn);
  check('A13c clicking live OFF takes the overlay off the screen',
    [btn.getAttribute('aria-pressed'), doc2.body.getAttribute('data-float'), p2.display(floatEl2)],
    ['false', 'off', 'none']);
  /* BACK ON for ARM B: B3 measures the PAGE while the caption is FLOATED, and the
     transparency rule keys on data-float="on". A13c is the only OFF transition, so
     the arm restores the ON state it needs rather than letting the ordering decide. */
  p2.click(btn);
  check('A13d and the caption is back ON, floated, with no page behind it',
    [btn.getAttribute('aria-pressed'), doc2.body.getAttribute('data-float')], ['true', 'on']);

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
  check('B2 every painting rule on the overlay or a descendant is neutralised',
    scan.offenders, []);
  checkTrue('B2b and the left bar really does paint something', scan.allowed.length >= 1);
  checkTrue('B2c the panel.css meter plate really was found and covered',
    scan.covered.some(function (e) { return e.indexOf('caption-float__meter') >= 0; }));
  console.log('         covered by caption-float.css: ' + scan.covered.length + ' rule(s)');
  for (const c of scan.covered) console.log('           ' + c);
  check('B3 while floated the PAGE paints nothing either (the owner solid div)',
    [p2.bg(doc2.documentElement), p2.bg(doc2.body)], ['rgba(0, 0, 0, 0)', 'rgba(0, 0, 0, 0)']);
  /* The page-level transparency is the ONE rule in this lane that a later theme could
     out-specify, so it is gated: nothing in the document's own sheet population may
     paint <html>/<body> with a specificity that beats caption-float.css's rule. */
  const ownRules = parseCss(fs.readFileSync(path.join(dir, 'caption-float.css'), 'utf8'));
  const transparency = ownRules.filter(function (r) {
    return r.members.some(function (m) {
      const k = targetKey(m);
      return (k === 'html' || k === 'body') && r.decls.background === 'transparent';
    });
  });
  const pagePainters = [];
  for (const f of documentSheets(dir)) {
    if (path.resolve(f) === path.resolve(path.join(dir, 'caption-float.css'))) continue;
    for (const rule of parseCss(fs.readFileSync(f, 'utf8'))) {
      if (!rule.decls.background || !paintsValue('background', rule.decls.background)) continue;
      for (const member of rule.members) {
        const key = targetKey(member);
        if (key !== 'html' && key !== 'body') continue;
        const beats = transparency.some(function (r) {
          return r.members.some(function (m) { return keyMatches(m, key) && specGte(specificity(m), specificity(member)); });
        });
        if (!beats) pagePainters.push(path.basename(f) + ' :: ' + member + ' { background: ' + rule.decls.background + ' }');
      }
    }
  }
  check('B3b no document sheet paints <html>/<body> harder than the transparency rule',
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
  const dayBtn = p2.qa('#history-gallery .gallery__day')[0];
  checkTrue('C1 the feed really holds rows (the gallery painted a day bucket)', Boolean(dayBtn));
  p2.click(dayBtn);
  await p2.tick();
  const rowCount = p2.qa('#history-list .hist').length;
  checkTrue('C2 and the rows are in the list', rowCount > 0);
  p2.defineScroll(list, 1200, 300);

  const theme = function () { doc2.documentElement.setAttribute('data-theme', 'theme-3'); };
  const settle = async function () { await p2.tick(); await p2.tick(); };

  list.scrollTop = 0;
  theme();
  await settle();
  check('C3 after a THEME write the feed is at the bottom', list.scrollTop, 1200);

  list.scrollTop = 0;
  doc2.body.setAttribute('data-skin', '1');
  await settle();
  check('C4 after a SKIN/template write the feed is at the bottom', list.scrollTop, 1200);

  list.scrollTop = 0;
  const link = doc2.createElement('link');
  link.rel = 'stylesheet';
  link.href = 'themes/cinematic.css';
  doc2.head.appendChild(link);
  link.dispatchEvent(new win.Event('load'));
  await settle();
  check('C5 after a STYLESHEET lands the feed is at the bottom', list.scrollTop, 1200);

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
    [feedSrc.indexOf('pinHistoryToBottom()') >= 0, /historyList\.scrollTop\s*=\s*0\s*;/.test(feedSrc)],
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
  const FILES = ['panel.html', 'panel.css', 'panel.js', 'caption-float.js', 'caption-float.css'];
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
    { tag: 'N1 the theme/skin guard is never armed (panel.js)',
      file: 'panel.js',
      apply: function (t) { return t.replace('wireThemeScrollGuard();', 'void 0;'); } },
    { tag: 'N2 the pin writes the TOP instead of the bottom (panel.js)',
      file: 'panel.js',
      apply: function (t) { return t.replace('  list.scrollTop = list.scrollHeight;', '  list.scrollTop = 0;'); } },
    { tag: 'N3 the page paints its solid slab behind the caption (caption-float.css)',
      file: 'caption-float.css',
      apply: function (t) {
        return t.replace(/html\[data-float="on"\],\r?\nbody\[data-float="on"\] \{[^}]*\}/,
          'html[data-float="on"],\r\nbody[data-float="on"] {\r\n  background: rgba(11, 15, 20, 0.98);\r\n}');
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
    { tag: 'N6 the shell cannot see the float state on <html> (caption-float.js)',
      file: 'caption-float.js',
      apply: function (t) { return t.replace("      d.documentElement.setAttribute('data-float', on ? 'on' : 'off');", '      void 0;'); } },
    /* N7/N8 ARE THE CONTROLS THE 2026-10-13 RE-BASELINE NEEDED, and they break the
       NEW contract. N7 deletes the ONE call that makes live-on mean caption-on-screen,
       so A13b/A13c and the panel-surface arms must go RED. N8 restores the interim
       default (`liveEnabled = true`), so A13's own "ships UNPRESSED" claim and the
       click direction must go RED. Both are ONE-LINE mutations of TODAY'S panel.js. */
    { tag: 'N7 the live button no longer drives the overlay (applyFloat call deleted) (panel.js)',
      file: 'panel.js',
      apply: function (t) { return t.replace(/  applyFloat\(liveEnabled\);\r?\n/, ''); } },
    { tag: 'N8 the caption ships ON again (liveEnabled defaults true) (panel.js)',
      file: 'panel.js',
      apply: function (t) { return t.replace('let liveEnabled = false;', 'let liveEnabled = true;'); } },
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
