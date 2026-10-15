#!/usr/bin/env node
/* Sotto -- the THEME SWITCHING gate: trocar de tema, on the REAL module.
 *
 * WHAT IT PROVES. The owner's control is one button: *"no painel, vai ter botao
 * de mudar o tema"*. The whole mechanism is ONE attribute write,
 *
 *     document.documentElement.dataset.theme = 'theme-3'
 *
 * because every rule in every generated stylesheet is scoped to
 * `:root[data-theme='X']`. So the claims that matter are the ones a byte-grep
 * cannot make:
 *
 *   ARM 1  THE SWITCH IS ONE WRITE. `set(name)` writes the attribute exactly
 *          once and returns the name it applied.
 *   ARM 2  THE CYCLE IS A RING. `next()` and `previous()` walk the manifest in
 *          order and WRAP: the ends of the list are not a wall, so a wrong click
 *          costs one more click instead of a trip to the picker.
 *   ARM 3  AN UNKNOWN NAME IS REFUSED. A half-applied switch is worse than no
 *          switch: the current theme is returned and the document is untouched.
 *   ARM 4  THE SWITCH TOUCHES NOTHING ELSE. It changes no element that carries
 *          text, adds no listener to the live box, and never reaches the shell
 *          bridge -- the shell is the only thing that can talk to the worker.
 *   ARM 5  EVERY MANIFEST ENTRY IS REACHABLE. Each name the manifest declares
 *          has a scope in the generated CSS, so a switch cannot change the
 *          attribute and paint nothing.
 *   ARM 6  THE STORED CHOICE COMES BACK. A restart must not repaint the panel
 *          in a different theme: the stored choice is applied at mount, before
 *          anything is painted.
 *   ARM 7  PERSISTENCE IS DEFENSIVE. `localStorage` is not guaranteed over
 *          `file://` in WebView2; when it throws, the switch still works.
 *   ARM 8  MOUNT IS IDEMPOTENT. A second `mount()` must not duplicate a
 *          listener or a picker.
 *
 * THE CONTROL IS THREE MUTANTS, NOT A COMMENT (`--neg-arm`). Each is a COPY of
 * the real `theme-switcher.js` written to `$TMPDIR` with ONE half of the
 * mechanism reverted, and the arm that owns it has to go RED:
 *
 *   M1  the attribute write is removed (the switch becomes a no-op);
 *   M2  the unknown-name refusal is removed (a half-applied switch);
 *   M3  the store write is removed (the choice does not survive a restart).
 *
 * NO GUI, NO BROWSER, NO SHELL: the REAL module is `require`d against a fake
 * document, exactly as `_main/theme-preview-oracle.js` already does. Nothing is
 * launched. `TMPDIR` is honoured.
 *
 * Run:  node _main/theme-switch-oracle.js
 *       node _main/theme-switch-oracle.js --neg-arm
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

/* This oracle is an ES module and the two panel modules it mounts are CommonJS
 * (`module.exports = api`), so `require` is built here explicitly rather than
 * borrowed from a global that an ESM does not have. */
const require = createRequire(import.meta.url);

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..');
const PANEL = path.join(REPO, 'app', 'panel');
const THEMES = path.join(PANEL, 'themes');
const args = process.argv.slice(2);
const NEG = args.includes('--neg-arm');

const say = (s) => { console.log(s); };

/* ── a SMALL but REAL DOM shim ───────────────────────────────────────────────
 * Only what the switcher touches. A compound selector still matches NOTHING on
 * purpose: the arms ask WHERE the module mounted, and a selector engine that
 * guessed would let a module that mounted nothing pass. */
