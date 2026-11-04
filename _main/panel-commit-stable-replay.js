#!/usr/bin/env node
/**
 * panel-commit-stable-replay.js — THE TWO LEGS OF A CAPTION LINE, ON REAL BYTES.
 *
 * WHAT IT IS. A replay harness (node builtins only: no npm, no jsdom, no Electron,
 * no window, no audio device) that loads the REAL `app/panel/panel.js`, the REAL
 * `app/panel/caption-formulation.js`, the REAL `app/panel/stable-words.js` and the
 * REAL `app/panel/history-source.js` into one vm context with a hand-rolled DOM and
 * a VIRTUAL CLOCK, then feeds them a recorded fragment sequence and records:
 *
 *   CAPTION_PROVISIONAL_PAINT  — the instant the live text exists on screen
 *                                (the panel's own counter, `noteProvisionalPaint`)
 *   commit                     — the instant `addCaption` acknowledges the line,
 *                                i.e. exactly what the shell logs as CAPTION_APPLIED
 *
 * WHEN IT PAINTS, IT SAYS SO: the paint row is emitted by the panel itself, not by
 * this harness, so the instrument is the same code the owner's panel runs.
 *
 * THE VIRTUAL CLOCK IS THE MEASUREMENT. `Date.now` and `setTimeout` inside the
 * context are the harness's, and a fragment is fed at the wall-clock instant the
 * log recorded for it. So a line committed by the renderer's 1500 ms deadline
 * measures 1500 ms here for the same reason it measured 1509 ms on the owner's
 * machine — the number comes from the panel's timer, not from a constant this file
 * echoes.
 *
 * --arm before reverts ONE line of `caption-formulation.js` in memory (the
 * `stable` commit) and writes the reverted source next to this file, so the
 * before/after pair is the same tree, the same corpus and one line apart. If the
 * line to revert is not found the harness exits 2: a mutant that does not move the
 * bytes is not a control.
 *
 * Usage:
 *   node _main/panel-commit-stable-replay.js --corpus <file.json> [--arm after|before]
 *   node _main/panel-commit-stable-replay.js --fallback-corpus [--arm after]
 * Prints ONE JSON object on stdout. Exit 0 = measured, 2 = setup error.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');

const REPO = path.resolve(__dirname, '..');
const FILES = {
  panel: path.join(REPO, 'app', 'panel', 'panel.js'),
  engine: path.join(REPO, 'app', 'panel', 'caption-formulation.js'),
  stable: path.join(REPO, 'app', 'panel', 'stable-words.js'),
  history: path.join(REPO, 'app', 'panel', 'history-source.js'),
};

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  if (i === -1) return fallback;
  return process.argv[i + 1] === undefined ? true : process.argv[i + 1];
}
function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}
function read(file) {
  return fs.readFileSync(file, 'utf8');
}
function die(message) {
  process.stderr.write('SETUP ERROR: ' + message + '\n');
  process.exit(2);
}

/* ── THE VIRTUAL CLOCK ──────────────────────────────────────────────────────
 * `setTimeout` is the panel's own deadline (`armHoldTimer`), and it is the thing
 * under measurement, so it must be the panel's timer and not a stub. Timers fire
 * in (at, insertion) order, the way a browser's do.
 */
function makeClock(startMs) {
  let seq = 0;
  const timers = [];
  const clock = {
    now: startMs,
    setTimeout(fn, ms) {
      seq += 1;
      const timer = { id: seq, at: clock.now + Math.max(0, Number(ms) || 0), fn, dead: false };
      timers.push(timer);
      return timer.id;
    },
    clearTimeout(id) {
      for (const t of timers) if (t.id === id) t.dead = true;
    },
    /** Run every timer due at or before `t`, then stand at `t`. */
    advanceTo(t) {
      for (;;) {
        let pick = null;
        for (const timer of timers) {
          if (timer.dead) continue;
          if (timer.at > t) continue;
          if (pick === null || timer.at < pick.at || (timer.at === pick.at && timer.id < pick.id)) pick = timer;
        }
        if (pick === null) break;
        pick.dead = true;
        clock.now = pick.at;
        pick.fn();
      }
      if (t > clock.now) clock.now = t;
    },
  };
  return clock;
}

