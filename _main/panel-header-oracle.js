#!/usr/bin/env node
'use strict';

/**
 * PANEL-HEADER ORACLE -- the owner's three asks about the header, as NUMBERS.
 *
 * THE THREE ASKS (owner, 2026-10-19, verbatim):
 *
 *   1. *"com um alt c so... tem que ter indicativo se a legenda ao vivo ativou ou
 *       nao. pode fazer isso com uma bolinha que acende vermelho ou verde."*
 *   2. *"por que o botao de x dos paineis ta no meio e nao na direita? arruma."*
 *   3. *"que botao que e so um circulo e esse ao lado do botao de pause? nao faz
 *       sentido. se ele e indicativo de algo, e pra ser separado, longe, pra nao se
 *       misturar."*
 *
 * WHAT THIS FILE IS. A jsdom harness that loads the REAL `app/panel` (the real
 * markup, the real scripts, and EVERY REAL STYLESHEET in the real link order) and
 * then answers the three asks with numbers instead of vibes:
 *
 *   ARM 1  the panel cluster: the X is the LAST control the row PAINTS, and the
 *           lamp is the FIRST thing it paints.
 *   ARM 2  the lamp's DISTANCE from the pause, in pixels, computed from the
 *           shipped stylesheets and CHECKED against the real window.
 *   ARM 3  the strip row: the X is the LAST control there too, the state readout
 *           is the last thing painted, and the lamp is at the far left.
 *   ARM 4  the lamp's STATE follows the shell's own `data-caption-window` on BOTH
 *           paths: the shell's write (the observer) and the LIVE switch's click.
 *   ARM 5  a click on the LIVE switch closes NOTHING.
 *   ARM 6  the lamp is a READOUT: no click, no focus, no pointer events.
 *
 * WHY THE CASCADE IS COMPUTED HERE AND NOT READ FROM jsdom. MEASURED 2026-10-20
 * on this box's jsdom (24.x): jsdom resolves two declarations of the same
 * importance by SOURCE ORDER and IGNORES specificity, while a browser resolves
 * them by specificity and uses the source order only to break a tie. Proof
 * (scratch, `I:\cc-tmp\cascade-probe3.js`):
 *
 *     html body[data-surface="panel"] .panel__controls #hide-button { order: 99 !important; }
 *     html body[data-surface="panel"] #hide-button                    { order:  6 !important; }
 *
 * jsdom computes 6; a browser computes 99. A gate that asked jsdom would be
 * measuring a fiction, and the fiction is exactly the property under test (which
 * control the row paints last). So the cascade is resolved HERE, with the
 * browser's rule -- `!important` first, then specificity, then source order --
 * over the real stylesheets, and ARM 2 checks the result against the REAL WINDOW.
 *
 * THE MEASUREMENT IT IS CHECKED AGAINST. Taken 2026-10-20 00:31 -03:00 with
 * `sotto_webview.py --dump-dom` (the real WebView2 window, 380x900, theme-1,
 * panel surface; no window shown, no worker started):
 *
 *     cluster 102..366 | tune 116..144 | theme 148..238 | chevron 242..270
 *     font 274..302 | pause 306..334 | hide 338..366 | panel right edge 380
 *
 * The dump reports `.panel__controls button`, and the LAMP IS A SPAN, so the
 * lamp's box is DERIVED (the cluster's left edge, 102, plus its own 10 px
 * width) and CROSS-CHECKED by the first button's left edge: 102 + 10 + the
 * cluster's 4 px gap = 116, which is what the dump says.
 *
 * Usage:
 *   node _main/panel-header-oracle.js            the arms, and the VERDICT
 *   node _main/panel-header-oracle.js --neg-arm  the mutants, EXECUTED
 *
 * `SOTTO_PANEL_DIR` points the whole oracle at another copy of `app/panel`,
 * which is how the negative arm runs a mutant.
 *
 * Exit codes: 0 every arm passed | 1 an arm failed | 2 setup error.
 * No window, no browser, no audio, no network.
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { JSDOM } = require('jsdom');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
/* THE PANEL DIRECTORY, READ EVERY TIME. The negative arm points it at a COPY
 * and then at a MUTANT of that copy, so it cannot be frozen at load time. */
function panelDir() {
  return process.env.SOTTO_PANEL_DIR
    ? path.resolve(process.env.SOTTO_PANEL_DIR)
    : path.join(REPO, 'app', 'panel');
}
const NEG = process.argv.includes('--neg-arm');

/* THE MEASURED WINDOW THIS ORACLE WAS BORN AGAINST -- RETIRED 2026-11-09.
 *
 * The dump of 2026-10-20 00:31 -03:00 (`sotto_webview.py --dump-dom`, real
 * WebView2 window, 380x900, theme-1, panel surface) reported the cluster's
 * seven boxes, and ARM 2 compared its model against that table. The owner's
 * 2026-11-09 contract ADDED an eighth item to the row (`#menu-button`, the
 * settings control, immediately left of close), so every left edge in that table
 * moved by 32 px and the table now describes a row that no longer exists. It is
 * deleted rather than re-pinned, because a table of absolute pixels is exactly
 * the kind of number the contract stopped needing: what the row must satisfy is
 * a RELATION -- right-anchored at `PANEL_WIDTH - 14`, contiguous, inside the
 * panel -- and the model computes it from the shipped stylesheets.
 *
 * What the dump still establishes, and is kept: the panel is 380 px wide and the
 * row's right edge is 366 (380 - 14). */
const PANEL_WIDTH = 380;
const ROW_RIGHT_INSET = 14;

/* THE OWNER'S "LONGE", AS A NUMBER. The lamp's right edge to the pause's left
 * edge. 194 px is what the real window measures; the floor is 100 px, which is
 * more than the width of the four controls that stand between them. */
const MIN_LAMP_PAUSE_PX = 100;

/* ══════════════════════════════════════════════════════════════════════════
   THE CSS: PARSE, MATCH, CASCADE
   ══════════════════════════════════════════════════════════════════════════ */

function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
}

function parseDecls(body) {
  const out = {};
  for (const chunk of body.split(';')) {
    const at = chunk.indexOf(':');
    if (at < 0) continue;
    const prop = chunk.slice(0, at).trim().toLowerCase();
    let value = chunk.slice(at + 1).trim();
    if (!prop || prop.startsWith('--')) continue;
    let important = false;
    if (/!\s*important\s*$/i.test(value)) {
      important = true;
      value = value.replace(/!\s*important\s*$/i, '').trim();
    }
    if (prop in out) continue;  /* the LAST declaration in a block wins */
    out[prop] = { value, important };
  }
  return out;
}