function makeElement(tag) {
  const el = {
    tagName: String(tag).toUpperCase(),
    children: [],
    _attrs: {},
    _text: '',
    _listeners: {},
    _observeHook: null,
    hidden: false,
    parentNode: null,
    /* A CSSStyleDeclaration, small but real: the module paints the swatch with
     * setProperty and reads it back, and a plain object would throw where the
     * browser would not. */
    style: {
      _props: {},
      setProperty(k, v) { this._props[String(k)] = String(v); },
      removeProperty(k) { delete this._props[String(k)]; },
      getPropertyValue(k) { return Object.prototype.hasOwnProperty.call(this._props, k) ? this._props[k] : ''; }
    },
    dataset: {},
    classList: {
      _set: null,
      contains(c) { return (this._set || []).indexOf(c) >= 0; },
      add(c) { if (!this._set) this._set = []; if (this._set.indexOf(c) < 0) this._set.push(c); },
      remove(c) { if (this._set) this._set = this._set.filter((x) => x !== c); }
    },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    insertBefore(c, ref) {
      c.parentNode = this;
      const i = ref ? this.children.indexOf(ref) : -1;
      if (i < 0) this.children.push(c); else this.children.splice(i, 0, c);
      return c;
    },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
    /* Element.append/prepend/replaceChildren: the modern insertion API the
     * module uses for its own picker. Text nodes are modelled as elements whose
     * textContent is the string, which is all the arms need to read back. */
    append() {
      for (let i = 0; i < arguments.length; i += 1) {
        const c = arguments[i];
        if (typeof c === 'string') { const tn = makeElement('#text'); tn.textContent = c; this.appendChild(tn); }
        else this.appendChild(c);
      }
    },
    prepend() {
      for (let i = arguments.length - 1; i >= 0; i -= 1) {
        const c = arguments[i];
        const node = typeof c === 'string' ? makeElement('#text') : c;
        if (typeof c === 'string') node.textContent = c;
        this.insertBefore(node, this.children[0] || null);
      }
    },
    replaceChildren() {
      this.children = [];
      this.append.apply(this, arguments);
    },
    setAttribute(k, v) { this._attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this._attrs, k) ? this._attrs[k] : null; },
    removeAttribute(k) { delete this._attrs[k]; },
    addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); },
    removeEventListener(type, fn) {
      if (this._listeners[type]) this._listeners[type] = this._listeners[type].filter((f) => f !== fn);
    },
    dispatch(type, ev) {
      ev = ev || {}; ev.type = type;
      if (!ev.preventDefault) ev.preventDefault = function () {};
      if (!ev.stopPropagation) ev.stopPropagation = function () {};
      const ls = (this._listeners[type] || []).slice();
      for (let i = 0; i < ls.length; i += 1) ls[i].call(this, ev);
    },
    focus() { doc.activeElement = this; },
    blur() { if (doc.activeElement === this) doc.activeElement = null; },
    contains(node) {
      if (node === this) return true;
      for (let i = 0; i < this.children.length; i += 1) {
        if (this.children[i].contains && this.children[i].contains(node)) return true;
      }
      return false;
    },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    querySelectorAll(sel) {
      const out = [], seen = [];
      const parts = String(sel).split(',');
      for (let p = 0; p < parts.length; p += 1) {
        const s = parts[p].trim();
        let m = null;
        if (/^\.\w[\w-]*$/.test(s)) m = { kind: 'class', value: s.slice(1) };
        else if (/^#\w[\w-]*$/.test(s)) m = { kind: 'id', value: s.slice(1) };
        else if (/^\[\w[\w-]*\]$/.test(s)) m = { kind: 'attr', value: s.slice(1, -1) };
        else if (/^[a-zA-Z][\w-]*$/.test(s)) m = { kind: 'tag', value: s.toLowerCase() };
        if (!m) continue;
        (function walk(n) {
          for (let i = 0; i < n.children.length; i += 1) {
            const c = n.children[i];
            let hit = false;
            if (m.kind === 'class') hit = !!(c.classList && c.classList.contains(m.value));
            else if (m.kind === 'id') hit = !!(c._attrs && c._attrs.id === m.value);
            else if (m.kind === 'attr') hit = !!(c._attrs && Object.prototype.hasOwnProperty.call(c._attrs, m.value));
            else if (m.kind === 'tag') hit = String(c.tagName).toLowerCase() === m.value;
            if (hit && seen.indexOf(c) < 0) { seen.push(c); out.push(c); }
            walk(c);
          }
        })(this);
      }
      return out;
    },
    get textContent() { return this._text; },
    set textContent(v) { this._text = String(v); }
  };
  Object.defineProperty(el, 'id', {
    get() { return this._attrs.id || ''; },
    set(v) { this._attrs.id = String(v); },
    configurable: true
  });
  Object.defineProperty(el, 'className', {
    get() { return (el.classList._set || []).join(' '); },
    set(v) { el.classList._set = String(v).split(/\s+/).filter(Boolean); },
    configurable: true
  });
  return el;
}

/* The documentElement's dataset is the whole hot path: the switcher writes
 * `el.dataset.theme = name`. A plain object would do the write and drop the
 * notification, so this shim RECORDS the write. */
