#!/usr/bin/env node
/**
 * panel-row-identity-oracle.js — DOES THE PANEL KEY A CAPTION ROW BY (source, start)?
 *
 * WHY THIS EXISTS. The worker stamps every caption event with an additive 'source'
 * key ('proc:<pid>' / 'device:<name>' / 'file:<name>', OMITTED when there is no
 * source). The panel used to find a row by 'start' ALONE, so two apps whose audio
 * starts in the same second collided: the second commit found the first one's row
 * and REPLACED its text. STEP 4 keys the row by (source, start) instead.
 *
 * WHAT IT MEASURES, AND WHY IT CAN SAY NO. This is not a reimplementation of the
 * panel: it loads the REAL bytes of app/panel/panel.js, the REAL
 * caption-formulation.js and the REAL history-source.js into one node vm context,
 * with a minimal hand-rolled DOM (node builtins only — no jsdom, no npm), and drives
 * the panel through its OWN bridge contract (bridge.onCaption / bridge.onStatus),
 * exactly the entry points the shell uses. The four checks are the contract, not
 * the implementation:
 *
 *   CHK-A   same start, DIFFERENT sources  -> TWO committed rows, each with its own text
 *   CHK-B   same (source, start) again     -> ONE row, text replaced IN PLACE
 *   CHK-C   NO source, same start twice    -> still ONE row (the pre-existing contract)
 *   CHK-C2  NO source at all               -> NO data-source attribute anywhere
 *   CHK-D   a partial for source A         -> never rewrites the live row of source B
 *   CHK-E   commit meta, from the ENGINE   -> the no-source literal stays byte-identical
 *                                             ({route,start,routeSource}, ...,producer:tag)
 *                                             and source is added LAST, only when present
 *   CHK-F   the trim path                  -> the oldest row leaves the DOM and its
 *                                             identity leaves the index with it
 *
 * --neg-arm runs the SAME checks against FOUR mutants, each removing ONE thing from
 * the real bytes in memory (no copy on disk, no fifth file): one engine for every app
 * (A and D must go RED), the row key ignoring the source (A must go RED), the source
 * key moved out of LAST place, and a no-source literal that grows a source key (the
 * last two must go RED on E alone, with every panel arm still GREEN). A green that
 * cannot turn red is a worthless gap, and this command prints every colour.
 *
 * THE SEAM, STATED PLAINLY. There is no WebView2 and no paint here. The fake DOM
 * implements only what the caption path touches; bridge.onStats/getStats are
 * deliberately absent, so wireLevel() takes its own documented early return. Every
 * claim below is about the DOM the panel builds in this process — NOT about what a
 * browser paints (see the receipt's NOT-MEASURED list).
 *
 * Usage:  node _main/panel-row-identity-oracle.js            (as shipped)
 *         node _main/panel-row-identity-oracle.js --neg-arm  (both colours)
 * Exit:   0 = VERDICT: PASS   1 = VERDICT: FAIL   2 = SETUP ERROR
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');
const cp = require('child_process');

const REPO = path.resolve(__dirname, '..');
const PANEL = path.join(REPO, 'app', 'panel', 'panel.js');
const ENGINE = path.join(REPO, 'app', 'panel', 'caption-formulation.js');
const HISTORY_SOURCE = path.join(REPO, 'app', 'panel', 'history-source.js');

const NEG_ARM = process.argv.indexOf('--neg-arm') >= 0;
function say(line) { process.stdout.write(line + '\n'); }
function sha256(text) { return crypto.createHash('sha256').update(text, 'utf8').digest('hex'); }
function revision(file) {
  const buf = fs.readFileSync(file);
  const st = fs.statSync(file);
  return { bytes: buf.length, sha256: crypto.createHash('sha256').update(buf).digest('hex'), mtime: st.mtime.toISOString(), text: buf.toString('utf8') };
}

// ---------------------------------------------------------------------------
// THE FAKE DOM — only what the caption path touches.
// ---------------------------------------------------------------------------
let DOC = null;

function compoundMatches(el, comp) {
  if (!comp) return false;
  const m = comp.match(/^([a-zA-Z][\w-]*)?((?:[.#][\w-]+|\[[^\]]*\])*)$/);
  if (!m) return false;
  if (m[1] && el.tagName !== m[1].toUpperCase()) return false;
  const parts = (m[2] || '').match(/[.#][\w-]+|\[[^\]]*\]/g) || [];
  for (const p of parts) {
    if (p[0] === '.') { if (!el.classList.contains(p.slice(1))) return false; }
    else if (p[0] === '#') { if (el.id !== p.slice(1)) return false; }
    else {
      const inner = p.slice(1, -1);
      const eq = inner.indexOf('=');
      const name = eq === -1 ? inner : inner.slice(0, eq);
      const val = eq === -1 ? null : inner.slice(eq + 1).replace(/^["']|["']$/g, '');
      const have = el._attrs[name];
      if (have === undefined) return false;
      if (val !== null && String(have) !== val) return false;
    }
  }
  return true;
}
function selMatches(el, sel) {
  const parts = sel.trim().split(/\s+/);
  let i = parts.length - 1;
  if (!compoundMatches(el, parts[i])) return false;
  i -= 1;
  let node = el.parentNode;
  while (i >= 0 && node) {
    if (node.nodeType === 1 && compoundMatches(node, parts[i])) i -= 1;
    node = node.parentNode;
  }
  return i < 0;
}
class FNode { constructor() { this.childNodes = []; this.parentNode = null; } }
class FText extends FNode {
  constructor(data) { super(); this.nodeType = 3; this.data = String(data); }
  get textContent() { return this.data; }
  set textContent(v) { this.data = String(v); }
}
class FElement extends FNode {
  constructor(tag) {
    super();
    this.nodeType = 1;
    this.tagName = String(tag).toUpperCase();
    this._className = '';
    this._attrs = {};
    // `dataset` MIRRORS into `_attrs` the way a browser does, because one of the
    // claims under test is the ABSENCE of a data-source attribute (no source) and
    // its presence (two sources). A plain object would leave every attribute
    // selector blind to what the panel wrote.
    this.dataset = new Proxy({}, {
      set: (target, key, value) => {
        target[key] = String(value);
        this._attrs['data-' + String(key).replace(/[A-Z]/g, (c) => '-' + c.toLowerCase())] = String(value);
        return true;
      },
      deleteProperty: (target, key) => {
        delete target[key];
        delete this._attrs['data-' + String(key).replace(/[A-Z]/g, (c) => '-' + c.toLowerCase())];
        return true;
      },
    });
    this.style = { setProperty() {}, removeProperty() {} };
    this.id = ''; this.hidden = false; this.title = ''; this.value = '';
    this.disabled = false; this.checked = false;
    this.scrollTop = 0; this.scrollHeight = 0; this.clientHeight = 0; this.clientWidth = 0;
    this.offsetParent = null;
    this._listeners = {};
    const self = this;
    this.classList = {
      contains: (c) => self._className.split(/\s+/).filter(Boolean).includes(c),
      add: (...cs) => { const s = new Set(self._className.split(/\s+/).filter(Boolean)); cs.forEach(c => s.add(c)); self._className = [...s].join(' '); },
      remove: (...cs) => { const s = new Set(self._className.split(/\s+/).filter(Boolean)); cs.forEach(c => s.delete(c)); self._className = [...s].join(' '); },
      toggle: (c, force) => { const on = force === undefined ? !self.classList.contains(c) : !!force; if (on) self.classList.add(c); else self.classList.remove(c); return on; },
    };
  }
  get className() { return this._className; }
  set className(v) { this._className = String(v); }
  get children() { return this.childNodes.filter(n => n.nodeType === 1); }
  get firstElementChild() { return this.children[0] || null; }
  get lastElementChild() { const c = this.children; return c[c.length - 1] || null; }
  get childElementCount() { return this.children.length; }
  get firstChild() { return this.childNodes[0] || null; }
  get nextSibling() { if (!this.parentNode) return null; const i = this.parentNode.childNodes.indexOf(this); return this.parentNode.childNodes[i + 1] || null; }
  // CONNECTED means "walks up to A document root", NOT "belongs to the last
  // document this file built": two panels live at once here (CHK-C2 and CHK-F
  // each build their own), and a global root made the first panel's rows look
  // detached the moment the second one existed.
  get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n.nodeType === 9; }
  get textContent() { return this.childNodes.map(n => n.textContent).join(''); }
  set textContent(v) { this.childNodes.forEach(n => { n.parentNode = null; }); this.childNodes = []; this.append(new FText(v)); }
  append(...nodes) { for (const n of nodes) { const node = (n instanceof FNode) ? n : new FText(n); node.parentNode = this; this.childNodes.push(node); } }
  prepend(...nodes) { for (const n of nodes.slice().reverse()) { const node = (n instanceof FNode) ? n : new FText(n); node.parentNode = this; this.childNodes.unshift(node); } }
  replaceChildren(...nodes) { this.childNodes.forEach(n => { n.parentNode = null; }); this.childNodes = []; this.append(...nodes); }
  removeChild(node) { const i = this.childNodes.indexOf(node); if (i === -1) throw new Error('removeChild: not a child'); this.childNodes.splice(i, 1); node.parentNode = null; return node; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  setAttribute(name, value) { this._attrs[name] = String(value); if (name === 'id') this.id = String(value); if (name === 'class') this.className = String(value); }
  getAttribute(name) { return this._attrs[name] === undefined ? null : this._attrs[name]; }
  removeAttribute(name) { delete this._attrs[name]; }
  addEventListener(type, cb) { (this._listeners[type] = this._listeners[type] || []).push(cb); }
  removeEventListener() {}
  dispatch(type, ev) { (this._listeners[type] || []).forEach(cb => cb(ev)); }
  closest(sel) { let n = this; while (n && n.nodeType === 1) { if (compoundMatches(n, sel)) return n; n = n.parentNode; } return null; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  querySelectorAll(sel) {
    const found = [];
    const walk = (n) => { for (const c of n.childNodes) { if (c.nodeType === 1) { if (selMatches(c, sel)) found.push(c); walk(c); } } };
    walk(this);
    return found;
  }
}

const PRESET_IDS = ['caption-list', 'captions-body', 'placeholder', 'status', 'status-text', 'status-dot', 'captions-hint', 'stats-chip'];

// ---------------------------------------------------------------------------
// THE HARNESS — real panel.js, real engine, fake document.
// ---------------------------------------------------------------------------
function buildPanel(panelSource, engineSource) {
  const doc = new FElement('#document');
  doc.nodeType = 9;
  doc._byId = new Map();
  doc.activeElement = null;
  doc.addEventListener = () => {};
  doc.removeEventListener = () => {};
  doc.createElement = (tag) => new FElement(tag);
  doc.createElementNS = (_ns, tag) => new FElement(tag);
  doc.createTextNode = (t) => new FText(t);
  doc.createDocumentFragment = () => new FElement('#fragment');
  DOC = doc;

  const body = new FElement('body');
  const html = new FElement('html');
  doc.append(html);
  html.append(body);
  doc.body = body;
  doc.documentElement = html;
  for (const id of PRESET_IDS) {
    const el = new FElement('div');
    el.id = id;
    doc._byId.set(id, el);
    body.append(el);
  }
  doc.getElementById = function (id) {
    if (this._byId.has(id)) return this._byId.get(id);
    const el = new FElement('div');
    el.id = id;
    this._byId.set(id, el);
    body.append(el);
    return el;
  };

  const sandbox = {
    console,
    document: doc,
    navigator: { userAgent: 'node' },
    location: { href: 'file:///panel.html' },
    setTimeout: () => 0,
    clearTimeout: () => {},
    setInterval: () => 0,
    clearInterval: () => {},
    requestAnimationFrame: (cb) => { cb(0); return 0; },
    cancelAnimationFrame: () => {},
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    performance: { now: () => Date.now() },
    addEventListener: () => {},
    removeEventListener: () => {},
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  const ctx = vm.createContext(sandbox);

  const handlers = { caption: null, status: null };
  // The bridge the shell injects. onStats/getStats are ABSENT on purpose:
  // wireLevel() has its own documented early return for that case.
  sandbox.sotto = {
    onCaption: (cb) => { handlers.caption = cb; },
    onStatus: (cb) => { handlers.status = cb; },
    onGeometry: () => {},
    captionApplied: () => {},
    statusApplied: () => {},
    clearApplied: () => {},
    ready: () => {},
    hide: () => {},
    quit: () => {},
    revive: () => {},
    pause: () => {},
    setTransparency: () => {},
    setPanelSurface: () => {},
    setLiveEnabled: () => {},
    setPointerInteractive: () => {},
    history: {
      root: () => Promise.resolve({ root: '' }),
      tail: () => Promise.resolve({ entries: [] }),
      append: () => Promise.resolve({ entry: null }),
    },
  };

  vm.runInContext(engineSource, ctx, { filename: 'caption-formulation.js' });
  vm.runInContext(revision(HISTORY_SOURCE).text, ctx, { filename: 'history-source.js' });
  vm.runInContext(panelSource, ctx, { filename: 'panel.js' });

  const list = doc._byId.get('caption-list');
  const textOf = (li) => { const b = li.querySelector('.caption__text'); return (b || li).textContent; };
  const rowOf = (li) => ({
    el: li,
    provisional: li.classList.contains('caption--provisional'),
    latest: li.classList.contains('caption--latest'),
    start: li.dataset.start === undefined ? null : li.dataset.start,
    source: li.dataset.source === undefined ? null : li.dataset.source,
    revision: li.dataset.revision === undefined ? null : li.dataset.revision,
    datasetKeys: Object.keys(li.dataset).sort(),
    text: textOf(li),
  });
  const rows = () => list.children.map(rowOf);
  const feed = (text, meta) => handlers.caption({ text, meta });
  // A status change is the panel's OWN flush trigger (wireStatus ->
  // engine.flush('status-change') for every engine). It needs a non-empty
  // 'text' or the handler returns before flushing — that is the panel's own
  // contract, not a shortcut of this oracle.
  const flush = () => handlers.status({ text: 'done', kind: 'done' });
  return { doc, list, rows, feed, flush, handlers };
}

// ---------------------------------------------------------------------------
// THE CHECKS — the contract, driven only through bridge.onCaption/onStatus.
// ---------------------------------------------------------------------------
function txt(r) { return JSON.stringify(r.text); }
// Case-insensitive on purpose: the engine's formulate() capitalises a line
// ("alpha one" -> "Alpha one."), so a case-sensitive match would be a bug in
// THIS instrument, not a finding about the panel.
function has(hay, needle) { return String(hay).toLowerCase().indexOf(String(needle).toLowerCase()) >= 0; }
function where(rs) { return rs.map((r) => (r.source === null ? 'no-source' : r.source) + '@' + r.start).join(', '); }

function checkA(h) {
  h.feed('alpha one', { start: 10, end: 11, final: false, source: 'proc:111' });
  h.feed('beta one', { start: 10, end: 11, final: false, source: 'proc:222' });
  h.flush();
  const rows = h.rows().filter((r) => !r.provisional);
  const a = rows.filter((r) => r.source === 'proc:111');
  const b = rows.filter((r) => r.source === 'proc:222');
  const ok = rows.length === 2 && a.length === 1 && b.length === 1
    && a[0].start === '10' && b[0].start === '10'
    && has(a[0].text, 'alpha') && has(b[0].text, 'beta')
    && a[0].el !== b[0].el;
  return { ok, detail: 'committed rows=' + rows.length + ' [' + where(rows) + '] texts=' + txt(a[0] || { text: '' }) + '/' + txt(b[0] || { text: '' }) };
}

function checkB(h) {
  h.feed('gamma one', { start: 20, end: 21, final: true, source: 'proc:111' });
  h.flush();
  // Scoped by START, not by source: the replace contract ("the same line again
  // rewrites the row it already has") is the PRE-STEP-4 contract too, so this
  // check must stay GREEN in the neg-arm. The source-specificity is CHK-A/CHK-D.
  const first = h.rows().filter((r) => !r.provisional && r.start === '20');
  const before = first.length === 1 ? first[0] : null;
  h.feed('gamma one corrected', { start: 20, end: 22, final: true, source: 'proc:111' });
  h.flush();
  const after = h.rows().filter((r) => !r.provisional && r.start === '20');
  const ok = !!before && after.length === 1 && after[0].el === before.el
    && after[0].source === before.source
    && after[0].text !== before.text && has(after[0].text, 'corrected')
    && after[0].revision === 'true';
  return { ok, detail: 'source=' + JSON.stringify(after[0] ? after[0].source : null) + ' rows@20=' + after.length + ' same-node=' + (!!before && after[0] && after[0].el === before.el) + ' text ' + txt(before || { text: '' }) + ' -> ' + txt(after[0] || { text: '' }) + ' revision=' + (after[0] ? after[0].revision : 'n/a') };
}

function checkC(h) {
  h.feed('delta one', { start: 30, end: 31, final: true });
  h.flush();
  const before = h.rows().filter((r) => !r.provisional && r.start === '30');
  h.feed('delta one corrected', { start: 30, end: 32, final: true });
  h.flush();
  const after = h.rows().filter((r) => !r.provisional && r.start === '30');
  const ok = before.length === 1 && after.length === 1 && after[0].source === null
    && after[0].el === before[0].el && after[0].text !== before[0].text
    && has(after[0].text, 'corrected');
  return { ok, detail: 'rows@30=' + after.length + ' data-source=' + JSON.stringify(after[0] ? after[0].source : null) + ' same-node=' + (before[0] && after[0] ? after[0].el === before[0].el : false) + ' text ' + txt(before[0] || { text: '' }) + ' -> ' + txt(after[0] || { text: '' }) };
}

function checkD(h) {
  h.feed('epsilon alpha', { start: 40, end: 41, final: false, source: 'proc:111' });
  const step1 = h.rows().filter((r) => r.provisional);
  const rowA = step1.filter((r) => r.source === 'proc:111');
  h.feed('epsilon beta', { start: 40, end: 41, final: false, source: 'proc:222' });
  const step2 = h.rows().filter((r) => r.provisional);
  const a2 = step2.filter((r) => r.source === 'proc:111');
  const b2 = step2.filter((r) => r.source === 'proc:222');
  const aTextAfterB = a2.length === 1 ? a2[0].text : '';
  h.feed('epsilon alpha extended', { start: 40, end: 42, final: false, source: 'proc:111' });
  const step3 = h.rows().filter((r) => r.provisional);
  const a3 = step3.filter((r) => r.source === 'proc:111');
  const b3 = step3.filter((r) => r.source === 'proc:222');
  const ok = rowA.length === 1 && step2.length === 2 && a2.length === 1 && b2.length === 1
    && a2[0].el === rowA[0].el && b2[0].el !== rowA[0].el
    && !has(aTextAfterB, 'beta') && has(b2[0].text, 'beta')
    && step3.length === 2 && a3.length === 1 && b3.length === 1
    && a3[0].el === rowA[0].el && b3[0].el === b2[0].el
    && a3[0].text !== aTextAfterB && b3[0].text === b2[0].text;
  return { ok, detail: 'provisional rows after A=' + step1.length + ' after A+B=' + step2.length + ' after A-repaint=' + step3.length
    + ' | A kept ' + txt({ text: aTextAfterB }) + ' while B=' + txt(b2[0] || { text: '' })
    + ' | A repaint -> ' + txt(a3[0] || { text: '' }) + ', B untouched=' + (a3[0] && b3[0] ? b3[0].text === b2[0].text : false) };
}

// CHK-C2 needs a panel of its OWN: in the shared harness CHK-A/CHK-B have already
// put data-source attributes on the list, so "no attribute anywhere" can only be
// measured where no sourced line ever arrived.
function checkC2(h, makePanel) {
  const fresh = makePanel();
  fresh.feed('delta solo', { start: 30, end: 31, final: true });
  fresh.flush();
  fresh.feed('delta solo corrected', { start: 30, end: 32, final: true });
  fresh.flush();
  const rows = fresh.rows().filter((r) => !r.provisional);
  const withAttr = fresh.doc.querySelectorAll('[data-source]').length;
  const ok = rows.length === 1 && rows[0].source === null
    && rows[0].datasetKeys.indexOf('source') === -1
    && withAttr === 0 && has(rows[0].text, 'corrected');
  return { ok, detail: 'rows=' + rows.length + ' rows-with-data-source=' + withAttr
    + ' dataset keys of the row=' + JSON.stringify(rows[0] ? rows[0].datasetKeys : null)
    + ' text=' + txt(rows[0] || { text: '' }) };
}

// CHK-E — the commit meta, from the ENGINE the panel itself loads, with no DOM.
// This is the half of the contract the panel arms cannot see: a row is keyed by
// (source, start), but the SOURCE travels on the commit meta, and the no-source
// literal has to stay byte-identical or every no-source run changes shape.
function loadEngine(engineSource) {
  const box = { module: { exports: {} }, console, setTimeout, clearTimeout, setInterval, clearInterval, performance: { now: () => Date.now() } };
  vm.runInContext(engineSource, vm.createContext(box), { filename: 'caption-formulation.js' });
  return box.module.exports;
}

function checkE(h, makePanel, panelSource, engineSource) {
  const F = loadEngine(engineSource);
  const run = (options, text, meta) => {
    const seen = [];
    const engine = F.createEngine(Object.assign({
      onCommit: (line, reason, m) => seen.push({ keys: Object.keys(m), meta: m }),
      onProvisional: () => {},
    }, options));
    engine.ingest(text, meta);
    engine.flush('status-change');
    return seen;
  };
  const FIN = (start, extra) => Object.assign({ start, end: start + 1, final: true }, extra || {});
  const keyOf = (r) => (r[0] ? r[0].keys.join(',') : 'NO-COMMIT');

  const plain = run({}, 'linha sem fonte', FIN(5));
  const sourced = run({ source: 'proc:111' }, 'linha com fonte', FIN(5));
  const producer = run({}, 'linha redux', FIN(7, { producer: 'redux' }));
  const both = run({ source: 'file:clip.wav' }, 'linha redux', FIN(7, { producer: 'redux' }));
  const empties = ['', null, 42, {}, []].map((s) => run({ source: s }, 'linha sem fonte util', FIN(9)));
  const two = [];
  const e1 = F.createEngine({ source: 'proc:111', onCommit: (l, r, m) => two.push(m.source), onProvisional: () => {} });
  const e2 = F.createEngine({ source: 'proc:222', onCommit: (l, r, m) => two.push(m.source), onProvisional: () => {} });
  e1.ingest('linha um', FIN(1)); e1.flush('status-change');
  e2.ingest('linha dois', FIN(1)); e2.flush('status-change');

  const ok = plain.length === 1
    && keyOf(plain) === 'route,start,routeSource'
    && JSON.stringify(plain[0].meta) === '{"route":"final","start":5,"routeSource":"worker-stamped"}'
    && keyOf(sourced) === 'route,start,routeSource,source' && sourced[0].meta.source === 'proc:111'
    && keyOf(producer) === 'route,start,routeSource,producer'
    && keyOf(both) === 'route,start,routeSource,producer,source' && both[0].meta.source === 'file:clip.wav'
    && empties.every((r) => keyOf(r) === 'route,start,routeSource')
    && JSON.stringify(two) === '["proc:111","proc:222"]';
  return { ok, detail: 'no-source keys=' + keyOf(plain) + ' obj=' + JSON.stringify(plain[0] ? plain[0].meta : null)
    + ' | +source keys=' + keyOf(sourced) + ' | +producer keys=' + keyOf(producer)
    + ' | +both keys=' + keyOf(both)
    + ' | empty/null/number/object/array source keys=' + empties.map(keyOf).join(' / ')
    + ' | two engines stamped ' + JSON.stringify(two) };
}

// CHK-F — the trim path. MAX_CAPTIONS rows is a cap, not an index reset: the
// oldest row leaves the DOM and its identity must leave the panel's index with
// it, or a later line rewrites a row that is no longer the one it names.
function checkF(h, makePanel, panelSource) {
  const m = panelSource.match(/const MAX_CAPTIONS = (\d+);/);
  const max = m ? Number(m[1]) : null;
  const fresh = makePanel();
  const A = 'proc:111';
  const B = 'proc:222';
  for (let i = 0; i < 100; i++) { fresh.feed('linhaA ' + i, { start: i, end: i + 0.5, final: true, source: A }); fresh.flush(); }
  for (let i = 0; i < 100; i++) { fresh.feed('linhaB ' + i, { start: i, end: i + 0.5, final: true, source: B }); fresh.flush(); }
  const before = fresh.rows().filter((r) => !r.provisional);
  fresh.feed('linhaB cem', { start: 100, end: 100.5, final: true, source: B });
  fresh.flush();
  const trimmed = fresh.rows().filter((r) => !r.provisional);
  const b0 = trimmed.filter((r) => r.source === B && r.start === '0');
  const b0el = b0.length === 1 ? b0[0].el : null;
  fresh.feed('linhaB reescrita', { start: 0, end: 0.5, final: true, source: B });
  fresh.flush();
  const rewritten = fresh.rows().filter((r) => !r.provisional);
  const survivor = rewritten.filter((r) => r.source === B && r.start === '0')[0];
  fresh.feed('nunca vista', { start: 500, end: 500.5, final: true, source: B });
  fresh.flush();
  const appended = fresh.rows().filter((r) => !r.provisional);
  const a0Left = trimmed.filter((r) => r.source === A && r.start === '0').length;
  const ok = max !== null && before.length === max && trimmed.length === max && a0Left === 0
    && b0.length === 1
    && rewritten.length === max && !!survivor && survivor.el === b0el && has(survivor.text, 'reescrita')
    && appended.length === max
    && has(appended[appended.length - 1].text, 'nunca')
    && appended.filter((r) => has(r.text, 'reescrita')).length === 1;
  return { ok, detail: 'MAX=' + max + ' rows after 200=' + before.length + ' after the 201st=' + trimmed.length
    + ' (A,0) still there=' + a0Left + ' | (B,0) rewritten IN PLACE=' + (!!survivor && survivor.el === b0el)
    + ' rows=' + rewritten.length + ' text=' + txt(survivor || { text: '' })
    + ' | append rows=' + appended.length + ' last=' + txt(appended[appended.length - 1] || { text: '' }) };
}

const CHECKS = [
  ['CHK-A', 'same start + DIFFERENT sources -> TWO rows with their own text', checkA],
  ['CHK-B', 'the same line again -> ONE row, text replaced IN PLACE', checkB],
  ['CHK-C', 'no source, same start twice -> still ONE row (pre-existing contract)', checkC],
  ['CHK-C2', 'no source at all -> NO data-source attribute anywhere in the box', checkC2],
  ['CHK-D', 'a partial for source A never rewrites the live row of source B', checkD],
  ['CHK-E', 'commit meta: no-source literal byte-identical, source added LAST', checkE],
  ['CHK-F', 'the trim path keeps the index on the rows that are still there', checkF],
];

function runArm(label, panelSource, engineSource) {
  say('');
  say('--- ' + label + ' ---');
  const makePanel = () => buildPanel(panelSource, engineSource);
  let h;
  try {
    h = makePanel();
  } catch (e) {
    say('  LOAD FAILED: ' + (e && e.name) + ': ' + (e && e.message));
    say('  ' + String((e && e.stack) || '').split('\n').slice(0, 4).join('\n  '));
    return { loaded: false, colours: {} };
  }
  const colours = {};
  for (const [id, title, fn] of CHECKS) {
    let res;
    try { res = fn(h, makePanel, panelSource, engineSource); } catch (e) { res = { ok: false, detail: 'THREW ' + (e && e.name) + ': ' + (e && e.message) }; }
    colours[id] = res.ok;
    say('  ' + (res.ok ? 'GREEN' : 'RED  ') + ' ' + id + '  ' + title);
    say('        ' + res.detail);
  }
  return { loaded: true, colours };
}

// ---------------------------------------------------------------------------
// THE NEG-ARM — the same bytes with ONLY the per-source keying removed.
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// THE NEG-ARM — each mutant removes ONE thing, in memory, from the real bytes.
// ---------------------------------------------------------------------------
const MUTANTS = [
  {
    id: 'M1 one engine for every app',
    what: 'engineFor(source) -> key = null (the pre-STEP-4 shape)',
    file: 'panel',
    apply(source) {
      const re = /function engineFor\(source\) \{\r?\n([ \t]*)const key = [^\n]*\n/;
      if (!re.test(source)) return null;
      return source.replace(re, (whole, indent) => 'function engineFor(source) {\n' + indent + 'const key = null; /* NEG-ARM M1 */\n');
    },
    mustRed: ['CHK-A', 'CHK-D'],
    mustGreen: ['CHK-B', 'CHK-C', 'CHK-C2', 'CHK-E'],
  },
  {
    id: 'M2 the row key ignores the source',
    what: 'rowIdentity(source, start) -> source = null',
    file: 'panel',
    apply(source) {
      const re = /function rowIdentity\(source, start\) \{\r?\n/;
      if (!re.test(source)) return null;
      return source.replace(re, (whole) => whole + '  source = null; /* NEG-ARM M2 */\n');
    },
    mustRed: ['CHK-A'],
    mustGreen: ['CHK-B', 'CHK-C', 'CHK-C2', 'CHK-D', 'CHK-E'],
  },
  {
    id: 'M3 the source key moves out of LAST place',
    what: 'commit meta -> { route, start, source, routeSource }',
    file: 'engine',
    apply(source) {
      const anchor = '{ route, start, routeSource, source: engineSource }';
      if (source.indexOf(anchor) === -1) return null;
      return source.replace(anchor, '{ route, start, source: engineSource, routeSource }');
    },
    mustRed: ['CHK-E'],
    mustGreen: ['CHK-A', 'CHK-B', 'CHK-C', 'CHK-C2', 'CHK-D'],
  },
  {
    id: 'M4 the no-source literal gains a source key',
    what: 'no-source commit meta -> { route, start, routeSource, source: null }',
    file: 'engine',
    apply(source) {
      const re = /\? \(tag === null\r?\n\s*\? \{ route, start, routeSource \}/;
      if (!re.test(source)) return null;
      return source.replace(re, (whole) => whole.replace('{ route, start, routeSource }', '{ route, start, routeSource, source: null }'));
    },
    mustRed: ['CHK-E'],
    mustGreen: ['CHK-A', 'CHK-B', 'CHK-C', 'CHK-C2', 'CHK-D'],
  },
];

// MAIN
// ---------------------------------------------------------------------------
say('panel-row-identity-oracle — real panel.js bytes in a node vm, fake DOM');
const panelRev = revision(PANEL);
const engineRev = revision(ENGINE);
say('  panel.js   ' + panelRev.bytes + ' B  sha256 ' + panelRev.sha256);
say('  panel.js   mtime ' + panelRev.mtime);
say('  engine     ' + engineRev.bytes + ' B  sha256 ' + engineRev.sha256);

const parsed = cp.spawnSync(process.execPath, ['--check', PANEL], { encoding: 'utf8' });
const checkRc = parsed.status;
say('  node --check app/panel/panel.js -> rc=' + checkRc + (parsed.stderr ? ' stderr=' + JSON.stringify(parsed.stderr.trim()) : ''));
if (checkRc !== 0) {
  say('VERDICT: FAIL (panel.js does not parse)');
  process.exit(1);
}

const shipped = runArm('AS SHIPPED', panelRev.text, engineRev.text);
const allGreen = shipped.loaded && CHECKS.every(([id]) => shipped.colours[id]);
say('');
say('AS-SHIPPED COLOURS: ' + CHECKS.map(([id]) => id + '=' + (shipped.colours[id] ? 'GREEN' : 'RED')).join(' '));

if (!NEG_ARM) {
  say('VERDICT: ' + (allGreen ? 'PASS' : 'FAIL'));
  process.exit(allGreen ? 0 : 1);
}

let selective = true;
for (const mutant of MUTANTS) {
  const target = mutant.file === 'engine' ? engineRev.text : panelRev.text;
  const mutated = mutant.apply(target);
  say('');
  say('--- NEG-ARM ' + mutant.id + ': ' + mutant.what + ' ---');
  if (mutated === null) {
    say('  SETUP ERROR: the anchor for this mutant was not found in this revision.');
    say('  A mutant that cannot be built has no colour, so this is an OPEN GAP, not a pass.');
    selective = false;
    continue;
  }
  say('  mutant bytes ' + Buffer.byteLength(mutated, 'utf8') + ' B  sha256 ' + sha256(mutated));
  const arm = mutant.file === 'engine'
    ? runArm('NEG-ARM ' + mutant.id, panelRev.text, mutated)
    : runArm('NEG-ARM ' + mutant.id, mutated, engineRev.text);
  say('  ' + mutant.id + ' COLOURS: ' + CHECKS.map(([id]) => id + '=' + (arm.colours[id] ? 'GREEN' : 'RED')).join(' '));
  const redMissed = mutant.mustRed.filter((id) => arm.colours[id]);
  const greenBroke = mutant.mustGreen.filter((id) => !arm.colours[id]);
  const ok = arm.loaded && redMissed.length === 0 && greenBroke.length === 0;
  say('  must be RED    ' + mutant.mustRed.join(',') + ' -> ' + (redMissed.length ? 'MISSED ' + redMissed.join(',') : 'all RED'));
  say('  must stay GREEN ' + mutant.mustGreen.join(',') + ' -> ' + (greenBroke.length ? 'BROKE ' + greenBroke.join(',') : 'all GREEN'));
  say('  ' + mutant.id + ' selective: ' + ok);
  if (!ok) selective = false;
}
say('');
say('VERDICT: ' + (allGreen && selective ? 'PASS' : 'FAIL'));
process.exit(allGreen && selective ? 0 : 1);
