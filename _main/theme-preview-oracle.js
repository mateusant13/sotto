/* Sotto — the oracle for the THEME PREVIEW (lane S6, 2026-10-12).
 *
 * Run:  node _main/theme-preview-oracle.js            -> PASS/FAIL, exit 0/1
 *       node _main/theme-preview-oracle.js --neg-arm  -> also proves the LIVENESS
 *                                                       gate can go RED
 *
 * WHAT THIS FILE IS FOR. The owner asked for a theme dropdown where hovering a
 * theme shows the preview "sem travamento e super otimizado". The risk is not a
 * crash — it is a preview that WORKS (it paints the theme) and costs the panel a
 * forced recalculation per hovered option, because the tuning layer's
 * MutationObserver answers every data-theme write with a full apply(). That is
 * the freeze he described, and it is invisible to any test that only checks "the
 * theme changed".
 *
 * So the arms here are about COST, not just effect:
 *   ARM 1  the manifest really enumerates N themes (49 today), no duplicates.
 *   ARM 2  a hover applies theme X to <html data-theme> — the effect.
 *   ARM 3  the preview writes ZERO bytes to localStorage — the store is the
 *          owner's choice, and a preview must not touch it.
 *   ARM 4  the preview makes ZERO bridge/worker calls — the shell is the only
 *          thing that can talk to the worker, and a preview must not reach it.
 *   ARM 5  a commit persists; a revert restores the committed theme.
 *   ARM 6  keyboard: arrows move the focus (and preview), Enter commits, Escape
 *          reverts.
 *   ARM 7  COALESCING: N hovers inside one frame cost ONE attribute write.
 *   ARM 8  the tuning layer runs ZERO applies during a preview and EXACTLY ONE
 *          at the commit that ends it.
 *   ARM 9  the warm path (fonts/images) runs off the open path.
 *   ARM 10 (--neg-arm) three mutants of the shipped file — the deferral removed,
 *          the preview made persistent, the coalescing removed — each goes RED
 *          on the arm that owns it. A gate that cannot say NO is not a gate.
 *
 * ── THE RE-ANCHOR ARMS (2026-10-12, lane S6-R) ────────────────────────────
 * The dropdown used to be anchored on `#strip-theme-chevron`, on the STRIP
 * surface, because that was then the only theme control reachable there. The
 * panel lane then shipped the owner's layout (`fae207a`): *"o painel de baixo,
 * deve conter apenas o bare minimum"*, so the list had to move to the RIGHT
 * panel (`body[data-surface="panel"]`) where every other control lives. These
 * arms pin WHERE the door is, in both colours:
 *   ARM 11 the dropdown trigger is REACHABLE on the RIGHT panel — it is wired,
 *          it lives in `.panel__controls`, clicking it opens `#theme-dropdown`,
 *          and the list escapes the panel because it is a BODY-level popup.
 *          STRIP STAYS BARE: the module builds no strip chevron, no chevron in
 *          the document sits in the strip bar, and `#strip-theme-button` still
 *          CYCLES instead of opening a list.
 *   ARM 12 a chevron the strip bar SHIPS is refused — not wired, no listener —
 *          so the strip cannot regain a door with a markup line alone, while
 *          the panel chevron keeps opening the list (the control arm: without
 *          it a module that wired NOTHING would pass too).
 *   ARM 13 STATIC EVIDENCE in the shipped bytes: panel.html, panel.css and
 *          theme-switcher.js each carry their half of the re-anchor, and the
 *          switcher never creates a stylesheet — so the only way a deferred
 *          theme's CSS can arrive is the ask `lazy-assets.js` makes, which is
 *          what makes that ask load-bearing.
 *   ARM 14 (--neg-arm) three further mutants, each breaking a different half of
 *          the re-anchor — the strip chevron restored, the strip-bar guard
 *          removed, the panel trigger deleted — each goes RED on its own arm.
 *
 * NOTHING HERE LAUNCHES THE APP. The DOM is a shim: the panel is served over
 * file:// and the shell is the owner's single instance, so this oracle drives the
 * real modules against a fake document and counts what they do.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PANEL = path.join(ROOT, 'app', 'panel');

const results = [];
let failures = 0;

function check(name, ok, detail) {
  results.push({ name, ok: Boolean(ok), detail: detail === undefined ? '' : String(detail) });
  if (!ok) failures += 1;
}
function eq(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  check(name, a === e, a === e ? a : 'got ' + a + ', want ' + e);
}

/* ══════════════════════════════════════════════════════════════════════════
 * THE DOM SHIM. Enough of a document for the two modules to run against, and
 * nothing more: every method here either records a fact the arms read or is a
 * no-op. The point is that the modules under test cannot tell the difference.
 * ══════════════════════════════════════════════════════════════════════════ */

var rafQueue = [];
var idleQueue = [];
var storeWrites = [];          // every localStorage.setItem, in order
var bridgeCalls = [];          // every call on the shell bridge
var computedReads = 0;          // every getComputedStyle
var attributeWrites = [];      // every data-theme write, in order
var styleMutations = 0;        // every setProperty/removeProperty on <html>

function resetCounters() {
  rafQueue = [];
  idleQueue = [];
  storeWrites = [];
  bridgeCalls = [];
  computedReads = 0;
  attributeWrites = [];
  styleMutations = 0;
}

/* The MutationObserver the tuning layer installs fires its callback on a
 * MICROTASK after the attribute write, exactly as the browser does. Node cannot
 * drain that queue synchronously (Atomics.wait does not yield to it in Node), so
 * the frame pump yields to the real event loop for one slice: microtasks queued by
 * the frame's writes run before the next line. */
var _flushResolver = null;
function flush() {
  return new Promise(function (resolve) { setImmediate(resolve); });
}

/* Drive one animation frame: run the callbacks that were queued for it, then let
 * the microtasks those writes queued run. */
async function tick(n) {
  var k = n || 1;
  for (var i = 0; i < k; i += 1) {
    var q = rafQueue;
    rafQueue = [];
    for (var j = 0; j < q.length; j += 1) q[j]();
  }
  await flush();
}
function tickIdle() {
  var q = idleQueue;
  idleQueue = [];
  for (var i = 0; i < q.length; i += 1) q[i]();
}

function makeStyle() {
  var props = {};
  return {
    setProperty: function (k, v) { props[k] = v; styleMutations += 1; },
    removeProperty: function (k) { delete props[k]; styleMutations += 1; },
    getPropertyValue: function (k) { return Object.prototype.hasOwnProperty.call(props, k) ? props[k] : ''; }
  };
}