function makeHtml() {
  const h = makeElement('html');
  const real = {};
  h.dataset = new Proxy(real, {
    set(t, k, v) {
      t[k] = v;
      if (k === 'theme') attributeWrites.push(String(v));
      if (h._observeHook) h._observeHook();
      return true;
    },
    get(t, k) { return t[k]; },
    has(t, k) { return k in t; }
  });
  return h;
}

/* The host page's own control cluster and strip theme button -- the markup the
 * switcher looks for before it builds its own. */
function makeBody(surface) {
  const body = makeElement('body');
  body.dataset.surface = surface || 'panel';
  const header = makeElement('header');
  header.className = 'panel__header';
  const controls = makeElement('div');
  controls.className = 'panel__controls';
  controls._attrs.id = 'panel-controls';
  header.appendChild(controls);
  body.appendChild(header);
  const stripbar = makeElement('section');
  stripbar.className = 'stripbar';
  stripbar._attrs.id = 'strip-controls';
  const theme = makeElement('button');
  theme.className = 'strip-button strip-button--theme';
  theme._attrs.id = 'strip-theme-button';
  theme._attrs['data-theme-button'] = 'true';
  theme.dataset.themeButton = 'true';
  stripbar.appendChild(theme);
  body.appendChild(stripbar);
  return body;
}

let attributeWrites = [];
let storeWrites = [];
let bridgeCalls = [];
let doc = null;
let root = null;

function makeRoot(storeMode, sharedStore) {
  /* \`sharedStore\` is how ARM 6 models a RESTART: the same profile's storage
   * handed to a second mount. Without it the arm would test my scaffolding
   * (a fresh empty store) instead of the module's persistence. */
  const store = sharedStore || {};
  const localStorageShim = {
    getItem(k) {
      if (storeMode === 'throw') throw new Error('SecurityError: file:// storage');
      return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null;
    },
    setItem(k, v) {
      if (storeMode === 'throw') throw new Error('SecurityError: file:// storage');
      storeWrites.push(String(k)); store[String(k)] = String(v);
    },
    removeItem(k) { delete store[k]; }
  };
  const bridge = new Proxy({}, {
    get(t, prop) {
      if (prop === 'history') return { append: function () { bridgeCalls.push('history.append'); } };
      return function () { bridgeCalls.push(String(prop)); };
    }
  });
  const listeners = {};
  const r = {
    document: null,
    localStorage: localStorageShim,
    navigator: { userAgent: 'sotto-oracle' },
    performance: { now: function () { return Date.now(); } },
    requestAnimationFrame: function (fn) { fn(); return 1; },
    cancelAnimationFrame: function () {},
    requestIdleCallback: function (fn) { fn(); return 1; },
    setTimeout: function (fn) { fn(); return 0; },
    clearTimeout: function () {},
    addEventListener: function (type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    dispatch: function (type, ev) {
      ev = ev || {}; ev.type = type;
      const ls = (listeners[type] || []).slice();
      for (let i = 0; i < ls.length; i += 1) ls[i].call(r, ev);
    },
    sotto: bridge,
    SottoThemeManifest: null,
    SottoTheme: null,
    SottoThemeTune: null
  };
  return r;
}

function makeDocument(surface) {
  const h = makeHtml();
  const b = makeBody(surface);
  const listeners = {};
  const d = {
    documentElement: h,
    body: b,
    activeElement: null,
    readyState: 'complete',
    fonts: { load: function () { return Promise.resolve(); } },
    createElement: function (t) { return makeElement(t); },
    createElementNS: function (ns, t) { return makeElement(t); },
    getElementById: function (id) {
      const all = b.querySelectorAll('#' + id);
      return all[0] || null;
    },
    querySelector: function (sel) { return b.querySelector(sel); },
    querySelectorAll: function (sel) { return b.querySelectorAll(sel); },
    addEventListener: function (type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    dispatch: function (type, ev) {
      ev = ev || {}; ev.type = type;
      if (!ev.preventDefault) ev.preventDefault = function () {};
      if (!ev.stopPropagation) ev.stopPropagation = function () {};
      const ls = (listeners[type] || []).slice();
      for (let i = 0; i < ls.length; i += 1) ls[i].call(d, ev);
    }
  };
  return d;
}

/* MOUNT A PRIVATE COPY of the module against a document of its own, on a
 * directory of its own so `require` re-executes it (a cached module would carry
 * the first one's listener list and its dropdown). `src` optional: a MUTANT. */
let mountSeq = 0;
function mountFresh(label, surface, storeMode, src, sharedStore) {
  const base = process.env.TMPDIR || process.env.TEMP || os.tmpdir();
  /* A DIRECTORY OF ITS OWN PER MOUNT, and this is load-bearing: require caches by
   * resolved path, so two mounts sharing one scratch file would make the second
   * silently re-run the FIRST one's bytes -- against the FIRST one's root. That
   * is a harness that measures the wrong module and reports whatever it finds,
   * which is worse than no harness at all. */
  mountSeq += 1;
  const dir = path.join(base, 'sotto-switch-' + label + '-' + mountSeq);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'theme-switcher.js'),
    src || fs.readFileSync(path.join(PANEL, 'theme-switcher.js'), 'utf8'));
  attributeWrites = []; storeWrites = []; bridgeCalls = [];
  doc = makeDocument(surface);
  root = makeRoot(storeMode, sharedStore);
  root.document = doc;
  /* The manifest is ITSELF a Node-loadable module (module.exports = api), so it
   * is REQUIRED rather than scraped: a regex over a literal would agree with the
   * file it rewrote, which is the one thing a gate must never do. */
  /* The module reads \`window\` ONCE, at load: \`(function (root) {...}(typeof window
   * !== 'undefined' ? window : null))\`. In Node that global does not exist, so
   * the shim installs itself under the name the module expects BEFORE the
   * require -- without this the module loads with \`root === null\` and every
   * method dies on \`root.document\`. */
  global.window = root;
  root.SottoThemeManifest = require(path.join(THEMES, 'themes.js'));
  const sw = require(path.join(dir, 'theme-switcher.js'));
  root.SottoTheme = sw;
  sw.mount();
  return { sw: sw, doc: doc, root: root };
}