/* ── THE FAKE DOM — only what the caption path touches ─────────────────────
 * Copied in shape from `_main/panel-row-identity-oracle.js`: the panel builds
 * `<li>` rows and finds them by class, so the class/attribute matching has to be
 * real. Nothing here paints anything; every claim below is about the DOM the panel
 * builds in this process.
 */
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
  constructor(tag, onCreate) {
    super();
    this.nodeType = 1;
    this.tagName = String(tag).toUpperCase();
    if (onCreate) onCreate(String(tag).toUpperCase());
    this._className = '';
    this._attrs = {};
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
      add: (...cs) => { const s = new Set(self._className.split(/\s+/).filter(Boolean)); cs.forEach((c) => s.add(c)); self._className = [...s].join(' '); },
      remove: (...cs) => { const s = new Set(self._className.split(/\s+/).filter(Boolean)); cs.forEach((c) => s.delete(c)); self._className = [...s].join(' '); },
      toggle: (c, force) => { const on = force === undefined ? !self.classList.contains(c) : !!force; if (on) self.classList.add(c); else self.classList.remove(c); return on; },
    };
  }
  get className() { return this._className; }
  set className(v) { this._className = String(v); }
  get children() { return this.childNodes.filter((n) => n.nodeType === 1); }
  get firstElementChild() { return this.children[0] || null; }
  get lastElementChild() { const c = this.children; return c[c.length - 1] || null; }
  get childElementCount() { return this.children.length; }
  get firstChild() { return this.childNodes[0] || null; }
  get nextSibling() { if (!this.parentNode) return null; const i = this.parentNode.childNodes.indexOf(this); return this.parentNode.childNodes[i + 1] || null; }
  get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n.nodeType === 9; }
  get textContent() { return this.childNodes.map((n) => n.textContent).join(''); }
  set textContent(v) { this.childNodes.forEach((n) => { n.parentNode = null; }); this.childNodes = []; this.append(new FText(v)); }
  append(...nodes) { for (const n of nodes) { const node = (n instanceof FNode) ? n : new FText(n); node.parentNode = this; this.childNodes.push(node); } }
  appendChild(node) { this.append(node); return node; }
  insertBefore(node, ref) {
    const n = (node instanceof FNode) ? node : new FText(node);
    const i = this.childNodes.indexOf(ref);
    n.parentNode = this;
    if (i < 0) this.childNodes.push(n); else this.childNodes.splice(i, 0, n);
    return n;
  }
  prepend(...nodes) { for (const n of nodes.slice().reverse()) { const node = (n instanceof FNode) ? n : new FText(n); node.parentNode = this; this.childNodes.unshift(node); } }
  replaceChildren(...nodes) { this.childNodes.forEach((n) => { n.parentNode = null; }); this.childNodes = []; this.append(...nodes); }
  removeChild(node) { const i = this.childNodes.indexOf(node); if (i === -1) throw new Error('removeChild: not a child'); this.childNodes.splice(i, 1); node.parentNode = null; return node; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  setAttribute(name, value) { this._attrs[name] = String(value); if (name === 'id') this.id = String(value); if (name === 'class') this.className = String(value); }
  getAttribute(name) { return this._attrs[name] === undefined ? null : this._attrs[name]; }
  removeAttribute(name) { delete this._attrs[name]; }
  hasAttribute(name) { return this._attrs[name] !== undefined; }
  addEventListener(type, cb) { (this._listeners[type] = this._listeners[type] || []).push(cb); }
  removeEventListener() {}
  dispatch(type, ev) { (this._listeners[type] || []).forEach((cb) => cb(ev)); }
  closest(sel) { let n = this; while (n && n.nodeType === 1) { if (compoundMatches(n, sel)) return n; n = n.parentNode; } return null; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  querySelectorAll(sel) {
    const found = [];
    const walk = (n) => { for (const c of n.childNodes) { if (c.nodeType === 1) { if (selMatches(c, sel)) found.push(c); walk(c); } } };
    walk(this);
    return found;
  }
}

const PRESET_IDS = ['caption-list', 'captions-body', 'placeholder', 'status', 'status-text',
  'status-dot', 'captions-hint', 'stats-chip'];

/* ── THE HARNESS ─────────────────────────────────────────────────────────── */
function buildPanel(sources, clock) {
  const created = { li: 0, all: 0 };
  const doc = new FElement('#document', () => {});
  doc.nodeType = 9;
  doc._byId = new Map();
  doc.activeElement = null;
  doc.addEventListener = () => {};
  doc.removeEventListener = () => {};
  doc.createElement = (tag) => {
    created.all += 1;
    if (String(tag).toUpperCase() === 'LI') created.li += 1;
    return new FElement(tag);
  };
  doc.createElementNS = (_ns, tag) => doc.createElement(tag);
  doc.createTextNode = (t) => new FText(t);
  doc.createDocumentFragment = () => new FElement('#fragment');

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

  const VDate = class extends Date {
    constructor(...a) { if (a.length === 0) super(clock.now); else super(...a); }
    static now() { return clock.now; }
  };

  const sandbox = {
    console,
    document: doc,
    navigator: { userAgent: 'node' },
    location: { href: 'file:///panel.html' },
    Date: VDate,
    setTimeout: (fn, ms) => clock.setTimeout(fn, ms),
    clearTimeout: (id) => clock.clearTimeout(id),
    setInterval: () => 0,
    clearInterval: () => {},
    requestAnimationFrame: () => 0,
    cancelAnimationFrame: () => {},
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    performance: { now: () => clock.now },
    addEventListener: () => {},
    removeEventListener: () => {},
    structuredClone: (v) => JSON.parse(JSON.stringify(v)),
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  const ctx = vm.createContext(sandbox);

  const paints = [];
  const commits = [];
  const appends = [];
  const handlers = { caption: null, status: null, external: null };
  sandbox.sotto = {
    onCaption: (cb) => { handlers.caption = cb; },
    onStatus: (cb) => { handlers.status = cb; },
    onExternalCaption: (cb) => { handlers.external = cb; },
    onGeometry: () => {},
    onStats: () => {},
    getStats: () => new Promise(() => {}),
    captionApplied: (text) => { commits.push({ at: clock.now, text: String(text) }); },
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
    setTranslationTarget: () => {},
    history: {
      root: () => Promise.resolve({ root: '' }),
      tail: () => Promise.resolve({ entries: [] }),
      // THE COMMIT META, AS THE STORE RECEIVES IT — route, start, routeSource,
      // reason. `null` entry = "the store refused this line", which is the honest
      // no-op for a replay with no disk.
      append: (text, meta) => { appends.push({ at: clock.now, text: String(text), meta: meta || null }); return Promise.resolve({ entry: null }); },
    },
  };

  vm.runInContext(sources.engine, ctx, { filename: 'caption-formulation.js' });
  vm.runInContext(sources.stable, ctx, { filename: 'stable-words.js' });
  vm.runInContext(sources.history, ctx, { filename: 'history-source.js' });
  vm.runInContext(sources.panel, ctx, { filename: 'panel.js' });

  // The panel's OWN paint counter is the sink: it is installed after panel.js has
  // defined it, exactly as a shell adapter would.
  sandbox.SottoPaintSink = (row) => { paints.push(Object.assign({}, row)); };

  // THE COMMIT META, READ AT THE STORE SEAM. `recordHistory` asks the DOM-free
  // history-source predicate which route this commit would take; wrapping it (and
  // returning the SHIPPED verdict unchanged) records exactly what the panel decided
  // without altering a decision. A line the store refuses never reaches
  // `history.append`, so this is the only place every commit's route is visible.
  const metas = [];
  if (sandbox.SottoHistorySource && typeof sandbox.SottoHistorySource.transcriptRoute === 'function') {
    const realRoute = sandbox.SottoHistorySource.transcriptRoute;
    sandbox.SottoHistorySource.transcriptRoute = function (meta) {
      const route = realRoute(meta);
      metas.push({
        at: clock.now,
        // THE ENGINE'S OWN WORDS (`caption-formulation.js commit`), not this
        // harness's reading of them.
        route: meta && meta.route !== undefined ? meta.route : null,
        reason: meta && meta.reason !== undefined ? meta.reason : null,
        routeSource: meta && meta.routeSource !== undefined ? meta.routeSource : null,
        start: meta && meta.start !== undefined ? meta.start : null,
        producer: meta && meta.producer !== undefined ? meta.producer : null,
        // What the SHIPPED predicate did with it — recorded, never changed.
        accepted: route === undefined ? null : route,
      });
      return route;
    };
  }

  const feed = (text, meta) => {
    if (!handlers.caption) die('panel.js never called bridge.onCaption');
    handlers.caption({ text, meta });
  };
  return { doc, paints, commits, appends, metas, created, feed, handlers };
}

/* ── NORMALISATION FOR THE JOIN ─────────────────────────────────────────────
 * The commit text is FORMULATED (capitalised, punctuated, seams healed), so the
 * paint/commit join cannot be string equality. Case, whitespace and punctuation
 * are dropped on both sides — the same normalisation the log analysis needs — and
 * a join that still fails is REPORTED as unmatched rather than approximated.
 */
function norm(text) {
  return String(text == null ? '' : text)
    .toLowerCase()
    .replace(/[^\p{L}\p{N} ]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function percentile(sorted, p) {
  if (!sorted.length) return null;
  const i = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[i];
}
function stats(values) {
  const v = values.filter((x) => typeof x === 'number' && isFinite(x)).sort((a, b) => a - b);
  return {
    n: v.length,
    p50: percentile(v, 50),
    p95: percentile(v, 95),
    max: v.length ? v[v.length - 1] : null,
    mean: v.length ? Math.round(v.reduce((a, b) => a + b, 0) / v.length) : null,
  };
}

/* ── THE CORPUS ───────────────────────────────────────────────────────────── */
const fallbackCorpus = [
  // No `stable` at all: the population the deadline still owns. Three lines, one
  // fragment each, the way the player channel and a pre-2026-10-30 worker emit.
  { t: 0, text: 'a queda do sinal', meta: { start: 0, end: 1.5, final: false } },
  { t: 60000, text: 'fez o resto', meta: { start: 2, end: 3.5, final: false } },
  { t: 120000, text: 'e ningue\u0301m soube', meta: { start: 4, end: 5.5, final: true } },
];

function main() {
  const arm = String(arg('--arm', 'after'));
  if (arm !== 'after' && arm !== 'before') die('--arm must be after|before');

  let corpus;
  let corpusName;
  let baseEpoch = null;
  if (arg('--fallback-corpus', false) !== false) {
    corpus = fallbackCorpus;
    corpusName = 'fallback:synthetic';
  } else {
    const file = arg('--corpus', null);
    if (!file) die('--corpus <file.json> or --fallback-corpus is required');
    const text = read(file);
    const parsed = JSON.parse(text);
    corpus = Array.isArray(parsed) ? parsed : parsed.fragments;
    corpusName = path.basename(file) + ' sha256=' + sha256(text).slice(0, 16);
    if (!Array.isArray(parsed) && parsed.base_epoch_ms) baseEpoch = Number(parsed.base_epoch_ms);
    if (!Array.isArray(corpus) || !corpus.length) die('corpus has no fragments: ' + file);
  }

  const sources = { panel: read(FILES.panel), engine: read(FILES.engine), stable: read(FILES.stable), history: read(FILES.history) };
  const shipped = { panel: sha256(sources.panel), engine: sha256(sources.engine) };

  let mutantPath = null;
  if (arm === 'before') {
    // REVERT THE ONE LINE THIS LANE ADDED, in memory, and land the mutated copy on
    // disk under `_main/_neg/` so the mutant can be read and hashed. The line is
    // matched EXACTLY: a silent miss would be a "before" that is really the
    // "after", i.e. a control that cannot go red.
    const stableCommit = 'if (meta && meta.stable === true) commit(\'stable\');';
    if (sources.engine.indexOf(stableCommit) === -1) {
      die('the stable commit line is not in caption-formulation.js — the before arm cannot be built: ' + stableCommit);
    }
    sources.engine = sources.engine.replace(stableCommit, '/* --arm before: stable commit removed */');
    // THE MUTANT LANDS WHERE A READER CAN INSPECT IT, NEVER INSIDE THE TREE: a
    // stray `app/panel/*.js` would be picked up by the panel's own asset and
    // health gates, and a stray file under `_main/` is noise in every `git status`.
    const dir = String(arg('--mutant-dir', '') || path.join(require('os').tmpdir(), 'sotto-panel-commit-stable'));
    fs.mkdirSync(dir, { recursive: true });
    mutantPath = path.join(dir, 'caption-formulation.before.js');
    fs.writeFileSync(mutantPath, sources.engine);
  }

  const t0 = corpus[0].t || 0;
  const clock = makeClock(t0);
  const panel = buildPanel(sources, clock);

  // Every paint is stamped with the arrival instant of the fragment that produced
  // it, so `push -> paint` is a measurement and not an assumption: the feed is
  // synchronous, so the paint happens at the fragment's own clock reading.
  let currentFragmentT = null;
  let currentFragmentTap = null;
  panel.doc.getElementById('caption-list');
  const feedOne = (frag) => {
    currentFragmentT = frag.t;
    currentFragmentTap = frag.meta && frag.meta.tap_ms !== undefined ? frag.meta.tap_ms : null;
    panel.feed(frag.text, frag.meta || {});
  };
  const paintsWithArrival = () => panel.paints.map((row) => ({
    at: row.at,
    arrival: row.arrival === undefined ? row.at : row.arrival,
    id: row.id === undefined ? null : row.id,
    src: row.src === undefined ? null : row.src,
    start: row.start === undefined ? null : row.start,
    conf: row.conf,
    prov: row.prov,
    tap_ms: row.tap_ms === undefined ? null : row.tap_ms,
    text: row.text,
  }));

  // The paint row itself does not carry the arrival (it must not: the panel must
  // not know about a replay), so the harness pairs each paint with the fragment
  // that was being fed at that instant.
  const paintArrivals = [];
  const sinkWrapGuard = () => {
    // paint rows are appended to panel.paints by the sandbox sink; walk them and
    // stamp the arrival from the feed that is in progress right now.
    for (const row of panel.paints) {
      if (row.arrival === undefined) {
        row.arrival = currentFragmentT === null ? row.at : currentFragmentT;
        // THE CAPTURE CLOCK the shell times `audio_ms` from (`CAPTION_IN tap_ms`).
        row.tap_ms = currentFragmentTap;
        paintArrivals.push(row);
      }
    }
  };

  for (const frag of corpus) {
    clock.advanceTo(frag.t);
    feedOne(frag);
    sinkWrapGuard();
  }
  // The stream stops; the deadline for anything still held must be allowed to fire.
  clock.advanceTo((corpus[corpus.length - 1].t || 0) + 10000);
  sinkWrapGuard();

  const paintRows = paintsWithArrival();
  const commits = panel.commits.slice();

  // ── THE THREE NUMBERS ────────────────────────────────────────────────────
  // leg 1  push -> provisional paint : what the owner's EYE gets, and when.
  // leg 2  paint -> commit           : the leg the 1500 ms deadline dominated.
  // leg 3  push -> commit            : the audit's `push -> panel-applied`.
  const legPushToPaint = paintRows.map((r) => r.at - r.arrival);
  const legPaintToCommit = [];
  const legPushToCommit = [];
  let unmatched = 0;
  let lastPaintIndex = -1;
  for (const commit of commits) {
    const want = norm(commit.text);
    let hit = -1;
    for (let i = paintRows.length - 1; i >= 0; i -= 1) {
      if (paintRows[i].at > commit.at) continue;
      if (norm(paintRows[i].text) === want) { hit = i; break; }
    }
    if (hit < 0) {
      // No paint carried this text (a seam-healed or re-formulated line). Reported,
      // never silently counted as a zero.
      unmatched += 1;
      for (let i = paintRows.length - 1; i >= 0; i -= 1) {
        if (paintRows[i].at <= commit.at) { hit = i; break; }
      }
      if (hit < 0) continue;
    }
    if (hit > lastPaintIndex) lastPaintIndex = hit;
    legPaintToCommit.push(commit.at - paintRows[hit].at);
    legPushToCommit.push(commit.at - paintRows[hit].arrival);
  }

  // THE TWO CLOCKS THE SHELL PUBLISHES (`CAPTION_APPLIED`), re-derived here so the
  // population can be judged the way the field judges it:
  //   queue_ms — the push of the fragment to the acknowledgement (the shell's
  //              `queue_ms`, `_last_push_at` -> `_caption_applied`)
  //   audio_ms — the capture instant of that audio to the acknowledgement (the
  //              shell's `audio_ms`, `tap_ms` -> `_caption_applied`)
  const commitRows = [];
  for (const commit of commits) {
    const want = norm(commit.text);
    let hit = -1;
    for (let i = paintRows.length - 1; i >= 0; i -= 1) {
      if (paintRows[i].at > commit.at) continue;
      if (norm(paintRows[i].text) === want) { hit = i; break; }
    }
    if (hit < 0) {
      for (let i = paintRows.length - 1; i >= 0; i -= 1) {
        if (paintRows[i].at <= commit.at) { hit = i; break; }
      }
    }
    if (hit < 0) continue;
    const paint = paintRows[hit];
    const audioMs = (baseEpoch !== null && paint.tap_ms !== null && paint.tap_ms !== undefined)
      ? (baseEpoch + commit.at) - paint.tap_ms
      : null;
    commitRows.push([commit.at - paint.arrival, audioMs]);
  }

  const band = legPushToCommit.filter((x) => x >= 1490 && x <= 1520).length;
  // A SECOND, INDEPENDENT CORRELATION: the panel's own row identity. The paint row
  // carries `id = rowIdentity(source, start)` (what `addCaption` keys the row by) and
  // the commit meta carries the same `start`, so a reader can join the two legs
  // without trusting this file's text normalisation at all.
  const paintIds = new Set(paintRows.map((r) => r.id));
  const metas = panel.metas.slice();
  const joinById = metas.filter((m) => m.start !== null && paintIds.has(m.start)).length;
  const routes = {};
  for (const m of metas) routes[String(m.route) + '/' + String(m.routeSource)] = (routes[String(m.route) + '/' + String(m.routeSource)] || 0) + 1;
  const out = {
    arm,
    corpus: corpusName,
    fragments: corpus.length,
    paints: paintRows.length,
    commits: commits.length,
    commitTexts: commits.length,
    unmatchedCommits: unmatched,
    joinById,
    metaRows: metas.length,
    routes,
    domCreated: panel.created,
    appendCalls: panel.appends.length,
    appendRoutes: panel.appends.map((a) => (a.meta && a.meta.route) || null),
    appendReasons: panel.appends.map((a) => (a.meta && a.meta.reason) || null),
    appendRouteSources: panel.appends.map((a) => (a.meta && a.meta.routeSource) || null),
    legs: {
      pushToPaint: stats(legPushToPaint),
      paintToCommit: stats(legPaintToCommit),
      pushToCommit: stats(legPushToCommit),
    },
    commitRows,
    band1490to1520: band,
    bandShare: legPushToCommit.length ? Math.round((band / legPushToCommit.length) * 1000) / 10 : null,
    sha256: { panel: shipped.panel, engine: shipped.engine, engineArmUsed: sha256(sources.engine) },
    mutant: mutantPath,
    // The rows themselves, so a reader can re-compute every number above.
    sample: paintRows.slice(0, 3).map((r) => ({ at: r.at, arrival: r.arrival, id: r.id, text: String(r.text).slice(0, 48) })),
  };
  process.stdout.write(JSON.stringify(out, null, 2) + '\n');
}

main();