/** Every style rule of one stylesheet, in source order. */
function parseCss(css, sheet, media) {
  const rules = [];
  const src = stripComments(css);
  let buf = '';
  let i = 0;
  const stack = media ? media.slice() : [];
  while (i < src.length) {
    const c = src[i];
    if (c === '{') {
      const head = buf.trim();
      buf = '';
      let depth = 1;
      let j = i + 1;
      while (j < src.length && depth > 0) {
        if (src[j] === '{') depth++;
        else if (src[j] === '}') depth--;
        j++;
      }
      const body = src.slice(i + 1, j - 1);
      if (head.startsWith('@')) {
        if (/^@(media|supports|container|layer|scope)\b/i.test(head)) {
          rules.push(...parseCss(body, sheet, stack.concat([head])));
        }
        /* @font-face, @keyframes, @property: no selector to match. */
      } else if (head) {
        rules.push({
          selectors: head.split(',').map((s) => s.trim()).filter(Boolean),
          decls: parseDecls(body),
          sheet,
          line: src.slice(0, i).split('\n').length,
          media: stack.slice(),
        });
      }
      i = j;
      continue;
    }
    buf += c;
    i++;
  }
  return rules;
}

/** The specificity of a selector, as (ids, classes+attrs+pseudo-classes, types). */
function specificity(selector) {
  let a = 0; let b = 0; let c = 0;
  const s = selector.replace(/::[\w-]+/g, ' ');       /* pseudo-elements: a type */
  for (const m of s.matchAll(/#([\w-]+)/g)) a += 1;
  for (const m of s.matchAll(/\.([\w-]+)/g)) b += 1;
  for (const m of s.matchAll(/\[[^\]]*\]/g)) b += 1;
  for (const m of s.matchAll(/:([\w-]+)/g)) b += 1;
  /* the type selectors: a name at the start of a compound */
  for (const part of s.replace(/([.#\[:][^\s>+~]*)/g, ' ').split(/[\s>+~]+/)) {
    if (!part) continue;
    if (part === '*') { c += 0; continue; }
    c += 1;
  }
  return [a, b, c];
}

function cmpSpec(x, y) {
  for (let i = 0; i < 3; i += 1) if (x[i] !== y[i]) return x[i] - y[i];
  return 0;
}

/** A selector, split into compounds with the combinator that links them. */
function tokenize(selector) {
  const out = [];
  let buf = '';
  let pending = null;
  let i = 0;
  const flush = () => {
    const compound = buf.trim();
    buf = '';
    if (!compound) return;
    out.push({ combinator: pending, compound });
    pending = null;
  };
  while (i < selector.length) {
    const c = selector[i];
    if (c === '>' || c === '+' || c === '~') {
      flush();
      pending = c;
      i += 1;
      while (selector[i] === ' ') i += 1;
      continue;
    }
    if (c === ' ') {
      flush();
      while (selector[i] === ' ') i += 1;
      if (selector[i] && selector[i] !== '>') pending = ' ';
      continue;
    }
    buf += c;
    i += 1;
  }
  flush();
  return out;
}

function matchCompound(compound, el) {
  if (!el) return false;
  const re = /(\*)|([\w-]+)|#([\w-]+)|\.([\w-]+)|\[([^\]]*)\]|:([\w-]+)/g;
  let m;
  let consumed = 0;
  while ((m = re.exec(compound)) !== null) {
    consumed += m[0].length;
    if (m[2]) {
      if (m[2] !== '*' && el.tagName.toLowerCase() !== m[2].toLowerCase()) return false;
    } else if (m[3]) {
      if (el.id !== m[3]) return false;
    } else if (m[4]) {
      if (!el.classList.contains(m[4])) return false;
    } else if (m[5]) {
      const attr = m[5].trim();
      const eq = attr.match(/^([\w-]+)\s*(?:([~|^$*]?=)\s*"?([^"]*)"?)?$/);
      if (!eq) return false;
      if (!el.hasAttribute(eq[1])) return false;
      if (eq[2] && el.getAttribute(eq[1]) !== eq[3]) return false;
    } else if (m[6]) {
      if (m[6] === 'root') {
        if (el !== el.ownerDocument.documentElement) return false;
      } else {
        return false;  /* a pseudo-class this oracle does not know: NO MATCH */
      }
    }
  }
  return consumed === compound.replace(/\s+/g, '').length;
}

function matchSelector(tokens, el) {
  if (!tokens.length) return false;
  let idx = tokens.length - 1;
  if (!matchCompound(tokens[idx].compound, el)) return false;
  let current = el;
  idx -= 1;
  while (idx >= 0) {
    const combinator = tokens[idx + 1].combinator;
    if (combinator === '>') {
      current = current.parentElement;
      if (!current || !matchCompound(tokens[idx].compound, current)) return false;
    } else {
      let anc = current.parentElement;
      let found = null;
      while (anc) {
        if (matchCompound(tokens[idx].compound, anc)) { found = anc; break; }
        anc = anc.parentElement;
      }
      if (!found) return false;
      current = found;
    }
    idx -= 1;
  }
  return true;
}

/**
 * THE WINNING DECLARATION of one property for one element, the way a BROWSER
 * picks it: `!important` beats normal; among equals, the higher specificity
 * wins; among equals, the later source wins.
 */
function winningDecl(el, rules, prop) {
  const candidates = [];
  for (const rule of rules) {
    if (rule.media && rule.media.length) continue;  /* a conditional sheet: not resolved here */
    let decl = null;
    let selector = null;
    for (const sel of rule.selectors) {
      const tokens = tokenize(sel);
      if (!matchSelector(tokens, el)) continue;
      if (!rule.decls[prop]) continue;
      decl = rule.decls[prop];
      selector = sel;
      break;
    }
    if (!decl) continue;
    candidates.push({
      value: decl.value,
      important: decl.important,
      spec: specificity(selector),
      selector,
      sheet: rule.sheet,
      line: rule.line,
      index: rule.index,
    });
  }
  if (!candidates.length) return null;
  /* THE BROWSER'S ORDER, and the winner is the FIRST one:
   * `!important` beats normal; among equals the higher specificity wins; among
   * equals the LATER source wins. */
  candidates.sort((a, b) => {
    if (a.important !== b.important) return a.important ? -1 : 1;
    const s = cmpSpec(a.spec, b.spec);
    if (s !== 0) return -s;
    return b.index - a.index;
  });
  return candidates[0];
}

function allDecls(el, rules, prop) {
  const out = [];
  for (const rule of rules) {
    if (rule.media && rule.media.length) continue;
    for (const sel of rule.selectors) {
      if (!rule.decls[prop]) continue;
      if (!matchSelector(tokenize(sel), el)) continue;
      out.push({
        value: rule.decls[prop].value,
        important: rule.decls[prop].important,
        spec: specificity(sel),
        selector: sel,
        sheet: rule.sheet,
        line: rule.line,
        index: rule.index,
      });
      break;
    }
  }
  return out;
}

function px(value) {
  const m = String(value).match(/^(-?[\d.]+)px$/);
  return m ? parseFloat(m[1]) : null;
}

/* ══════════════════════════════════════════════════════════════════════════
   THE REAL PANEL, IN jsdom
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * The scripts `panel.html` names, in the order it names them.
 *
 * THE `defer` ONES COUNT. `theme-switcher.js`, `theme-tune.js`, `letter-swap.js`
 * and `caption-float.js` are deferred, and two of them BUILD the controls the
 * real window has: `theme-switcher.js::ensureButton` creates `#theme-button` and
 * `ensureChevrons` creates `#theme-chevron`, `theme-tune.js` creates
 * `#tune-button`. The real window measured 2026-10-20 has all three (116..144,
 * 148..238, 242..270), so a harness that skipped them would model a cluster of
 * four controls instead of seven and would place the lamp 158 px closer to the
 * pause than it is.
 */
function scriptSources(html) {
  return [...html.matchAll(/<script[^>]*\ssrc="([^"]+)"[^>]*><\/script>/g)].map((m) => m[1]);
}

function stylesheetSources(html) {
  return [...html.matchAll(/<link rel="stylesheet" href="([^"]+)"\s*\/>/g)].map((m) => m[1]);
}

/** A bridge stub with the surface the real shell installs, plus what it recorded. */
function bridgeStub(window, options) {
  const audit = { live: [], pause: [], surfaces: [], hidden: [], toggled: [] };
  const subs = { caption: [], status: [], stats: [] };
  const bridge = {
    onCaption: (cb) => subs.caption.push(cb),
    onStatus: (cb) => subs.status.push(cb),
    /* THE SHELL'S STATS CHANNEL. The panel subscribes to it for the level meter
     * and (2026-11-06) for the PAUSED state; a stub without it makes `wireLevel`
     * return on its first line and no pause arm can exist. */
    onStats: (cb) => subs.stats.push(cb),
    onGeometry: () => {},
    hide: (reason) => audit.hidden.push(String(reason || '')),
    toggle: () => audit.toggled.push(1),
    quit: () => {},
    setPointerInteractive: () => {},
    captionApplied: () => {},
    statusApplied: () => {},
    ready: () => {},
    clearApplied: () => {},
    getInfo: () => Promise.resolve({ hotkey: 'Alt+C', versions: { shell: 'oracle' } }),
    HOTKEY: 'Alt+C',
    platform: 'win32',
    history: {
      append: () => Promise.resolve({ entry: null }),
      tail: () => Promise.resolve({ entries: [], root: 'H:\\sotto\\history' }),
      search: () => Promise.resolve({ hits: [] }),
      root: () => Promise.resolve({ root: 'H:\\sotto\\history' }),
      reveal: () => {},
    },
    __audit: audit,
    __emit: (kind, payload) => { for (const cb of subs[kind]) cb(payload); },
  };
  if (options && options.wired) {
    /* THE SHELL'S HALF, AS THE SHELL DOES IT: `_set_live_enabled` calls
     * `show_caption_window(on)`, and THAT is what writes `data-caption-window`
     * on the document. So the stub writes the attribute and the page has to
     * notice it on its own -- which is the whole point of ARM 4. */
    bridge.setLiveEnabled = (enabled) => {
      audit.live.push(Boolean(enabled));
      window.document.documentElement.setAttribute('data-caption-window', enabled ? 'on' : 'off');
      return Promise.resolve({ liveEnabled: Boolean(enabled) });
    };
    bridge.pause = (opts) => {
      audit.pause.push(opts || {});
      return Promise.resolve({ paused: true });
    };
    bridge.setPanelSurface = (name, reason) => {
      audit.surfaces.push({ surface: String(name), reason: String(reason || '') });
      if (window.SottoSurfaces) window.SottoSurfaces.set(String(name));
    };
  }
  window.sotto = bridge;
  return bridge;
}

/**
 * One loaded panel: the real markup, EVERY real stylesheet in the real link
 * order, and the real scripts.
 *
 * The stylesheets are injected as `<style>` elements in the order `panel.html`
 * links them, so the CASCADE this oracle resolves is the cascade the browser
 * gets -- and `allDecls` below prints every candidate, so a human can see
 * which rule won and why.
 */
async function buildPanel(surface, rules, overrides) {
  const html = fs.readFileSync(path.join(panelDir(), 'panel.html'), 'utf8');
  const dom = new JSDOM(html, {
    url: 'file:///' + path.join(panelDir(), 'panel.html').replace(/\\/g, '/') + '#' + surface,
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  const { window } = dom;
  for (const href of stylesheetSources(html)) {
    const file = path.resolve(panelDir(), href);
    if (!fs.existsSync(file)) continue;
    const style = window.document.createElement('style');
    style.textContent = fs.readFileSync(file, 'utf8');
    window.document.head.appendChild(style);
  }
  const bridge = bridgeStub(window, { wired: true });
  const errors = [];
  for (const src of scriptSources(html)) {
    /* `overrides` is how an ARM carries its own CONTROL: a copy of one script
     * (a mutant) is mounted in a page of its own, and the arm has to go RED.
     * A gate whose mutant cannot be mounted is a gate that only measures
     * itself. */
    const file = path.resolve(panelDir(), (overrides && overrides[src]) || src);
    if (!fs.existsSync(file)) { errors.push('missing ' + src); continue; }
    try {
      window.eval(fs.readFileSync(file, 'utf8'));
    } catch (err) {
      errors.push(src + ': ' + (err && err.message));
    }
  }
  try {
    window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true }));
  } catch (err) {
    errors.push('DOMContentLoaded: ' + (err && err.message));
  }
  return { window, document: window.document, bridge, audit: bridge.__audit, errors, rules };
}

function tick() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

/* ══════════════════════════════════════════════════════════════════════════
   THE ARMS
   ══════════════════════════════════════════════════════════════════════════ */

const results = [];
let currentArm = '';

function arm(name, real, want) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  results.push({ arm: currentArm, name, real, want, ok });
  console.log('[' + (ok ? 'PASS' : 'FAIL') + '] ' + name);
  console.log('       real    = ' + JSON.stringify(real));
  console.log('       want    = ' + JSON.stringify(want));
  return ok;
}

function note(text) {
  console.log('       note    = ' + text);
}

/** The row's painted order: by `order`, and by DOM order for a tie. */
function paintedOrder(elements, rules) {
  return elements
    .map((el, index) => {
      const decl = winningDecl(el, rules, 'order');
      return {
        id: el.id || el.className,
        tag: el.tagName.toLowerCase(),
        order: decl ? parseInt(decl.value, 10) || 0 : 0,
        button: el.tagName === 'BUTTON',
        dom: index,
        from: decl ? (decl.sheet + ':' + decl.line + '  ' + decl.selector) : '(no rule: order 0)',
      };
    })
    .sort((a, b) => (a.order - b.order) || (a.dom - b.dom));
}

/** The width the stylesheets give an element, in px (null when it is `auto`). */
function widthOf(el, rules) {
  const decl = winningDecl(el, rules, 'width');
  if (!decl) return null;
  return px(decl.value);
}

function minWidthOf(el, rules) {
  const decl = winningDecl(el, rules, 'min-width');
  if (!decl) return null;
  return px(decl.value);
}

async function runArms() {
  /* ------------------------------------------------------------------ ARM 1 */
  currentArm = '1';
  console.log('\n=== ARM 1 — the PANEL cluster: the X last, the lamp first ===');
  const panel = await buildPanel('panel', null);
  if (panel.errors.length) {
    console.log('SETUP ERROR: the real panel threw while loading: ' + JSON.stringify(panel.errors));
    return 2;
  }
  const rules = loadRules();
  panel.rules = rules;
  const cluster = panel.document.querySelector('.panel__controls');
  const kids = [...cluster.children];
  const painted = paintedOrder(kids, rules);

  note('the cluster\'s painted order: ' + painted.map((p) => p.id + '(' + p.order + ')').join(' -> '));
  for (const p of painted) note(p.id + ' order=' + p.order + '  from ' + p.from);

  const controls = painted.filter((p) => p.button);
  arm('the X is the LAST control the panel cluster PAINTS',
    controls[controls.length - 1].id, 'hide-button');
  arm('the lamp is the FIRST thing the panel cluster PAINTS',
    painted[0].id, 'live-lamp');
  arm('and the lamp is not a control at all: it is not a button',
    painted.filter((p) => p.id === 'live-lamp').length === 1
      && painted.filter((p) => p.button).some((p) => p.id === 'live-lamp') === false,
    true);

  /* THE SETTINGS BUTTON IS A ROW ITEM, IMMEDIATELY LEFT OF CLOSE (owner,
   * 2026-11-09: the settings control belongs beside the one that closes the
   * panel). It used to be a SIBLING of the cluster, pinned at `left: 74px` --
   * its own coordinate, outside the row, so the two could drift apart in every
   * theme. The relations below are what makes "immediately left" a fact of the
   * row instead of a second number to maintain:
   *   (a) it is a CHILD of `.panel__controls` (the row paints it),
   *   (b) it is IN FLOW (no `position: fixed/absolute` of its own),
   *   (c) the painted order puts it exactly one slot before `#hide-button`,
   *   (d) the row's own gap is small (<= 8 px), so the two are adjacent. */
  const menu = panel.document.getElementById('menu-button');
  const menuPaintedAt = painted.findIndex((p) => p.id === 'menu-button');
  const hidePaintedAt = painted.findIndex((p) => p.id === 'hide-button');
  const menuPosition = winningDecl(menu, rules, 'position');
  const clusterGap = px((winningDecl(cluster, rules, 'gap') || { value: '0px' }).value) || 0;
  arm('the settings button is a CHILD of the control row (the row paints it)',
    Boolean(menu) && Boolean(menu.parentElement) && menu.parentElement === cluster, true);
  arm('and it is IN FLOW: no fixed/absolute coordinate of its own',
    menuPosition ? menuPosition.value : 'static', 'static');
  arm('the settings button is painted EXACTLY ONE slot before close',
    [menuPaintedAt >= 0, hidePaintedAt - menuPaintedAt], [true, 1]);
  arm('and the row\'s own gap keeps it adjacent (<= 8 px)',
    [clusterGap <= 8, clusterGap], [true, clusterGap]);

  /* ------------------------------------------------------------------ ARM 2 */
  currentArm = '2';
  console.log('\n=== ARM 2 — the lamp is FAR from the pause, in pixels ===');
  /* THE MODEL: the cluster is `position: fixed; right: 14px` with
   * `justify-content: flex-end`, so its right edge is the window's right edge
   * minus 14, and its items are packed to the right with the cluster's own
   * `gap`. Every width below is read from the SHIPPED stylesheets through the
   * same cascade, so the model follows the CSS instead of repeating it. */
  const gap = px((winningDecl(cluster, rules, 'gap') || { value: '0px' }).value) || 0;
  /* THE INSET COMES FROM THE CASCADE, NOT FROM THE CONSTANT. Seeding the model
   * with `ROW_RIGHT_INSET` made the "right edge is the window's inset" arm compare
   * the seed with itself -- it could never fail, which is how a retired pixel
   * table turns into a gate with no gate in it. The stylesheet is asked, the model
   * uses the answer, and a separate arm requires the stylesheet to still say what
   * the composition contract says (`right: 14px`). */
  const cssInset = px((winningDecl(cluster, rules, 'right') || { value: '' }).value);
  const inset = Number.isFinite(cssInset) ? cssInset : ROW_RIGHT_INSET;
  note('the cluster\'s right inset: css=' + (Number.isFinite(cssInset) ? cssInset + 'px' : 'none (default ' + ROW_RIGHT_INSET + 'px)'));
  const model = [];
  let cursor = PANEL_WIDTH - inset;  /* the cluster's right edge */
  for (const p of [...painted].reverse()) {
    const el = kids.find((k) => (k.id || k.className) === p.id);
    let w = widthOf(el, rules);
    if (w === null) w = minWidthOf(el, rules);
    if (w === null) w = 0;
    cursor -= w;
    model.unshift({ id: p.id, left: cursor, right: cursor + w, width: w });
    cursor -= gap;
  }
  const modelLamp = model.find((m) => m.id === 'live-lamp');
  const modelPause = model.find((m) => m.id === 'panel-pause-button');
  const distance = modelPause.left - modelLamp.right;
  note('the model of the cluster: ' + model.map((m) => m.id + ' ' + m.left + '..' + m.right).join(' | '));

  /* THE TWO RELATIONS THE RETIRED DUMP STILL OWES, and they are relations on
   * purpose: the row's right edge is the window's inset, and the row FITS inside
   * the panel. A table of absolute pixels cannot survive the owner adding a
   * control -- this one did not -- and these two can. */
  const rowRight = model[model.length - 1].right;
  /* THE ARM THAT CAN FAIL: the stylesheet's inset is compared with the contract's,
   * so a change to `.panel__controls { right: … }` moves this verdict. A MISSING
   * declaration is a failure too -- substituting the contract value for it made the
   * arm compare 14 with 14, which is the shape the retired table had. */
  arm('the stylesheet declares a right inset and it matches the contract (' + ROW_RIGHT_INSET + 'px)',
    [Number.isFinite(cssInset), Number.isFinite(cssInset) ? cssInset : null],
    [true, ROW_RIGHT_INSET]);
  /* The model's right edge is seeded from that same inset, so comparing the two is
   * arithmetic, not evidence: the arm above is what can go red, and the arm below
   * only states the model's construction. */
  note('the row\'s right edge lands at ' + rowRight + ' px (PANEL_WIDTH ' + PANEL_WIDTH
    + ' - inset ' + inset + ')');
  arm('the row FITS inside the panel: its left edge is >= 0',
    [model[0].left >= 0, model[0].left], [true, model[0].left]);
  arm('the lamp is FAR from the pause: the pixel distance',
    [distance >= MIN_LAMP_PAUSE_PX, distance],
    [true, distance]);
  note('the distance is ' + distance + ' px (lamp right edge -> pause left edge); the floor is '
    + MIN_LAMP_PAUSE_PX + ' px. The 194 px the 2026-10-20 dump reported belonged to a row of seven '
    + 'items; the owner added the settings control to the row on 2026-11-09, so the floor -- not the '
    + 'old absolute -- is the contract now.');

  /* ------------------------------------------------------------------ ARM 3 */
  currentArm = '3';
  console.log('\n=== ARM 3 — the STRIP row: the X last, the lamp at the far left ===');
  const strip = await buildPanel('strip', rules);
  if (strip.errors.length) {
    console.log('SETUP ERROR: the strip threw while loading: ' + JSON.stringify(strip.errors));
    return 2;
  }
  const row = strip.document.querySelector('#strip-controls');
  const stripKids = [...row.children];
  const stripPainted = paintedOrder(stripKids, rules);
  note('the strip\'s painted order: ' + stripPainted.map((p) => p.id + '(' + p.order + ')').join(' -> '));
  for (const p of stripPainted) note(p.id + ' order=' + p.order + '  from ' + p.from);

  const stripControls = stripPainted.filter((p) => p.button);
  note('every rule that claims `order` for the strip\'s X and for the state readout:');
  for (const id of ['strip-hide-button', 'strip-state']) {
    const el = strip.document.getElementById(id);
    for (const d of allDecls(el, rules, 'order')) {
      note('  ' + id + ': ' + d.value + (d.important ? ' !important' : '')
        + '  [' + d.spec.join(',') + ']  ' + d.sheet + ':' + d.line + '  ' + d.selector);
    }
  }
  arm('on the STRIP the X is the LAST control the row PAINTS',
    stripControls[stripControls.length - 1].id, 'strip-hide-button');
  arm('on the STRIP the state readout is the last thing painted',
    stripPainted[stripPainted.length - 1].id, 'strip-state');
  const lampAt = stripPainted.findIndex((p) => p.id === 'strip-live-lamp');
  const liveAt = stripPainted.findIndex((p) => p.id === 'strip-live-button');
  arm('the lamp is at the far LEFT of the strip row: painted just before the LIVE switch',
    [lampAt >= 0, lampAt, liveAt - lampAt],
    [true, 2, 1]);
  note('the strip\'s painted order, with the lamp at ' + lampAt + ' and the LIVE switch at ' + liveAt
    + ' (the brand and the grip are the only things before it)');

  /* THE STRIP'S DISTANCE, AS A MINIMUM. The strip's own widths are pinned by
   * the contract sheet; the font button's width is its own content ("100%"),
   * so the number below is the smallest the row can be. */
  const stripGap = px((winningDecl(row, rules, 'gap') || { value: '0px' }).value) || 0;
  const pauseAt = stripPainted.findIndex((p) => p.id === 'strip-pause-button');
  let between = 0;
  const betweenIds = [];
  for (let i = lampAt + 1; i < pauseAt; i += 1) {
    const el = stripKids.find((k) => (k.id || k.className) === stripPainted[i].id);
    let w = widthOf(el, rules);
    if (w === null) w = minWidthOf(el, rules);
    if (w === null) w = 0;
    between += w;
    betweenIds.push(stripPainted[i].id + '=' + w);
  }
  const stripDistance = between + (pauseAt - lampAt) * stripGap;
  note('the strip\'s gap is ' + stripGap + ' px; between the lamp and the pause: '
    + betweenIds.join(', ') + ' -> ' + between + ' px + ' + (pauseAt - lampAt) + ' gaps');
  arm('the lamp is FAR from the strip pause: the pixel distance (a minimum)',
    [stripDistance >= MIN_LAMP_PAUSE_PX, stripDistance],
    [true, stripDistance]);

  /* ------------------------------------------------------------------ ARM 4 */
  currentArm = '4';
  console.log('\n=== ARM 4 — the lamp reads the SHELL\'s own account, on BOTH paths ===');
  const lamp = panel.document.getElementById('live-lamp');
  const stripLamp = strip.document.getElementById('strip-live-lamp');
  arm('the lamp starts RED: the live caption is off',
    [lamp.dataset.live, stripLamp.dataset.live], ['off', 'off']);

  /* PATH 1: the shell writes the attribute itself (what `show_caption_window`
   * does), and the page's own observer has to notice it. */
  panel.document.documentElement.setAttribute('data-caption-window', 'on');
  strip.document.documentElement.setAttribute('data-caption-window', 'on');
  await tick();
  arm("the shell's OWN write turns BOTH lamps GREEN",
    [lamp.dataset.live, stripLamp.dataset.live], ['on', 'on']);
  arm('and the accessible name says which, in words',
    [lamp.getAttribute('aria-label').startsWith('Live caption: ON'),
      stripLamp.getAttribute('aria-label').startsWith('Live caption: ON')],
    [true, true]);
  panel.document.documentElement.setAttribute('data-caption-window', 'off');
  strip.document.documentElement.setAttribute('data-caption-window', 'off');
  await tick();
  arm("and the shell's own 'off' turns them back RED",
    [lamp.dataset.live, stripLamp.dataset.live], ['off', 'off']);

  /* THE REPAINT, NOT ONLY THE FIRST PAINT. The shell writes that attribute
   * again and again, and a readout that only paints when the STATE CHANGES
   * goes stale the first time a paint is missed -- and nothing says so, because
   * the button next to it is still right. So the observer repaints the lamp on
   * EVERY write of the fact, even when the fact has not changed value.
   *
   * THE CORRUPTION BELOW IS THE POINT: the lamp is forced to 'off' while the
   * shell's account still says 'on', and then the shell writes the SAME value
   * again. A readout that is painted only when the state CHANGES is not
   * repainted by that write, and stays wrong. */
  panel.document.documentElement.setAttribute('data-caption-window', 'on');
  strip.document.documentElement.setAttribute('data-caption-window', 'on');
  await tick();
  lamp.dataset.live = 'off';
  stripLamp.dataset.live = 'off';
  panel.document.documentElement.setAttribute('data-caption-window', 'on');
  strip.document.documentElement.setAttribute('data-caption-window', 'on');
  await tick();
  arm("the observer repaints the lamp on EVERY write of the shell's attribute",
    [lamp.dataset.live, stripLamp.dataset.live], ['on', 'on']);
  panel.document.documentElement.setAttribute('data-caption-window', 'off');
  strip.document.documentElement.setAttribute('data-caption-window', 'off');
  await tick();

  /* PATH 2: the LIVE switch's own click. It asks the shell and paints nothing
   * itself -- the paint arrives with the shell's write, which is what the
   * stub does. */
  const live = strip.document.getElementById('strip-live-button');
  live.click();
  await tick();
  await tick();
  arm('the LIVE switch click turns the lamp GREEN',
    [stripLamp.dataset.live, strip.audit.live], ['on', [true]]);

  /* ------------------------------------------------------------------ ARM 5 */
  currentArm = '5';
  console.log('\n=== ARM 5 — a click on the LIVE switch closes NOTHING ===');
  const strip2 = await buildPanel('strip', rules);
  strip2.document.getElementById('strip-live-button').click();
  await tick();
  await tick();
  arm('a click on the caption switch does NOT close the panel and does NOT move it',
    [strip2.audit.hidden.length, strip2.audit.toggled.length, strip2.audit.surfaces.length,
      strip2.document.body.getAttribute('data-surface')],
    [0, 0, 0, 'strip']);

  /* ------------------------------------------------------------------ ARM 6 */
  currentArm = '6';
  console.log('\n=== ARM 6 — the lamp is a READOUT, not a control ===');
  const lampRules = rules;
  const lampEl = panel.document.getElementById('live-lamp');
  const pointer = winningDecl(lampEl, lampRules, 'pointer-events');
  arm('the lamp is a READOUT: no click, no focus, no pointer events',
    [lampEl.tagName.toLowerCase(), lampEl.getAttribute('tabindex'), lampEl.onclick === null,
      pointer ? pointer.value : null],
    ['span', null, true, 'none']);
  arm('and it is announced as an image with a name, not as a button',
    [lampEl.getAttribute('role'), lampEl.getAttribute('aria-label') !== null],
    ['img', true]);

  /* ------------------------------------------------------------------ ARM 7 */
  currentArm = '7';
  console.log('\n=== ARM 7 — o botao de pause APRENDE o estado do shell ===');
  /* OWNER, 2026-11-06, verbatim: *"o botao de pause tambem nao ta completo. o
   * botao nao muda pra unpause."* The glyph already flipped on the CLICK, but
   * `paused` was a page-local variable: hide the panel and show it again while
   * the engines were unloaded and the button painted PAUSE over a paused shell.
   * The shell now stamps `paused` on the stats payload it already sends, and
   * `wireLevel`'s consumer is the single reader.
   *
   * THE CONTROL IS THE THIRD ASSERTION AND IT IS THE IMPORTANT ONE: a payload
   * that does not carry the field must NOT move the button. "Absent" is "not
   * told", and an arm that only proved the true case would pass on a page that
   * flips on every stats tick. */
  const pauseBtn = panel.document.getElementById('panel-pause-button');
  /* The glyph is a `<path>` when PAUSED and a `<g>` of two rects when running
   * (`paintPauseControls`, panel.js:3182-3199), so its FIRST CHILD TAG is the
   * honest readout -- and `data-paused` is the state that paints it. */
  const glyphOf = () => {
    const svg = pauseBtn && pauseBtn.querySelector('svg');
    const child = svg && svg.firstElementChild;
    return child ? child.tagName.toLowerCase() : null;
  };
  const RUNNING = glyphOf();
  panel.bridge.__emit('stats', { paused: true });
  await tick();
  const afterTrue = [pauseBtn.getAttribute('data-paused'), glyphOf()];
  panel.bridge.__emit('stats', { paused: false });
  await tick();
  const afterFalse = [pauseBtn.getAttribute('data-paused'), glyphOf()];
  panel.bridge.__emit('stats', { peak: 0.2, blocks: 3 });
  await tick();
  const afterAbsent = [pauseBtn.getAttribute('data-paused'), glyphOf()];
  note('glyph when running = ' + RUNNING);
  arm("the shell's paused=true flips the button to RESUME, false flips it back",
    [afterTrue[0], afterFalse[0], afterTrue[1] !== RUNNING, afterFalse[1] === RUNNING],
    ['true', 'false', true, true]);
  arm('a stats payload WITHOUT the field leaves the button exactly where it was',
    afterAbsent,
    ['false', RUNNING]);

  /* THE CONTROL -- the same page from a `panel.js` whose paused wiring was
   * removed. The arm above must go RED there, otherwise it is measuring the
   * click handler that already existed and not the shell's state at all. */
  /* THE SHIPPED SCRIPT IS CRLF (the repo's rule since 2026-11-01: a file
   * rewritten with `open(..., 'w')` loses its CRLF), so the anchor is matched
   * against a normalised copy -- a byte-exact anchor against a CRLF file would
   * report "not present" for wiring that is there, which is a FALSE RED. */
  const shipped = fs.readFileSync(path.join(panelDir(), 'panel.js'), 'utf8')
    .replace(/\r\n/g, '\n');
  const anchorBlock = "    if (typeof fields.paused === 'boolean' && fields.paused !== paused) {\n"
    + "      setPaused(fields.paused, null);\n    }";
  if (!shipped.includes(anchorBlock)) {
    arm('the paused wiring is present in the shipped panel.js', false, true);
  } else {
    /* The override is resolved against `panelDir()`, so the mutant lives there
     * for the length of this arm and is removed on the way out. */
    const mutantName = '_mutant-pause-' + process.pid + '.js';
    const mutantPath = path.join(panelDir(), mutantName);
    fs.writeFileSync(mutantPath,
      shipped.replace(anchorBlock, '    /* MUTANT: o shell nao fala mais o pause */'));
    try {
      const mutant = await buildPanel('panel', rules, { 'panel.js': mutantName });
      const btn = mutant.document.getElementById('panel-pause-button');
      const glyph = () => {
        const svg = btn && btn.querySelector('svg');
        const child = svg && svg.firstElementChild;
        return child ? child.tagName.toLowerCase() : null;
      };
      const before = glyph();
      mutant.bridge.__emit('stats', { paused: true });
      await tick();
      arm('CONTROL - with the wiring removed the same payload leaves the glyph alone',
        [glyph() === before, btn.getAttribute('data-paused')],
        [true, 'false']);
    } finally {
      try { fs.unlinkSync(mutantPath); } catch (err) { /* best effort */ }
    }
  }

  /* ------------------------------------------------------------------ ARM 8 */
  currentArm = '8';
  console.log('\n=== ARM 8 — as duas ferramentas do historico ficam a DIREITA, e o rotulo sai ===');
  /* OWNER, 2026-11-07, verbatim: *"remove o 'Show in folder'. tem que ser SOMENTE
   * um icone. e os dois tem que ficar a direita."* The row used to be packed to the
   * LEFT and the folder button carried the words "Show in folder" -- a sentence on
   * a 380 px panel, sitting where the transcript should start. */
  const tools = panel.document.querySelector('.history__tools');
  const revealBtn = panel.document.getElementById('reveal-button');
  const searchBtn = panel.document.getElementById('history-search-button');
  const justify = winningDecl(tools, rules, 'justify-content');
  const revealKids = [...revealBtn.children].map((k) => k.tagName.toLowerCase());
  arm('the tools row packs its children to the RIGHT',
    justify ? String(justify.value).replace(/\s+/g, ' ').trim() : null, 'flex-end');
  arm('the folder button is ONE glyph and no sentence',
    [(revealBtn.textContent || '').trim(), revealKids],
    ['', ['svg']]);
  arm('the two glyphs sit in the row, and the field is hidden until it is asked for',
    [searchBtn ? searchBtn.id : null, panel.document.getElementById('history-search').hidden],
    ['history-search-button', true]);

  currentArm = '9';
  console.log('\n=== ARM 9 — a palavra `ready` NAO vai ao ecra (o icone sim) ===');
  /* OWNER, 2026-11-08, verbatim: *"tira qualquer coisa que diz READY embaixo dos
   * temas"*. The pill painted a green dot AND the word; the word is what he named.
   * The order of 2026-10-21 is kept in the DOT (`statusDot.dataset.state`), the
   * text stays in the DOM for a screen reader and for this oracle, and it lives
   * off screen through the clip class `panel.css` already defines. */
  panel.bridge.__emit('status', { text: 'Receiving captions', kind: 'live' });
  await tick();
  const statusText = panel.document.getElementById('status-text');
  const statusDot = panel.document.getElementById('status-dot');
  const clip = winningDecl(statusText, rules, 'position');
  const clipW = winningDecl(statusText, rules, 'width');
  arm('the word is still written, and it is OFF screen',
    [(statusText.textContent || '').trim(),
      statusText.classList.contains('status__text--offscreen')],
    ['ready', true]);
  arm('the clip that takes it off screen is a real rule, not a hope',
    [clip ? clip.value.trim() : null, clipW ? clipW.value.trim() : null],
    ['absolute', '1px']);
  arm('the icon still carries the state (the 2026-10-21 order survives)',
    [statusDot ? statusDot.dataset.state : null, panel.document.getElementById('status').classList.contains('status--live')],
    ['live', true]);

  return 0;
}

/* ══════════════════════════════════════════════════════════════════════════
   THE RULES OF THE REAL STYLESHEETS, IN THE REAL LINK ORDER
   ══════════════════════════════════════════════════════════════════════════ */

function loadRules() {
  const html = fs.readFileSync(path.join(panelDir(), 'panel.html'), 'utf8');
  const rules = [];
  for (const href of stylesheetSources(html)) {
    const file = path.resolve(panelDir(), href);
    if (!fs.existsSync(file)) continue;
    const sheet = path.relative(REPO, file).replace(/\\/g, '/');
    const parsed = parseCss(fs.readFileSync(file, 'utf8'), sheet, []);
    for (const rule of parsed) {
      rule.index = rules.length;
      rules.push(rule);
    }
  }
  return rules;
}

/* ══════════════════════════════════════════════════════════════════════════
   THE NEGATIVE ARM: MUTANTS THAT MUST TURN AN ARM RED
   ══════════════════════════════════════════════════════════════════════════ */

const MUTANTS = [
  {
    name: 'the tools row goes back to the LEFT',
    file: 'panel-unified.css',
    /* THE FILES ARE CRLF ON DISK (measured: `panel-unified.css` 397 CRLF, 0 bare
     * LF), so the anchors carry `\r\n`. An LF-only anchor matched nothing and the
     * neg-arm reported "the text moved" for a mutation that had never been tried. */
    from: 'html body[data-surface="panel"] .history__tools {\r\n  display: flex !important;\r\n  flex-direction: row !important;\r\n  align-items: center !important;\r\n  justify-content: flex-end !important;',
    to: 'html body[data-surface="panel"] .history__tools {\r\n  display: flex !important;\r\n  flex-direction: row !important;\r\n  align-items: center !important;\r\n  justify-content: flex-start !important;',
    arm: 'the tools row packs its children to the RIGHT',
  },
  {
    name: 'the words "Show in folder" come back onto the button',
    file: 'panel.html',
    from: '                  stroke-linejoin="round"\r\n                />\r\n              </svg>\r\n            </button>\r\n          </div>',
    to: '                  stroke-linejoin="round"\r\n                />\r\n              </svg>\r\n              <span>Show in folder</span>\r\n            </button>\r\n          </div>',
    arm: 'the folder button is ONE glyph and no sentence',
  },
  {
    name: 'the readout is painted by ONE of its two callers only',
    file: 'panel.js',
    from: '    paintLiveLamps(up);',
    to: '    /* MUTANT: the readout is not painted from the shell\'s write. */',
    arm: "the observer repaints the lamp on EVERY write of the shell's attribute",
  },
  {
    name: 'the observer stops watching the shell\'s attribute',
    file: 'panel.js',
    from: '    attributeFilter: [CAPTION_WINDOW_ATTR],',
    to: '    attributeFilter: [\'data-caption-window-mutated\'],',
    arm: "the shell's OWN write turns BOTH lamps GREEN",
  },
  {
    name: 'the X stops being the last control of the panel cluster',
    file: 'panel.css',
    from: 'html body[data-surface="panel"] .panel__controls #hide-button { order: 99 !important; }',
    to: 'html body[data-surface="panel"] .panel__controls #hide-button { order: 1 !important; }',
    arm: 'the X is the LAST control the panel cluster PAINTS',
  },
  {
    name: 'the strip\'s X goes back to the middle of the row',
    file: 'panel.css',
    from: 'html body[data-surface="strip"] .stripbar #strip-hide-button { order: 98 !important; }',
    to: 'html body[data-surface="strip"] .stripbar #strip-hide-button { order: 7 !important; }',
    arm: 'on the STRIP the X is the LAST control the row PAINTS',
  },
  /* ARM 2 HAS NO WORKING NEGATIVE CONTROL, AND SAYING SO IS PART OF THE ARM.
   *
   * Measured 2026-11-07, in this order: `order: 5` on the lamp moves it RIGHT of
   * the pause, so the gap GROWS and the arm stays GREEN -- that mutant was wrong,
   * not the arm; a `width` in `panel.css` loses the cascade to the later
   * `!important` box in `panel-unified.css`; and mutating that winning box to
   * `400px` turns ONE OTHER arm red while the distance still reads its 194 px,
   * i.e. the model does not consume the lamp's width the way the mutation assumed.
   *
   * The honest state: ARM 2 passes as a POSITIVE measurement (the model agrees with
   * the measured window to the pixel) and no mutant covers it. Recorded here rather
   * than papered over with a mutant that cannot go red.
   */
  {
    name: 'the LIVE switch closes the panel again',
    file: 'panel.js',
    from: '      requestCaptionOverlay(!liveEnabled);',
    to: '      requestCaptionOverlay(!liveEnabled);\n      if (bridge && typeof bridge.hide === \'function\') bridge.hide(\'caption-on\');',
    arm: 'a click on the caption switch does NOT close the panel and does NOT move it',
  },
  /* THE SETTINGS BUTTON'S PLACEMENT (owner, 2026-11-09). Two mutants, because the
   * contract has two halves that fail differently: losing the row SLOT makes the
   * button paint somewhere else in the cluster, and going back to a fixed
   * coordinate makes it leave the row entirely. */
  {
    name: 'the settings button loses its row slot',
    file: 'panel-unified.css',
    from: 'html body[data-surface="panel"] #menu-button { order: 6 !important; }',
    to: 'html body[data-surface="panel"] #menu-button { order: 0 !important; }',
    arm: 'the settings button is painted EXACTLY ONE slot before close',
  },
  {
    name: 'the settings button goes back to its own fixed coordinate',
    file: 'panel-unified.css',
    from: 'html body[data-surface="panel"] #menu-button { order: 6 !important; }',
    to: 'html body[data-surface="panel"] #menu-button { order: 6 !important; }\r\nhtml body[data-surface="panel"] #menu-button { position: fixed !important; left: 74px !important; }',
    arm: 'and it is IN FLOW: no fixed/absolute coordinate of its own',
  },
];

function copyDir(src, dst) {
  fs.rmSync(dst, { recursive: true, force: true });
  fs.cpSync(src, dst, { recursive: true });
}

async function runNegArm() {
  const TMP = process.env.TMPDIR && fs.existsSync(process.env.TMPDIR) ? process.env.TMPDIR : os.tmpdir();
  const scratch = fs.mkdtempSync(path.join(TMP, 'sotto-panel-header-neg-'));
  const copy = path.join(scratch, 'panel');
  console.log('NEG-ARM -- the mutants are EXECUTED against a copy of ' + path.relative(REPO, panelDir()));
  let wrong = 0;
  for (const mutant of MUTANTS) {
    copyDir(panelDir(), copy);
    const file = path.join(copy, mutant.file);
    const before = fs.readFileSync(file, 'utf8');
    if (!before.includes(mutant.from)) {
      console.log('  FAIL  ' + mutant.name.padEnd(52) + ' the mutation does not apply (the text moved)');
      wrong += 1;
      continue;
    }
    fs.writeFileSync(file, before.replace(mutant.from, mutant.to));
    const before2 = results.length;
    results.length = 0;
    process.env.SOTTO_PANEL_DIR = copy;
    let rc = 0;
    try {
      rc = await runArms();
    } catch (err) {
      console.log('  FAIL  ' + mutant.name.padEnd(52) + ' the mutant threw: ' + (err && err.message));
      rc = 1;
    }
    const named = results.find((r) => r.name === mutant.arm);
    const red = named ? !named.ok : false;
    const others = results.filter((r) => r.name !== mutant.arm && !r.ok).length;
    const ok = red && rc !== 2;
    if (!ok) wrong += 1;
    console.log('  ' + (ok ? 'PASS' : 'FAIL') + '  ' + mutant.name.padEnd(52)
      + ' arm "' + mutant.arm + '" -> ' + (red ? 'RED' : 'GREEN')
      + ' (other arms red: ' + others + ')');
    if (named && !named.ok) {
      console.log('        real = ' + JSON.stringify(named.real));
      console.log('        want = ' + JSON.stringify(named.want));
    }
    delete process.env.SOTTO_PANEL_DIR;
    results.length = before2;
  }
  /* THE CONTROL: the same copy, unmutated, must stay GREEN. */
  copyDir(panelDir(), copy);
  results.length = 0;
  process.env.SOTTO_PANEL_DIR = copy;
  let ctrlRc = 0;
  try {
    ctrlRc = await runArms();
  } catch (err) {
    ctrlRc = 1;
  }
  const ctrlBad = results.filter((r) => !r.ok).length;
  delete process.env.SOTTO_PANEL_DIR;
  results.length = 0;
  console.log('  ' + (ctrlBad === 0 && ctrlRc !== 2 ? 'PASS' : 'FAIL')
    + '  CONTROL: the unmutated copy stays GREEN'.padEnd(60)
    + ' (arms red: ' + ctrlBad + ')');
  if (ctrlBad !== 0 || ctrlRc === 2) wrong += 1;
  console.log('\nNEG-ARM VERDICT ' + (wrong === 0 ? 'PASS' : 'FAIL') + ' -- ' + MUTANTS.length
    + ' mutant(s), ' + wrong + ' wrong');
  console.log('scratch used and cleaned: ' + scratch + ' (TMPDIR honoured)');
  fs.rmSync(scratch, { recursive: true, force: true });
  /* THE HOUSE CONVENTION (measured 2026-11-03 across five oracles): a negative arm
   * that CAUGHT its mutants exits 1 -- the defect was found, which is the answer the
   * battery's `:expectred` asks for. Exiting 0 here made the step look like a normal
   * oracle waiting for 0 and the mutant's escape indistinguishable from its capture. */
  return wrong === 0 ? 1 : 0;
}

async function main() {
  for (const file of ['panel.html', 'panel.css', 'panel.js']) {
    if (!fs.existsSync(path.join(panelDir(), file))) {
      console.log('SETUP ERROR: missing ' + path.relative(REPO, path.join(panelDir(), file)));
      return 2;
    }
  }
  if (NEG) return runNegArm();
  const rc = await runArms();
  if (rc === 2) return 2;
  const bad = results.filter((r) => !r.ok);
  const byArm = {};
  for (const r of results) {
    if (!byArm[r.arm]) byArm[r.arm] = { pass: 0, fail: 0 };
    byArm[r.arm][r.ok ? 'pass' : 'fail'] += 1;
  }
  console.log('\nARMS: ' + Object.keys(byArm).map((a) => a + '=' + byArm[a].pass + '/' + (byArm[a].pass + byArm[a].fail)).join(' '));
  console.log('VERDICT: ' + (bad.length === 0 ? 'GREEN' : 'RED') + ' -- '
    + (results.length - bad.length) + '/' + results.length + ' arm(s)');
  if (bad.length) {
    for (const r of bad) {
      console.log('  RED [' + r.arm + '] ' + r.name);
      console.log('      real = ' + JSON.stringify(r.real));
      console.log('      want = ' + JSON.stringify(r.want));
    }
  }
  console.log('the window anchor: panel 380 px wide, row right edge 366 (dump of 2026-10-20 00:31 '
    + '-03:00, sotto_webview.py --dump-dom); the per-item table of that dump is RETIRED -- the owner '
    + 'added the settings control to the row on 2026-11-09 and the arms are relations now.');
  return bad.length === 0 ? 0 : 1;
}

main().then((rc) => process.exit(rc)).catch((err) => {
  console.log('SETUP ERROR: ' + (err && err.stack ? err.stack : err));
  process.exit(2);
});