/* ── the arms ────────────────────────────────────────────────────────────────
 * Every arm reads \`m.doc\` -- the document THAT module mounted against -- and
 * never a module-level "current document": a later mount would otherwise move the
 * ground under an arm that had already run, which is exactly the mistake this
 * comment exists to stop being made twice. */
function arm1(m) {
  const bad = [];
  const before = attributeWrites.length;
  const got = m.sw.set('theme-3');
  if (got !== 'theme-3') bad.push('set(theme-3) returned "' + got + '", expected "theme-3"');
  if (attributeWrites.length !== before + 1) {
    bad.push('set() wrote the attribute ' + (attributeWrites.length - before)
      + ' time(s), expected exactly 1');
  }
  if (m.doc.documentElement.dataset.theme !== 'theme-3') {
    bad.push('documentElement.dataset.theme is "' + m.doc.documentElement.dataset.theme
      + '", expected "theme-3"');
  }
  return bad;
}

function arm2(m) {
  const bad = [];
  const names = m.sw.list().map((x) => x.name);
  const N = names.length;
  if (N < 2) { bad.push('the manifest lists ' + N + ' theme(s); cannot test a ring'); return bad; }
  m.sw.set(names[0]);
  const seq = [];
  for (let i = 0; i < N + 2; i += 1) seq.push(m.sw.next());
  for (let i = 0; i < N + 2; i += 1) {
    const want = names[(i + 1) % N];
    if (seq[i] !== want) {
      bad.push('next() step ' + i + ' gave "' + seq[i] + '", expected "' + want + '"');
      break;
    }
  }
  if (seq[N] !== names[1]) {
    bad.push('next() did not WRAP: after ' + N + ' steps it gave "' + seq[N]
      + '", expected "' + names[1] + '"');
  }
  m.sw.set(names[0]);
  const back = [];
  for (let i = 0; i < N; i += 1) back.push(m.sw.previous());
  for (let i = 0; i < N; i += 1) {
    const want = names[((N - (i + 1)) % N + N) % N];
    if (back[i] !== want) {
      bad.push('previous() step ' + i + ' gave "' + back[i] + '", expected "' + want + '"');
      break;
    }
  }
  if (back[N - 1] !== names[0]) {
    bad.push('previous() did not WRAP back to the first theme: it gave "'
      + back[N - 1] + '"');
  }
  return bad;
}