function walkAll(n, out) {
  out.push(n);
  for (var i = 0; i < n.children.length; i += 1) walkAll(n.children[i], out);
  return out;
}
function findById(n, id) {
  var all = walkAll(n, []);
  for (var i = 0; i < all.length; i += 1) if (all[i]._attrs && all[i]._attrs.id === id) return all[i];
  return null;
}
function makeElement(tag) {
  var el = {
    tagName: String(tag || 'div').toUpperCase(),
    children: [],
    listeners: {},
    dataset: {},
    style: makeStyle(),
    hidden: false,
    isConnected: true,
    parentNode: null,
    firstChild: null,
    nextSibling: null,
    _text: '',
    className: '',
    _attrs: {},
    setAttribute: function (k, v) { this._attrs[k] = String(v); },
    getAttribute: function (k) { return Object.prototype.hasOwnProperty.call(this._attrs, k) ? this._attrs[k] : null; },
    removeAttribute: function (k) { delete this._attrs[k]; },
    appendChild: function (c) { c.parentNode = this; this.children.push(c); this.firstChild = this.children[0] || null; return c; },
    prepend: function (c) { c.parentNode = this; this.children.unshift(c); this.firstChild = this.children[0] || null; return c; },
    append: function (c) { return this.appendChild(c); },
    insertBefore: function (c, ref) {
      c.parentNode = this;
      var i = ref ? this.children.indexOf(ref) : -1;
      if (i < 0) this.children.push(c); else this.children.splice(i, 0, c);
      this.firstChild = this.children[0] || null;
      return c;
    },
    addEventListener: function (type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    removeEventListener: function () {},
    dispatch: function (type, ev) {
      ev = ev || {};
      ev.type = type;
      ev.target = ev.target || this;
      if (!ev.preventDefault) ev.preventDefault = function () {};
      if (!ev.stopPropagation) ev.stopPropagation = function () {};
      var ls = this.listeners[type] || [];
      for (var i = 0; i < ls.length; i += 1) ls[i].call(this, ev);
    },
    focus: function () { doc.activeElement = this; this.dispatch('focus'); },
    contains: function (n) {
      if (n === this) return true;
      for (var i = 0; i < this.children.length; i += 1) if (this.children[i].contains && this.children[i].contains(n)) return true;
      return false;
    },
    querySelector: function (sel) { return this.querySelectorAll(sel)[0] || null; },
    /* A SMALL BUT REAL selector engine, because the re-anchor arms ask the
     * module WHERE it mounted and the module answers with a selector list.
     * Supported per comma member, nothing else: `.class`, `#id`, `[attr]`,
     * `tag`. A COMPOUND selector (`.x[attr="v"]`, `#a .b`) still matches NOTHING —
     * that is deliberate and load-bearing: `openDropdown()` focuses
     * `.theme-dropdown__option[aria-current="true"]` and falls back to the
     * first option, and making that compound selector start matching would
     * change which option ARM 5-7 focus and therefore what they measure. */
    querySelectorAll: function (sel) {
      var out = [];
      var seen = [];
      var parts = String(sel).split(',');
      for (var p = 0; p < parts.length; p += 1) {
        var s = parts[p].trim();
        var m = null;
        if (/^\.[\w-]+$/.test(s)) m = { kind: 'class', value: s.slice(1) };
        else if (/^#[\w-]+$/.test(s)) m = { kind: 'id', value: s.slice(1) };
        else if (/^\[[\w-]+\]$/.test(s)) m = { kind: 'attr', value: s.slice(1, -1) };
        else if (/^[a-zA-Z][\w-]*$/.test(s)) m = { kind: 'tag', value: s.toLowerCase() };
        if (!m) continue;
        (function walk(n) {
          for (var i = 0; i < n.children.length; i += 1) {
            var c = n.children[i];
            var hit = false;
            if (m.kind === 'class') hit = !!(c.className && String(c.className).split(/\s+/).indexOf(m.value) >= 0);
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
  /* `el.id = x` in a real element sets the id ATTRIBUTE; the shim stores
   * attributes in `_attrs`, so route the property through it. */
  Object.defineProperty(el, 'id', {
    get: function () { return this._attrs.id || ''; },
    set: function (v) { this._attrs.id = String(v); },
    configurable: true
  });
  return el;
}

/* The documentElement's dataset is the whole hot path: the switcher writes
 * `el.dataset.theme = name` and the tuning layer's observer must be told about
 * it. A plain object would do the write and drop the notification, so this shim
 * RECORDS the write (the arms count them) and fires the observer hook. */
var htmlEl = makeElement('html');
(function () {
  var real = {};
  htmlEl.dataset = new Proxy(real, {
    set: function (t, k, v) {
      t[k] = v;
      if (k === 'theme') attributeWrites.push(String(v));
      if (htmlEl._observeHook) htmlEl._observeHook();
      return true;
    },
    get: function (t, k) { return t[k]; },
    has: function (t, k) { return k in t; }
  });
})();
var bodyEl = makeElement('body');
installDocument(makePanelDoc({ surface: 'panel' }));

/* ── THE TWO SURFACES, MODELLED AS THE SHIPPED PAGE MODELS THEM ─────────────
 * `body[data-surface]`. `panel` is the FULL column: a `.panel__header` holding
 * `.panel__controls`, the cluster every button lives in — the RIGHT panel of the
 * owner's 2026-10-12 layout. `strip` is the short bar: `.stripbar`, which is the
 * ONLY thing the strip surface keeps, and which carries exactly one theme
 * control, `#strip-theme-button`, the one that CYCLES. Combined with the selector
 * engine above, this is what lets the re-anchor arms ask the module where it
 * mounted instead of asserting a byte pattern.
 *
 * `makePanelDoc(opts)` builds either surface. `opts.stripChevron` is the
 * regression case ARM 12 needs: a `#strip-theme-chevron` SHIPPED IN THE STRIP
 * BAR, which the module must refuse. */
function makePanelDoc(opts) {
  opts = opts || {};
  var body = makeElement('body');
  body.dataset.surface = opts.surface || 'panel';

  /* The RIGHT panel: `.panel__header` is `display:none` on the strip surface in
   * the real sheet, so the cluster is genuinely panel-only. */
  var header = makeElement('header');
  header.className = 'panel__header';
  var controls = makeElement('div');
  controls.className = 'panel__controls';
  controls._attrs.id = 'panel-controls';
  header.appendChild(controls);
  body.appendChild(header);

  /* The strip bar, `panel.html:610`. Its theme button is markup, it carries
   * `data-theme-button`, and the module must NOT build a neighbour for it. */
  var stripbar = makeElement('section');
  stripbar.className = 'stripbar';
  stripbar._attrs.id = 'strip-controls';
  var live = makeElement('button');
  live._attrs.id = 'strip-live-button';
  stripbar.appendChild(live);
  var theme = makeElement('button');
  theme.className = 'strip-button strip-button--theme';
  theme._attrs.id = 'strip-theme-button';
  theme._attrs['data-theme-button'] = 'true';
  theme.dataset.themeButton = 'true';
  stripbar.appendChild(theme);
  if (opts.stripChevron) {
    var sc = makeElement('button');
    sc.className = 'strip-button strip-button--chevron';
    sc._attrs.id = 'strip-theme-chevron';
    sc.dataset.themeChevron = 'true';
    sc._attrs['aria-controls'] = 'theme-dropdown';
    stripbar.appendChild(sc);
  }
  body.appendChild(stripbar);
  return body;
}

/* The host page's own control cluster and strip theme button — the markup the
 * switcher looks for before it creates its own chevron. Without them the
 * switcher builds nothing and the warm path never arms. The default document is
 * the PANEL surface, which is the one `panel.html` opens on. */
var panelControls = null;   // filled in by installDocument()
var stripThemeButton = null;

/* Swap the document under the running shim. Used by the default setup and by
 * every arm that needs a document of its own; the shim is rebuilt rather than
 * mutated so an arm cannot inherit another arm's elements. */
function installDocument(body) {
  bodyEl = body || makePanelDoc({ surface: 'panel' });
  panelControls = bodyEl.querySelector('.panel__controls');
  stripThemeButton = bodyEl.querySelector('#strip-theme-button');
  return bodyEl;
}

var docListeners = {};
var registry = {};
var doc = {
  documentElement: htmlEl,
  body: bodyEl,
  activeElement: null,
  readyState: 'complete',
  fonts: { load: function () { return Promise.resolve(); } },
  createElement: function (t) { return makeElement(t); },
  createElementNS: function (ns, t) { return makeElement(t); },
  getElementById: function (id) { return findById(bodyEl, id); },
  querySelector: function (sel) { return bodyEl.querySelector(sel); },
  querySelectorAll: function (sel) { return bodyEl.querySelectorAll(sel); },
  addEventListener: function (type, fn) { (docListeners[type] = docListeners[type] || []).push(fn); },
  dispatch: function (type, ev) {
    ev = ev || {}; ev.type = type;
    if (!ev.preventDefault) ev.preventDefault = function () {};
    if (!ev.stopPropagation) ev.stopPropagation = function () {};
    var ls = docListeners[type] || [];
    for (var i = 0; i < ls.length; i += 1) ls[i].call(doc, ev);
  }
};

/* The shell bridge: the ONLY way the panel talks to the worker. A preview that
 * reaches it is a preview that can cost the owner a transcription. */
var bridge = new Proxy({}, {
  get: function (t, prop) {
    if (prop === 'history') return { append: function () { bridgeCalls.push('history.append'); } };
    return function () { bridgeCalls.push(String(prop)); };
  }
});

var store = {};
var localStorageShim = {
  getItem: function (k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
  setItem: function (k, v) { storeWrites.push(String(k)); store[String(k)] = String(v); },
  removeItem: function (k) { delete store[k]; }
};

var rootListeners = {};
var root = {
  document: doc,
  localStorage: localStorageShim,
  navigator: { userAgent: 'sotto-oracle' },
  performance: { now: function () { return Date.now(); } },
  requestAnimationFrame: function (fn) { rafQueue.push(fn); return rafQueue.length; },
  cancelAnimationFrame: function () {},
  requestIdleCallback: function (fn) { idleQueue.push(fn); return idleQueue.length; },
  setTimeout: function (fn) { fn(); return 0; },
  clearTimeout: function () {},
  addEventListener: function (type, fn) { (rootListeners[type] = rootListeners[type] || []).push(fn); },
  dispatch: function (type, ev) {
    ev = ev || {}; ev.type = type;
    var ls = rootListeners[type] || [];
    for (var i = 0; i < ls.length; i += 1) ls[i].call(root, ev);
  },
  sotto: bridge,
  SottoThemeManifest: null,
  SottoTheme: null,
  SottoThemeTune: null
};

/* The MutationObserver the tuning layer installs. It must be REAL enough that
 * the deferral logic is exercised: a callback that fires on the next microtask
 * after an attribute write, exactly as the browser does. */
function MutationObserverShim(fn) {
  this.fn = fn;
  this.observing = null;
}
MutationObserverShim.prototype.observe = function (target, opts) {
  this.observing = { target: target, opts: opts };
  var self = this;
  var prev = target._observeHook;
  target._observeHook = function () {
    if (prev) prev.call(target);
    queueMicrotask(function () { self.fn([{ type: 'attributes', attributeName: 'data-theme' }]); });
  };
};
MutationObserverShim.prototype.disconnect = function () { this.observing = null; };
root.MutationObserver = MutationObserverShim;

root.Image = function () {
  this.decoding = '';
  this.src = '';
  this.complete = true;
};

/* getComputedStyle: the tuning layer reads the alpha of a colour companion
 * from the computed value. Counted, because a forced recalculation is the cost
 * the deferral exists to avoid. */
var getComputedStyleShim = function (el) {
  computedReads += 1;
  return { getPropertyValue: function () { return 'rgba(242, 233, 216, 0.12)'; } };
};

/* The manifest modules are browser scripts: two of them reach for a bare
 * `window` (skins.js:8 assigns `window.SOTTO_SKINS`). In Node that global does
 * not exist, so the shim installs itself under the name they expect. */
global.window = root;

/* A FRESH document for the negative arms. The shim's document is ONE object
 * for the whole process, so a second mount of the switcher would reuse the FIRST
 * module's #theme-dropdown: the hover would then be answered by that module's
 * listeners, the mutant would look inert, and the original would keep working
 * behind its back. Each neg-arm therefore gets its own html/body/anchors, and the
 * helpers read the CURRENT document through the module-level `doc`. */
/* ── A FRESH DOCUMENT for the negative arms and the re-anchor arms ──────────
 * The shim's document is ONE object for the whole process, so a second mount of
 * the switcher would reuse the FIRST module's #theme-dropdown: the hover would
 * then be answered by that module's listeners, the mutant would look inert, and
 * the original would keep working behind its back. Each arm therefore gets its
 * own html/body/anchors, and the helpers read the CURRENT document through the
 * module-level `doc`. `makeDocument` is now the surface-aware factory the main
 * shim uses too, so both paths see the same two surfaces. */
function makeDocument(opts) {
  var h = makeElement('html');
  h.dataset = new Proxy({}, {
    set: function (t, k, v) {
      t[k] = v;
      if (k === 'theme') attributeWrites.push(String(v));
      if (h._observeHook) h._observeHook();
      return true;
    },
    get: function (t, k) { return t[k]; },
    has: function (t, k) { return k in t; }
  });
  var b = makePanelDoc(opts);
  var d = {
    documentElement: h,
    body: b,
    activeElement: null,
    readyState: 'complete',
    fonts: { load: function () { return Promise.resolve(); } },
    createElement: function (t) { return makeElement(t); },
    createElementNS: function (ns, t) { return makeElement(t); },
    getElementById: function (id) { return findById(b, id); },
    querySelector: function (sel) { return b.querySelector(sel); },
    querySelectorAll: function (sel) { return b.querySelectorAll(sel); },
    addEventListener: function (type, fn) { (docListeners[type] = docListeners[type] || []).push(fn); },
    dispatch: function (type, ev) {
      ev = ev || {}; ev.type = type;
      if (!ev.preventDefault) ev.preventDefault = function () {};
      if (!ev.stopPropagation) ev.stopPropagation = function () {};
      var ls = docListeners[type] || [];
      for (var i = 0; i < ls.length; i += 1) ls[i].call(d, ev);
    }
  };
  return d;
}

/* House rule: anything temp goes to I:/cc-tmp (G: fills and kills lanes). */
var TMP_BASE = (function () {
  var cands = ['I:/cc-tmp', process.env.TMPDIR, process.env.TEMP, require('os').tmpdir()];
  for (var i = 0; i < cands.length; i += 1) {
    if (!cands[i]) continue;
    try { fs.mkdirSync(cands[i], { recursive: true }); return cands[i]; } catch (e) { }
  }
  return require('os').tmpdir();
})();

/* MOUNT A PRIVATE COPY of the two modules against a document of its own, on a
 * directory of its own so `require` re-executes them (the neg-arms and the
 * re-anchor arms both need a fresh mount, and a cached module would carry the
 * first one's listener list and its dropdown). `switcherSrc` optional: a
 * MUTANT. Returns { sw, tn, doc }. */
function mountFresh(label, docOpts, switcherSrc) {
  var dir = path.join(TMP_BASE, 's6-anchor-' + label);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'theme-switcher.js'),
                  switcherSrc || fs.readFileSync(path.join(PANEL, 'theme-switcher.js'), 'utf8'));
  fs.writeFileSync(path.join(dir, 'theme-tune.js'),
                  fs.readFileSync(path.join(PANEL, 'theme-tune.js'), 'utf8'));
  var d = makeDocument(docOpts);
  doc = d;
  root.document = d;
  resetCounters();
  var sw = require(path.join(dir, 'theme-switcher.js'));
  var tn = require(path.join(dir, 'theme-tune.js'));
  root.SottoTheme = sw;
  root.SottoThemeTune = tn;
  sw.mount();
  tn.apply();
  resetCounters();
  return { sw: sw, tn: tn, doc: d };
}

/* Load the real modules against the shim, in the panel's own order. */
function loadModules() {
  resetCounters();
  root.SottoThemeManifest = null;
  root.SottoTheme = null;
  root.SottoThemeTune = null;
  /* Clear the dataset WITHOUT replacing the proxy: the proxy is what records
   * the writes and notifies the observer. */
  for (var dk in htmlEl.dataset) if (Object.prototype.hasOwnProperty.call(htmlEl.dataset, dk)) delete htmlEl.dataset[dk];
  htmlEl.style = makeStyle();
  store = {};
  storeWrites = [];

  require(path.join(PANEL, 'themes', 'themes.js'));
  require(path.join(PANEL, 'themes', 'panel-designs.js'));
  require(path.join(PANEL, 'skins', 'skins.js'));
  require(path.join(PANEL, 'theme-switcher.js'));
  require(path.join(PANEL, 'theme-tune.js'));

  root.SottoTheme.mount();
  root.SottoThemeTune.apply();
}

/* The dropdown options, in manifest order. */
function options() {
  return doc.querySelectorAll('.theme-dropdown__option');
}
function optionByName(name) {
  var o = options();
  for (var i = 0; i < o.length; i += 1) if (o[i].dataset.themeChoice === name) return o[i];
  return null;
}
/* The ONLY door: the RIGHT panel's chevron. Before the 2026-10-12 re-anchor this
 * helper reached for the strip chevron first, because that was where the
 * dropdown was anchored and the strip was the surface with a control. Now it is
 * the other way round — and ARM 11 asserts this resolves to a chevron inside
 * `.panel__controls`, so a lane that re-anchors it back goes RED here rather than
 * quietly measuring the wrong element. */
function panelChevron() {
  var chev = doc.getElementById('theme-chevron') || doc.querySelector('.panel__controls [data-theme-chevron]');
  return chev || null;
}
function openDropdown() {
  var chev = panelChevron();
  if (chev) chev.dispatch('click');
}
function hover(name) { var o = optionByName(name); if (o) o.dispatch('mouseenter'); }
function clickOption(name) { var o = optionByName(name); if (o) o.dispatch('click'); }
function keyOn(el, key) { el.dispatch('keydown', { key: key }); }
/* Reset the shim counters AND leave the switcher in the closed, committed
 * state, so one arm's preview cannot leak into the next as an open dropdown. */
function resetAll() {
  resetCounters();
  if (root.SottoTheme && typeof root.SottoTheme.closeDropdown === 'function') root.SottoTheme.closeDropdown();
}

/* A snapshot of the switcher's own counters, so an arm can measure the DELTA it
 * caused instead of the whole run. */
function statSnap() {
  var s = root.SottoTheme.stats();
  return {
    hoverEvents: s.hoverEvents, focusEvents: s.focusEvents, applies: s.applies,
    commits: s.commits, reverts: s.reverts, frames: s.frames,
    coalescedDrops: s.coalescedDrops, storeWrites: s.storeWrites,
    shellCalls: s.shellCalls, warmFonts: s.warmFonts, warmImages: s.warmImages,
    warmMs: s.warmMs, previewWindowOpen: s.previewWindowOpen
  };
}
function delta(before, after) {
  var out = {};
  for (var k in after) out[k] = after[k] - before[k];
  return out;
}
function tuneSnap() {
  var t = root.SottoThemeTune;
  return { applyCalls: t.applyCalls(), previewDeferred: t.previewDeferred(), swatching: t.swatching() };
}

/* ══════════════════════════════════════════════════════════════════════════
 * ARMS
 * ══════════════════════════════════════════════════════════════════════════ */

loadModules();

/* ── ARMS RUN ASYNC: the observer's microtask must be able to run ───────── */
(async function () {

/* ── ARM 1: the manifest enumerates N themes, no duplicates ───────────────── */
var manifest = root.SottoThemeManifest;
var names = (manifest && manifest.themes || []).map(function (t) { return t.name; });
var seen = {};
var dupes = [];
for (var i = 0; i < names.length; i += 1) {
  if (seen[names[i]]) dupes.push(names[i]);
  seen[names[i]] = true;
}
eq('ARM1 manifest theme count', names.length, 49);
eq('ARM1 no duplicate names', dupes, []);
eq('ARM1 fallback is a real theme', Boolean(manifest.byName(manifest.fallback)), true);
eq('ARM1 every theme has a label', (manifest.themes || []).every(function (t) { return !!t.label; }), true);
eq('ARM1 every theme has a swatch', (manifest.themes || []).every(function (t) { return !!t.swatch; }), true);
eq('ARM1 the switcher lists the same N', root.SottoTheme.list().length, names.length);

/* ── ARM 2: a hover applies theme X ───────────────────────────────────────── */
resetCounters();
var committed0 = root.SottoTheme.current();
var storeBefore = localStorageShim.getItem('sotto.theme');
openDropdown();
hover('theme-3');
await tick(1);
eq('ARM2 hover applies the theme', root.SottoTheme.current(), 'theme-3');
eq('ARM2 the attribute is the only write', attributeWrites, ['theme-3']);

/* ── ARM 3: the preview writes ZERO bytes to the store ────────────────────── */
eq('ARM3 preview store writes', storeWrites, []);
eq('ARM3 the store is untouched by the preview', localStorageShim.getItem('sotto.theme'), storeBefore);

/* ── ARM 4: the preview makes ZERO bridge calls ───────────────────────────── */
eq('ARM4 preview bridge calls', bridgeCalls, []);

/* ── ARM 5: commit persists, revert restores ──────────────────────────────── */
resetCounters();
openDropdown();
hover('theme-4');
await tick(1);
clickOption('theme-4');
eq('ARM5 commit persists', localStorageShim.getItem('sotto.theme'), 'theme-4');
eq('ARM5 commit is one store write', storeWrites.length, 1);
eq('ARM5 commit leaves the attribute on the committed theme', root.SottoTheme.current(), 'theme-4');

resetCounters();
openDropdown();
hover('theme-2');
await tick(1);
var opts = options();
keyOn(opts[0], 'Escape');
await tick(1);
eq('ARM5 revert restores the committed theme', root.SottoTheme.current(), 'theme-4');
eq('ARM5 revert writes nothing to the store', storeWrites, []);

/* ── ARM 6: keyboard ──────────────────────────────────────────────────────── */
resetCounters();
openDropdown();
var first = options()[0];
first.focus();
await tick(1);
var afterFocus = root.SottoTheme.current();
keyOn(first, 'ArrowDown');
await tick(1);
var afterDown = root.SottoTheme.current();
keyOn(optionByName(afterDown) || first, 'ArrowUp');
await tick(1);
var afterUp = root.SottoTheme.current();
check('ARM6 ArrowDown previews a different theme', afterDown !== afterFocus,
  'focus=' + afterFocus + ' down=' + afterDown);
check('ARM6 ArrowUp previews a different theme again', afterUp !== afterDown,
  'down=' + afterDown + ' up=' + afterUp);
keyOn(optionByName(afterUp) || first, 'Enter');
await tick(1);
eq('ARM6 Enter commits the previewed theme', localStorageShim.getItem('sotto.theme'), afterUp);

resetCounters();
openDropdown();
hover('theme-5');
await tick(1);
keyOn(optionByName('theme-5'), 'Escape');
await tick(1);
eq('ARM6 Escape reverts to the committed theme', root.SottoTheme.current(), afterUp);
eq('ARM6 Escape writes nothing', storeWrites, []);

/* ── ARM 7: COALESCING — N hovers in one frame cost ONE write ─────────────── */
resetAll();
var sb7 = statSnap();
openDropdown();
var sweep = ['theme-1', 'theme-2', 'theme-3', 'theme-4', 'theme-5', 'pd-tele', 'cine-adobe', 'cine-harbor'];
for (var s = 0; s < sweep.length; s += 1) hover(sweep[s]);
eq('ARM7 no write before the frame (they are coalesced)', attributeWrites.length, 0);
await tick(1);
eq('ARM7 N hovers in one frame = 1 attribute write', attributeWrites.length, 1);
eq('ARM7 the write is the LAST hovered theme (latest wins)', attributeWrites[0], sweep[sweep.length - 1]);
eq('ARM7 the frame applies it', root.SottoTheme.current(), sweep[sweep.length - 1]);
var d7 = delta(sb7, statSnap());
eq('ARM7 the frame is one apply', d7.applies, 1);
eq('ARM7 the events are all counted', d7.hoverEvents, sweep.length);
eq('ARM7 the frame is one frame', d7.frames, 1);
eq('ARM7 the coalescer dropped the rest', d7.coalescedDrops, sweep.length - 1);

/* Count the tuning layer's DIRECT applies (the commit path), separately
 * from the module's own applyCalls() (which counts the observer's deferred
 * applies). The commit applies via applyTune -> tune.apply, which the module's
 * counter does not see. */
var directApplies = 0;
var _realTuneApply = root.SottoThemeTune.apply;
root.SottoThemeTune.apply = function (name) {
  directApplies += 1;
  return _realTuneApply(name);
};

/* ── ARM 8: the tuning layer defers during a preview ──────────────────────── */
resetAll();
directApplies = 0;   // resetAll reverts the previous arm's preview (one apply)
var tune = root.SottoThemeTune;
var tb8 = tuneSnap();
openDropdown();
hover('theme-2');
await tick(1);
var d8a = delta(tb8, tuneSnap());
eq('ARM8 zero applies during the preview', d8a.applyCalls, 0);
eq('ARM8 the deferral is counted', d8a.previewDeferred >= 1, true);
eq('ARM8 zero computed-style reads during the preview', computedReads, 0);
var styleBefore = styleMutations;
clickOption('theme-2');
await tick(1);
var d8b = delta(tb8, tuneSnap());
eq('ARM8 exactly one apply at the commit', directApplies, 1);
check('ARM8 the commit apply wrote the inline properties', styleMutations > styleBefore,
  'before=' + styleBefore + ' after=' + styleMutations);

/* ── ARM 9: the warm path runs off the open path ──────────────────────────── */
resetCounters();
openDropdown();
tickIdle();
var st = root.SottoTheme.stats();
check('ARM9 the warm path ran in an idle slice', st.warmMs >= 0 && (st.warmFonts > 0 || st.warmImages > 0),
  'fonts=' + st.warmFonts + ' images=' + st.warmImages + ' ms=' + st.warmMs);
eq('ARM9 the warm path wrote nothing to the store', storeWrites, []);
eq('ARM9 the warm path made no bridge calls', bridgeCalls, []);

/* ── ARM 10: the preview never reaches the worker, even after a commit ───── */
eq('ARM10 total bridge calls in the whole run', bridgeCalls, []);

/* ══════════════════════════════════════════════════════════════════════════
 * ARM 11/12/13: the re-anchor — the dropdown door is on the RIGHT panel, and
 * the strip is still bare.
 *
 * Owner, 2026-10-12, verbatim: *"o painel de baixo, deve conter apenas o bare
 * minimum"*, *"o terceiro painel, e o da direita. onde deve ter todos os
 * botoes."* The dropdown used to be anchored on #strip-theme-chevron — on the
 * STRIP, the surface that keeps no other button — because the owner's path only
 * ever had one theme control and the strip is where it had to be. The panel lane
 * then shipped its layout (fae207a), so the chevron came out of the strip bar and
 * the list moved to `.panel__controls` on the RIGHT panel. Every control now
 * lives on one surface, and the strip keeps exactly one theme button, which
 * CYCLES.
 *
 * What could still break this, months from now: a lane re-adds a chevron to the
 * strip bar, or removes the one on the panel, or repoints the oracle's own
 * openDropdown() helper. These arms therefore ask the MODULE, not the bytes: they
 * mount a document that models both surfaces (panel.html's real
 * `.panel__header > .panel__controls` plus its `.stripbar`) and assert what
 * the module WIRED and what happens when the owner clicks.
 * ══════════════════════════════════════════════════════════════════════════ */

/* ancestors of an element, outermost first — the classes the chain carries. */
function ancestorClasses(el) {
  var out = [];
  var n = el;
  while (n) {
    if (n.className) out.push(String(n.className).split(/\s+/)[0]);
    n = n.parentNode;
  }
  return out;
}

/* ── ARM 11: the door lives on the RIGHT PANEL ─────────────────────────────── */
var anchor = mountFresh('anchor11', { surface: 'panel' });
var chev11 = anchor.doc.getElementById('theme-chevron');
check('ARM11.1 the module builds its chevron #theme-chevron', !!chev11, chev11 ? chev11.id : 'absent');
var chain11 = ancestorClasses(chev11);
check('ARM11.2 that chevron is inside .panel__controls (the RIGHT panel)',
  chain11.length > 0 && chain11.indexOf('panel__controls') >= 0,
  'chain=' + chain11.join('<'));
check('ARM11.3 that chevron is NOT inside .stripbar',
  chain11.indexOf('stripbar') < 0, 'chain=' + chain11.join('<'));
check('ARM11.4 the chevron it wired advertises the list it controls',
  !!chev11 && chev11.getAttribute('aria-controls') === 'theme-dropdown',
  chev11 ? String(chev11.getAttribute('aria-controls')) : 'absent');

/* The same document models the strip bar, which still ships the ONE theme
 * control the owner keeps — and the module must NOT have built a chevron beside
 * it, which is the defect the re-anchor removed. */
var stripChev11 = anchor.doc.getElementById('strip-theme-chevron');
check('ARM11.5 the module builds NO chevron in the strip bar', !stripChev11,
  stripChev11 ? stripChev11.id + ' at chain ' + ancestorClasses(stripChev11).join('<') : 'none built');
var stripBtn = anchor.doc.getElementById('strip-theme-button');
check('ARM11.6 the strip keeps its one theme button #strip-theme-button', !!stripBtn,
  stripBtn ? stripBtn.id : 'absent');

/* Clicking the panel chevron opens the list — the whole point of the move. */
resetCounters();
if (chev11) chev11.dispatch('click');
var dd11 = anchor.doc.getElementById('theme-dropdown');
check('ARM11.7 clicking the panel chevron opens #theme-dropdown',
  !!dd11 && dd11.hidden === false, dd11 ? 'hidden=' + dd11.hidden : 'no dropdown element');
check('ARM11.8 the dropdown is a BODY-level popup (the panel cannot clip it)',
  !!dd11 && dd11.parentNode === anchor.doc.body,
  dd11 ? 'parent=' + (dd11.parentNode && dd11.parentNode.tagName) : 'absent');

/* ── ARM 12: the STRIP STAYS BARE — it cannot open a list ──────────────────── */
/* A chevron the STRIP BAR ships is refused: not registered, no listener, and
 * clicking it opens nothing. This is the arm that stops a future lane from
 * re-adding the door by editing only the markup. */
var refused = mountFresh('refused12', { surface: 'strip', stripChevron: true });
var shippedStripChev = refused.doc.getElementById('strip-theme-chevron');
check('ARM12.1 a chevron the strip bar ships exists in the document', !!shippedStripChev,
  shippedStripChev ? shippedStripChev.id : 'absent');
check('ARM12.2 the module does NOT register the strip chevron as a door',
  refused.sw.triggers().indexOf(shippedStripChev) < 0
  && refused.sw.triggers().every(function (c) { return !c || !c.contains || !c.contains(shippedStripChev); }),
  refused.sw.triggers().map(function (c) { return c && c.id; }).join(',') || 'none');
check('ARM12.3 the strip chevron carries NO click listener',
  !(shippedStripChev.listeners && shippedStripChev.listeners.click),
  shippedStripChev.listeners && shippedStripChev.listeners.click ? 'has click' : 'no click');

/* Clicking it must open nothing and write nothing. */
resetCounters();
if (shippedStripChev) shippedStripChev.dispatch('click');
var dd12 = refused.doc.getElementById('theme-dropdown');
check('ARM12.4 clicking the strip chevron does NOT open the list',
  !dd12 || dd12.hidden === true, dd12 ? 'hidden=' + dd12.hidden : 'no dropdown');
eq('ARM12.5 clicking the strip chevron wrote nothing to the store', storeWrites, []);

/* THE CONTROL: on the SAME document, the panel chevron still opens the list.
 * Without it, a module that wired NOTHING anywhere would pass ARM 12 too. */
var panelChev12 = refused.doc.getElementById('theme-chevron');
check('ARM12.6 the panel chevron exists on that same document', !!panelChev12,
  panelChev12 ? panelChev12.id : 'absent');
if (panelChev12) panelChev12.dispatch('click');
var dd12b = refused.doc.getElementById('theme-dropdown');
check('ARM12.7 clicking the panel chevron DOES open the list on that document',
  !!dd12b && dd12b.hidden === false, dd12b ? 'hidden=' + dd12b.hidden : 'no dropdown');

/* ── ARM 13: the strip's one button CYCLES, it does not open a list ────────── */
var cycler = mountFresh('cycler13', { surface: 'strip' });
var cycleBtn = cycler.doc.getElementById('strip-theme-button');
check('ARM13.1 the strip theme button is present', !!cycleBtn, cycleBtn ? cycleBtn.id : 'absent');
var beforeCycle = cycler.sw.current();
if (cycleBtn) cycleBtn.dispatch('click');
await tick(1);
check('ARM13.2 clicking it CYCLES the theme (the owner keeps this control)',
  cycler.sw.current() !== beforeCycle, beforeCycle + ' -> ' + cycler.sw.current());
check('ARM13.3 clicking it does NOT open the dropdown',
  !cycler.doc.getElementById('theme-dropdown') || cycler.doc.getElementById('theme-dropdown').hidden === true,
  cycler.doc.getElementById('theme-dropdown') ? 'hidden=' + cycler.doc.getElementById('theme-dropdown').hidden : 'no dropdown');

/* ── ARM 14: THE SHIPPED BYTES carry the re-anchor (static half) ───────────── */
/* The arms above measure what the module DOES. This one measures what the
 * repository SHIPS: the markup no longer carries the strip chevron, the
 * stylesheet no longer builds a door on the strip, and the switcher never builds
 * a stylesheet of its own — so the ONLY way the trigger and the list can fail to
 * paint is by the shell's own gate, which is exactly the dependency the Lead
 * asked to be made visible. */
var htmlBytes = fs.readFileSync(path.join(PANEL, 'panel.html'), 'utf8');
var cssBytes = fs.readFileSync(path.join(PANEL, 'panel.css'), 'utf8');
var swBytes = fs.readFileSync(path.join(PANEL, 'theme-switcher.js'), 'utf8');

check('ARM14.1 panel.html still ships #strip-theme-button (the cycler stays)',
  /id="strip-theme-button"/.test(htmlBytes), 'absent from markup');
check('ARM14.2 panel.html ships NO #strip-theme-chevron',
  !/id="strip-theme-chevron"/.test(htmlBytes), 'present in markup');
check('ARM14.3 panel.html opens on the PANEL surface',
  /<body data-surface="panel">/.test(htmlBytes), 'default surface is not panel');
check('ARM14.4 panel.css hides #strip-theme-chevron on the strip surface',
  /body\[data-surface="strip"\]\s*#strip-theme-chevron\s*\{[^}]*display:\s*none/.test(cssBytes),
  'rule absent');

/* The dropdown itself: the list is refused on the strip, by the surface. */
check('ARM14.5 panel.css refuses .theme-dropdown on the strip surface with !important',
  /body\[data-surface="strip"\]\s*\.theme-dropdown\s*\{[^}]*display:\s*none\s*!important/.test(cssBytes),
  'rule absent');
check('ARM14.6 panel.css still STYLES .theme-dropdown for the panel surface',
  /\.theme-dropdown\s*\{[^}]*position:\s*absolute/.test(cssBytes)
  && /\.theme-dropdown__option\s*\{/.test(cssBytes),
  'base rules absent');
check('ARM14.7 the .theme-chevron rule still exists for the panel',
  /\.theme-chevron\s*\{/.test(cssBytes), 'rule absent');

/* The switcher's own bytes: it must not resurrect the door, and it must not
 * build a stylesheet — the second is what makes the shell's gate the single
 * dependency for the trigger and the list to paint. */
check('ARM14.8 theme-switcher.js no longer builds a strip chevron',
  !/makeChevron\(doc, 'strip-theme-chevron'/.test(swBytes), 'creation block still present');
check('ARM14.9 theme-switcher.js still builds the panel chevron',
  /makeChevron\(doc, 'theme-chevron'/.test(swBytes), 'creation block absent');
check('ARM14.10 theme-switcher.js refuses a chevron the strip bar ships',
  /isPanelChevron/.test(swBytes) && /inStripBar/.test(swBytes), 'guard absent');
check('ARM14.11 theme-switcher.js never creates a stylesheet of its own',
  !/createElement\(['"](?:link|style)['"]\)/.test(swBytes) && !/document\.write/.test(swBytes),
  'a link or style element can bypass the shell gate');
check('ARM14.12 the dropdown\'s own CSS is linked EAGERLY (panel.css)',
  /<link[^>]*href="panel\.css"/.test(htmlBytes), 'panel.css not linked');
check('ARM14.13 the deferred themesheets are NOT linked eagerly',
  !/href="themes\/cinematic\.css"/.test(htmlBytes), 'cinematic.css is linked eagerly');

/* ══════════════════════════════════════════════════════════════════════════
 * ARM 15 (--neg-arm): the gate can go RED. Six mutants of the SHIPPED file,
 * each in its own copy, each expected to fail the arm that owns the property it
 * breaks. M1/M2/M3 are the liveness ones (deferral, persistence, coalescing).
 * M4/M5/M6 are the re-anchor ones: the strip chevron restored, the strip-bar
 * guard removed, the panel trigger deleted. If any of the six stays green the
 * gate is decorative — including the three that existed before this lane.
 *
 * Every mutant goes to I:/cc-tmp (G: fills and kills lanes on this box), each in
 * a directory of its own so `require` re-executes it rather than handing back the
 * cached module that already holds the FIRST mount's dropdown and listeners.
 * ══════════════════════════════════════════════════════════════════════════ */
if (process.argv.indexOf('--neg-arm') >= 0) {
  const src = fs.readFileSync(path.join(PANEL, 'theme-switcher.js'), 'utf8');
  const tuneSrc = fs.readFileSync(path.join(PANEL, 'theme-tune.js'), 'utf8');

  async function withSource(label, switcherSrc, tuneSrc2, arm) {
    const dir = path.join(TMP_BASE, 's6-neg-' + label);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, 'theme-switcher.js'), switcherSrc);
    fs.writeFileSync(path.join(dir, 'theme-tune.js'), tuneSrc2);
    /* A fresh document FIRST: the mutant must build its own dropdown and its own
     * listeners, or it inherits the first mount's elements and measures nothing. */
    doc = makeDocument();
    root.document = doc;
    const sw = require(path.join(dir, 'theme-switcher.js'));
    const tn = require(path.join(dir, 'theme-tune.js'));
    root.SottoTheme = sw;
    root.SottoThemeTune = tn;
    sw.mount();
    tn.apply();
    resetCounters();
    directApplies = 0;
    openDropdown();
    const out = await arm(sw, tn);
    check('neg-arm ' + label + ' goes RED', out === false, String(out));
  }

  /* M1: the deferral removed from the tuning layer — the preview must now cost
   * an apply per hover.
   *
   * NOTE ON THE DOUBLE `openDropdown()` (this one and the one inside `withSource`)
   * — it is NOT a redundancy, and removing it makes the arm go GREEN. `openDropdown`
   * focuses the first option, which queues `flushPreview` on the rAF queue; the arm's
   * `resetCounters()` then CLEARS that queue, so a mutant whose applies are counted
   * from the rAF callback would measure nothing. The second open re-arms the frame
   * the reset just dropped. Leave both calls in place. */
  await withSource('no-defer', src,
      tuneSrc.replace('if (previewOpen()) {', 'if (false) {'), async function (sw, tn) {
    resetCounters();
    openDropdown();
    /* HOVER A THEME THE DOCUMENT IS NOT ALREADY ON. theme-tune.js:978 pays the owed
     * work only when `appliedTheme !== target`, so re-hovering the CURRENT theme is
     * a no-op that fires no apply at all -- and this mutant must COST an apply for
     * the gate to be able to say NO. Picking a differing theme does not change what
     * the mutant breaks; it removes an accident of what the document sat on. */
    var on = doc.documentElement.getAttribute('data-theme');
    hover(on === 'theme-3' ? 'theme-1' : 'theme-3');
    await tick(1);
    console.error('DBG m1 applyCalls=' + tn.applyCalls() + ' on=' + doc.documentElement.getAttribute('data-theme') + ' attr=' + JSON.stringify(attributeWrites) + ' store=' + JSON.stringify(store));
    return tn.applyCalls() === 0;   // mutant: applies ran, so this is false
  });

  /* M2: the preview made persistent — it must now write the store. */
  await withSource('persist-preview', src.replace('api.set(previewTheme, { persist: false });', 'api.set(previewTheme);'), tuneSrc, async function (sw) {
    resetCounters();
    openDropdown();
    hover('theme-3');
    await tick(1);
    /* The mutant persists the preview, so the store now holds a byte. */
    return storeWrites.length === 0;  // mutant: it wrote, so this is false
  });

  /* M3: the coalescing removed — N hovers must now cost N writes. */
  await withSource('no-coalesce', src.replace('if (rafHandle !== null) { stat.coalescedDrops = (stat.coalescedDrops || 0) + 1; return; }', 'flushPreview();'), tuneSrc, async function (sw) {
    resetCounters();
    openDropdown();
    hover('theme-1'); hover('theme-2'); hover('theme-3');
    return attributeWrites.length === 1;  // mutant: 3 writes, so this is false
  });

  /* ── THE RE-ANCHOR MUTANTS (the Lead's required deliverable) ───────────────────
   * These three break the re-anchor in three different ways, so the arms above
   * cannot all be answering one property. Each is a one-string copy of the
   * SHIPPED file: the mutation is a splice into the source text, never an edit to
   * the real module, and the temp copy goes to I:/cc-tmp. */

  /* M4: the strip chevron is built again — the pre-2026-10-12 behaviour. ARM 11.5
   * is the arm that must catch it: the strip bar gains a chevron that the module
   * wired, and the strip is no longer bare. */
  await withSource('strip-chev-restored', src.replace(
    "  var host = doc.querySelector('.panel__controls');",
    "  var host = doc.querySelector('.panel__controls');\r\n" +
    "  if (doc.querySelector('.stripbar')) {\r\n" +
    "    var shost = doc.getElementById('strip-theme-button') ? doc.getElementById('strip-theme-button').parentNode : doc.querySelector('.stripbar');\r\n" +
    "    var sb = doc.createElement('button'); sb.id = 'strip-theme-chevron'; sb.className = 'strip-button'; sb.setAttribute('aria-controls', 'theme-dropdown'); sb.dataset.themeChevron = 'true'; sb.setAttribute('aria-label', 'Escolher tema'); sb.setAttribute('aria-haspopup', 'listbox');\r\n" +
    "    if (shost) shost.insertBefore(sb, doc.getElementById('strip-theme-button') ? doc.getElementById('strip-theme-button').nextSibling : null);\r\n" +
    "    doc.querySelector('.stripbar') && doc.querySelector('.stripbar').appendChild(sb);\r\n" +
    "  }"
  ), tuneSrc, async function (sw) {
    openDropdown();
    return doc.getElementById('strip-theme-chevron') === null;  // mutant: it built one
  });

  /* M5: the strip-bar guard removed from registerChevron — a chevron the strip
   * bar SHIPS is wired again. ARM 12.3 is the arm that must catch it: that
   * chevron carries a click listener and can open the list. */
  await withSource('strip-guard-removed', src.replace(
    'if (!isPanelChevron(btn)) return null;',
    ''
  ), tuneSrc, async function (sw) {
    doc = makeDocument({ surface: 'strip', stripChevron: true });
    root.document = doc;
    sw.mount();
    var sc = doc.getElementById('strip-theme-chevron');
    return !(sc.listeners && sc.listeners.click);  // mutant: it wired a click
  });

  /* M6: the panel trigger is not created at all. ARM 11.7 is the arm that must
   * catch it: no #theme-chevron exists, so clicking the RIGHT panel opens
   * nothing — the trigger is unreachable exactly where the owner put every
   * button. */
  await withSource('panel-chev-removed', src.replace(
    'var host = doc.querySelector(\'.panel__controls\');',
    'var host = null;'
  ), tuneSrc, async function (sw) {
    openDropdown();
    var dd = doc.getElementById('theme-dropdown');
    return !!dd && dd.hidden === false;  // mutant: it never opened
  });
}

/* ══════════════════════════════════════════════════════════════════════════ */
for (var r = 0; r < results.length; r += 1) {
  const x = results[r];
  console.log((x.ok ? '  ok  ' : '  FAIL') + '  ' + x.name + (x.detail && !x.ok ? '  — ' + x.detail : ''));
}
console.log(failures === 0 ? 'VERDICT: PASS' : 'VERDICT: FAIL');
process.exit(failures === 0 ? 0 : 1);

})();   // end of the async ARMS block