function arm3(m) {
  const bad = [];
  m.sw.set('theme-2');
  const before = attributeWrites.length;
  const got = m.sw.set('theme-999');
  if (got === 'theme-999') bad.push('an unknown name was ACCEPTED and returned');
  if (attributeWrites.length !== before) {
    bad.push('a refused switch still wrote the attribute '
      + (attributeWrites.length - before) + ' time(s)');
  }
  if (m.doc.documentElement.dataset.theme !== 'theme-2') {
    bad.push('a refused switch moved the document to "'
      + m.doc.documentElement.dataset.theme + '"');
  }
  return bad;
}

function arm4(m) {
  const bad = [];
  bridgeCalls.length = 0;
  m.sw.set('theme-4');
  if (bridgeCalls.length !== 0) {
    bad.push('the switch reached the shell bridge ' + bridgeCalls.length
      + ' time(s): ' + bridgeCalls.slice(0, 3).join(', '));
  }
  const live = m.doc.querySelectorAll('.captions, .status, .history, #status-text');
  for (let i = 0; i < live.length; i += 1) {
    if (live[i]._text !== '') bad.push('the switch wrote text into <' + live[i].tagName + '>');
  }
  return bad;
}

function arm5() {
  const bad = [];
  const manifest = require(path.join(THEMES, 'themes.js'));
  const names = (manifest.themes || []).map((x) => x.name);
  const sheets = ['theme-1.css', 'theme-2.css', 'theme-3.css', 'theme-4.css',
    'theme-5.css', 'cinematic.css', 'panel-designs.css', 'zipc-panels.css'];
  const scopes = new Set();
  for (const s of sheets) {
    const q = path.join(THEMES, s);
    if (!fs.existsSync(q)) continue;
    for (const mm of fs.readFileSync(q, 'utf8')
      .matchAll(/:root\[data-theme=['^]?([^'\]]+)['\]]?/g)) scopes.add(mm[1]);
  }
  const missing = names.filter((n) => !scopes.has(n));
  if (missing.length) {
    bad.push('manifest entries with NO CSS scope (a switch would paint nothing): '
      + missing.join(', '));
  }
  return bad;
}

function arm6(m, ctx) {
  const bad = [];
  /* ONE store, two mounts: the restart is the same profile coming back, and a
   * fresh empty store would test nothing but my own scaffolding. */
  const store = {};
  const first = mountFresh('restart-a', 'panel', 'ok', ctx.src, store);
  first.sw.set('theme-5');
  if (first.sw.last() !== 'theme-5') {
    bad.push('last() is "' + first.sw.last() + '", expected "theme-5"');
  }
  const again = mountFresh('restart-b', 'panel', 'ok', ctx.src, store);
  if (again.doc.documentElement.dataset.theme !== 'theme-5') {
    bad.push('after a restart the document wears "'
      + again.doc.documentElement.dataset.theme + '", expected "theme-5"');
  }
  return bad;
}

function arm7(m, ctx) {
  const bad = [];
  const throwing = mountFresh('throwing', 'panel', 'throw', ctx.src);
  const got = throwing.sw.set('theme-1');
  if (got !== 'theme-1') bad.push('with localStorage throwing, set(theme-1) returned "' + got + '"');
  if (throwing.doc.documentElement.dataset.theme !== 'theme-1') {
    bad.push('with localStorage throwing, the document wears "'
      + throwing.doc.documentElement.dataset.theme + '"');
  }
  return bad;
}

function arm8(m) {
  const bad = [];
  const before = attributeWrites.length;
  m.sw.mount();
  m.sw.mount();
  if (attributeWrites.length !== before) {
    bad.push('a second mount() wrote the attribute ' + (attributeWrites.length - before)
      + ' time(s)');
  }
  const buttons = m.doc.querySelectorAll('[data-theme-button]');
  for (const b of buttons) {
    const wired = (b._listeners.click || []).length;
    if (wired !== 1) {
      bad.push('after three mount() calls the button #' + b.id + ' carries ' + wired
        + ' click listener(s), expected 1');
    }
  }
  return bad;
}

const ARMS = [
  ['ARM 1 the switch is ONE attribute write', arm1],
  ['ARM 2 the cycle is a RING that wraps', arm2],
  ['ARM 3 an unknown name is REFUSED', arm3],
  ['ARM 4 the switch touches nothing else', arm4],
  ['ARM 5 every manifest entry is reachable', arm5],
  ['ARM 6 the stored choice comes back', arm6],
  ['ARM 7 persistence is defensive', arm7],
  ['ARM 8 mount is idempotent', arm8]
];

/* ── the mutants ───────────────────────────────────────────────────────────── */
const MUTANTS = [
  ['M1 the attribute write is removed',
    '      el.dataset.theme = theme.name;',
    '      /* MUTANT M1: the switch no longer writes the attribute */'],
  ['M2 the unknown-name refusal is removed',
    '      var theme = known(name);\r\n      if (!theme) return currentTheme();',
    '      var theme = known(name) || { name: name };  /* MUTANT M2 */'],
  ['M3 the store write is removed',
    '      if (!opts || opts.persist !== false) writeStore(theme.name);',
    '      /* MUTANT M3: the choice is not persisted */']
];

function runLive() {
  const fails = [];
  const ctx = { src: null };
  const m = mountFresh('live', 'panel', 'ok', ctx.src);
  for (const [label, fn] of ARMS) {
    let got = [];
    try { got = fn(m, ctx); } catch (e) { got = [label + ' raised ' + e.message]; }
    for (const line of got) fails.push(label + ': ' + line);
  }
  return fails;
}

/* ── the negative arm ────────────────────────────────────────────────────────
 * The contract every other oracle in this house keeps: the control run EXITS 0
 * when it worked, i.e. when EVERY mutant went RED on the arm that owns it. An
 * exit code of 1 here would mean "a mutant is still green and this gate cannot
 * say no", which is the failure worth failing on. The shipped module is also
 * re-run inside the same command, so a module that fails EVERYTHING cannot pass
 * as a control. */
function runNeg() {
  const src = fs.readFileSync(path.join(PANEL, 'theme-switcher.js'), 'utf8');
  const live = runLive();
  const lines = [];
  let ok = live.length === 0;
  lines.push('control: the shipped module is GREEN (' + live.length + ' failure(s))');
  for (const f of live) lines.push('   LIVE ' + f);

  for (let i = 0; i < MUTANTS.length; i += 1) {
    const [label, oldText, newText] = MUTANTS[i];
    const n = src.split(oldText).length - 1;
    if (n !== 1) {
      ok = false;
      lines.push('NEG-ARM ' + label + ': CONTROL IS DEAD (anchor count=' + n + ')');
      continue;
    }
    /* A DIRECTORY OF ITS OWN PER MUTANT, and this is load-bearing: require
     * caches by resolved path, so two mutants sharing one scratch file would
     * make the second one silently re-run the FIRST one's bytes -- a control
     * that measures the wrong mutant and reports whatever it finds. */
    const ctx = { src: src.replace(oldText, newText) };
    const m = mountFresh('neg-' + i, 'panel', 'ok', ctx.src);
    const got = [];
    for (const [alabel, fn] of ARMS) {
      let bad = [];
      try { bad = fn(m, ctx); } catch (e) { bad = [alabel + ' raised ' + e.message]; }
      for (const line of bad) got.push(alabel + ': ' + line);
    }
    const red = got.length > 0;
    if (!red) ok = false;
    lines.push('NEG-ARM ' + label + ': ' + (red ? 'RED as expected' : 'STILL GREEN -- the oracle cannot say no'));
    for (const line of got.slice(0, 4)) lines.push('        ' + line);
  }
  return { ok: ok, lines: lines };
}

say('== SOTTO theme switching oracle ==');
say('module = ' + path.join(PANEL, 'theme-switcher.js'));
say('bytes  = ' + fs.statSync(path.join(PANEL, 'theme-switcher.js')).size);
say('mode   = ' + (NEG ? 'NEG-ARM (defect injected in a COPY)' : 'shipped module'));
if (NEG) {
  const r = runNeg();
  for (const l of r.lines) say('   ' + (l.length > 170 ? l.slice(0, 170) + '...' : l));
  say('VERDICT: ' + (r.ok ? 'PASS' : 'FAIL') + '  (every mutant RED=' + r.ok + ')');
  process.exit(r.ok ? 0 : 1);
}
const fails = runLive();
for (const f of fails) say('   ' + (f.length > 170 ? f.slice(0, 170) + '...' : f));
say('VERDICT: ' + (fails.length ? 'FAIL' : 'PASS') + '  (' + fails.length + ' failure(s))');
process.exit(fails.length ? 1 : 0);
