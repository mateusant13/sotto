/* panel-language-oracle.js -- EVERY STRING THE REAL PAGE PAINTS IS PT-BR
 *
 * THE DEFECT THIS GATE CLOSES (independent review, 2026-11-25): `panel.html`
 * is now Portuguese, but `panel.js` OVERWRITES ~40 of those strings in English
 * at runtime. A gate that reads the markup alone calls that page Portuguese;
 * a gate that reads the DOM after the real scripts ran does not.
 *
 * WHAT THIS RUNS: the REAL `app/panel/panel.html` in jsdom, every REAL script
 * in document order (same harness shape as `_main/panel-row-identity-oracle.js`
 * and `_main/panel-two-voices-oracle.js`), a stubbed preload bridge, and then
 * the SEVEN STATES the owner actually sees. No window, no browser, no audio
 * device, no network: jsdom only. `NODE_PATH=H:/sotto/node_modules`.
 *
 * ARMS
 *   L1 startup (bridge wired)      every painted text/title/aria is PT-BR
 *   L2 startup (no bridge)         the no-preload failure is PT-BR
 *   L3 live caption ON             the ON lamp/button/readout is PT-BR
 *   L4 live caption OFF            the OFF lamp/button/readout is PT-BR
 *   L5 paused                      the pause toggle and strip word are PT-BR
 *   L6 error + backlog             the cause and the stats chip are PT-BR
 *   L7 revive tooltip              both "restarting" sentences are PT-BR
 *
 * THE DETECTOR is deliberately not an English allowlist: a string FAILS when
 * it carries two or more distinctive English words, or one at the head of an
 * imperative/state phrase, or zero Portuguese function words. The tiny exact
 * allow-list holds only the two owner-ordered state words (`ready`, `not ready`)
 * that `_main/panel-header-oracle.js` arm 9 pins; language autonyms live in
 * <option> nodes and are not judged.
 *
 * NEGATIVE ARM: each mutant reverts ONE shipped writer to the English bytes it
 * replaced, in memory, and must redden its own arm(s) and no others.
 *
 *   node _main/panel-language-oracle.js             VERDICT: PASS, rc=0
 *   node _main/panel-language-oracle.js --neg-arm   every mutant RED, rc=1 by design
 */
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');

const REPO = path.resolve(__dirname, '..');
const PANEL = path.join(REPO, 'app', 'panel');
const NEG = process.argv.indexOf('--neg-arm') >= 0;

function say(line) { process.stdout.write(line + '\n'); }
function sha256(text) { return crypto.createHash('sha256').update(text, 'utf8').digest('hex'); }
function revision(file) {
  const buf = fs.readFileSync(file);
  return { bytes: buf.length, sha256: crypto.createHash('sha256').update(buf).digest('hex'), text: buf.toString('utf8') };
}
function scriptSources(html) {
  return Array.from(html.matchAll(/<script\s+src="([^"]+)"[^>]*><\/script>/g)).map((m) => m[1]);
}
function stylesheetSources(html) {
  return Array.from(html.matchAll(/<link[^>]+href="([^"]+\.css)"[^>]*>/g)).map((m) => m[1]);
}

let JSDOM = null;
function jsdomClass() {
  if (!JSDOM) {
    try { ({ JSDOM } = require('jsdom')); }
    catch (err) { throw new Error('jsdom is required (NODE_PATH=H:/sotto/node_modules): ' + (err && err.message)); }
  }
  return JSDOM;
}

/** The shell's preload bridge, with the channels the panel actually subscribes to. */
function bridgeStub(window, options) {
  const opts = options || {};
  const subs = { caption: [], status: [], stats: [] };
  const bridge = {
    onCaption: (cb) => subs.caption.push(cb),
    onStatus: (cb) => subs.status.push(cb),
    onStats: (cb) => subs.stats.push(cb),
    onGeometry: () => {},
    hide: () => {}, toggle: () => {}, quit: () => {},
    setPointerInteractive: () => {},
    captionApplied: () => {}, statusApplied: () => {}, ready: () => {}, clearApplied: () => {},
    getInfo: () => Promise.resolve({ hotkey: 'Alt+C', versions: { shell: 'language-oracle' } }),
    HOTKEY: 'Alt+C', platform: 'win32',
    history: {
      append: () => Promise.resolve({ entry: null }),
      tail: () => Promise.resolve({ entries: [], root: 'H:\\sotto\\history', canonicalProducer: 'redux' }),
      search: () => Promise.resolve({ hits: [] }),
      root: () => Promise.resolve({ root: 'H:\\sotto\\history', canonicalProducer: 'redux' }),
      reveal: () => {},
    },
    revive: () => Promise.resolve({ revived: true }),
    pause: () => Promise.resolve({ paused: true }),
    setTransparency: () => {},
    setPanelSurface: () => Promise.resolve({ surface: 'strip' }),
    setTranslationTarget: () => {},
    setLiveEnabled: (on) => {
      window.document.documentElement.setAttribute('data-caption-window', on ? 'on' : 'off');
      return Promise.resolve({ liveEnabled: Boolean(on) });
    },
    __emit: (kind, payload) => { for (const cb of subs[kind] || []) cb(payload); },
  };
  if (opts.wired !== false) window.sotto = bridge;
  return bridge;
}

/** One real page. `overrides['panel.js']` lets a mutant carry its own bytes. */
async function buildPanel(dir, overrides, options) {
  const htmlPath = path.join(dir, 'panel.html');
  const html = fs.readFileSync(htmlPath, 'utf8');
  const dom = new (jsdomClass())(html, {
    url: 'file:///' + htmlPath.replace(/\\/g, '/'),
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  const window = dom.window;
  for (const href of stylesheetSources(html)) {
    const file = path.resolve(dir, href);
    if (!fs.existsSync(file)) continue;
    const style = window.document.createElement('style');
    style.textContent = fs.readFileSync(file, 'utf8');
    window.document.head.appendChild(style);
  }
  const bridge = bridgeStub(window, options);
  const errors = [];
  for (const src of scriptSources(html)) {
    const file = path.resolve(dir, src);
    if (!fs.existsSync(file)) { errors.push('missing ' + src); continue; }
    let source = fs.readFileSync(file, 'utf8');
    if (src === 'panel.js' && overrides && Object.prototype.hasOwnProperty.call(overrides, src)) source = overrides[src];
    try { window.eval(source); } catch (err) { errors.push(src + ': ' + (err && err.message)); }
  }
  window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true }));
  /* The history root/tail promises are callbacks, not synchronous writes. */
  await new Promise((resolve) => setTimeout(resolve, 0));
  return { dom, window, document: window.document, bridge, errors: errors.filter((e) => /^panel\.js:/.test(e)) };
}

// ---------------------------------------------------------------------------
// THE DETECTOR
// ---------------------------------------------------------------------------
const ALLOW_EXACT = new Set([
  // owner-ordered vocabulary, pinned by `_main/panel-header-oracle.js` arm 9
  'ready', 'not ready',
]);
const EN_WORDS = new Set(('the is are was were be been being click press first this that with without '
  + 'not on off live caption captions engine engines transcript shell audio error errors starting '
  + 'started working paused pause resume restart restarting pipeline unavailable folder open opens '
  + 'show select selected line lines dropped behind missing impossible yet here nothing written '
  + 'refused failed failure turn bring back screen until unload unloaded reload reloads cannot '
  + 'does did from into under over by for of to in may will can you your').split(/\s+/));
const EN_HEADS = new Set(('open show select pause resume restart restarting paused error live working '
  + 'starting behind nothing the this click press already caption captions transcript history '
  + 'preload window export search panel').split(/\s+/));
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'HEAD', 'NOSCRIPT', 'TEMPLATE', 'OPTION']);
function tokens(text) { return String(text).toLowerCase().match(/[a-zà-ÿ]+/g) || []; }
function isEnglish(text) {
  const s = String(text).trim();
  if (!s || ALLOW_EXACT.has(s)) return false;
  if (/^[\d\s\W]+$/.test(s)) return false;
  const words = tokens(s);
  if (!words.length) return false;
  const en = [...new Set(words.filter((w) => EN_WORDS.has(w)))];
  if (en.length >= 2) return true;
  if (en.length === 1 && EN_HEADS.has(words[0])) return true;
  return words.length >= 2 && !words.some((w) => PT_WORDS.has(w));
}
function notHidden(el) {
  let n = el;
  while (n && n.nodeType === 1) {
    if (n.hidden === true) return false;
    if (n.classList && n.classList.contains('status__text--offscreen')) return false;
    n = n.parentNode;
  }
  return true;
}
const PT_WORDS = new Set(('de da do das dos a o as os e em para por com sem na no nas nos ao atrasado '
  + 'ainda clique pressione está estão será serão não nada até que este esta esses essas neste '
  + 'nao ligada ligado desligada desligado motores legenda legendas transcrição painel reiniciar '
  + 'reiniciando pausar pausado retomar descarregar descarregados carregar recarregar falha falhou '
  + 'recusou indisponível abrir aberta primeira linha tela áudio motore cancelar continuar '
  + 'transcrevendo transcrição próxima todas temas tema legendas').split(/\s+/));
function paintedStrings(doc) {
  const out = [];
  for (const el of doc.querySelectorAll('*')) {
    if (SKIP_TAGS.has(el.tagName) || !notHidden(el)) continue;
    const where = '#' + (el.id || el.className || el.tagName.toLowerCase());
    for (const attr of ['title', 'aria-label', 'placeholder', 'alt']) {
      const v = el.getAttribute && el.getAttribute(attr);
      if (v && v.trim()) out.push({ where: where + '@' + attr, text: v.trim() });
    }
    for (const node of el.childNodes) {
      if (node.nodeType === 3 && node.data.trim()) out.push({ where: where + '@text', text: node.data.trim() });
    }
  }
  return out;
}
function judge(p) {
  const bad = paintedStrings(p.document).filter((s) => isEnglish(s.text));
  return {
    ok: bad.length === 0 && p.errors.length === 0,
    detail: (p.errors.length ? 'panel.js errors=' + JSON.stringify(p.errors) + ' ' : '')
      + (bad.length ? bad.length + ' English string(s): ' + bad.slice(0, 12)
        .map((s) => s.where + '=' + JSON.stringify(s.text)).join(' | ')
        : 'no English string painted'),
  };
}

// ---------------------------------------------------------------------------
// THE ARMS
// ---------------------------------------------------------------------------
async function drive(state, p) {
  const w = p.window;
  if (state === 'L2') return;
  if (state === 'L3') {
    w.document.documentElement.setAttribute('data-caption-window', 'on');
    await new Promise((resolve) => setTimeout(resolve, 0));
  } else if (state === 'L4') {
    w.document.documentElement.setAttribute('data-caption-window', 'off');
    await new Promise((resolve) => setTimeout(resolve, 0));
  } else if (state === 'L5') {
    /* A strict-mode top-level function is NOT a window property under
     * `window.eval`, so the state is driven through the real button, as the
     * owner does: the strip pause IS the confirm, and the bridge resolves it. */
    const btn = w.document.getElementById('strip-pause-button');
    if (!btn) throw new Error('no #strip-pause-button to pause');
    btn.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));
  } else if (state === 'L6') {
    p.bridge.__emit('status', { text: 'Falha no dispositivo de áudio', kind: 'error' });
    p.bridge.__emit('stats', { queue_drops: 5, rate: 0.42 });
    await new Promise((resolve) => setTimeout(resolve, 0));
  } else if (state === 'L7') {
    const status = w.document.getElementById('status');
    if (!status) throw new Error('no #status to revive');
    /* ONE click: the first paint writes the strip word `Reiniciando` AFTER
     * setStatus has written `Trabalhando`; a second click would overwrite it
     * again and hide the very writer the mutant reverts. */
    status.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}
const ARMS = [
  ['L1', 'startup with a wired bridge'],
  ['L2', 'startup with no preload bridge'],
  ['L3', 'live caption ON'],
  ['L4', 'live caption OFF'],
  ['L5', 'paused'],
  ['L6', 'error + backlog'],
  ['L7', 'revive tooltip'],
];
async function runArm(id, panelSource) {
  const overrides = panelSource === null ? null : { 'panel.js': panelSource };
  const options = { wired: id !== 'L2' };
  let p;
  try { p = await buildPanel(PANEL, overrides, options); await drive(id, p); }
  catch (err) { return { ok: false, detail: 'THREW ' + (err && err.name) + ': ' + (err && err.message) }; }
  return judge(p);
}

// ---------------------------------------------------------------------------
// THE NEG-ARM -- one writer reverted to the English bytes it replaced.
// ---------------------------------------------------------------------------
const MUTANTS = [
  { id: 'M1 no-bridge status back to English', mustRed: ['L2'], mustGreen: ['L1', 'L3', 'L4', 'L5', 'L6', 'L7'],
    from: "dom.statusText.textContent = 'Ponte de preload ausente · legendas impossíveis'",
    to: "dom.statusText.textContent = 'Preload bridge missing · captions are impossible'" },
  { id: 'M2 live-ON lamp back to English', mustRed: ['L3'], mustGreen: ['L1', 'L2', 'L4', 'L5', 'L6', 'L7'],
    from: "'Legenda ao vivo: LIGADA · o motor ao vivo está ligado.'",
    to: "'Live caption: ON · the live engine is on.'" },
  { id: 'M3 live-OFF lamp back to English', mustRed: ['L4'], mustGreen: ['L2', 'L3'],
    from: "'Legenda ao vivo: DESLIGADA · pressione Alt+C para ligar.'",
    to: "'Live caption: OFF · press Alt+C to turn it on.'" },
  { id: 'M4 the strip live label back to LIVE', mustRed: ['L3', 'L4'], mustGreen: ['L2'],
    from: "dom.stripLiveLabel.textContent = 'ao vivo'",
    to: "dom.stripLiveLabel.textContent = 'LIVE'" },
  { id: 'M5 the paused word back to English', mustRed: ['L5'], mustGreen: ['L1', 'L2', 'L3', 'L4', 'L6', 'L7'],
    from: "word = 'Pausado'", to: "word = 'Paused'" },
  { id: 'M6 the backlog chip back to English', mustRed: ['L6'], mustGreen: ['L1', 'L2', 'L3', 'L4', 'L5', 'L7'],
    from: '`atrasado · ${bits.join(', to: '`behind · ${bits.join(' },
  { id: 'M7 the revive word back to English', mustRed: ['L7'], mustGreen: ['L1', 'L2', 'L3', 'L4', 'L5', 'L6'],
    from: "dom.stripWord.textContent = 'Reiniciando'", to: "dom.stripWord.textContent = 'Restarting'" },
];

async function main() {
  say('panel-language-oracle — real panel.html + real panel.js in jsdom, no window');
  const rev = revision(path.join(PANEL, 'panel.js'));
  const htmlRev = revision(path.join(PANEL, 'panel.html'));
  say('  panel.js   ' + rev.bytes + ' B  sha256 ' + rev.sha256);
  say('  panel.html ' + htmlRev.bytes + ' B  sha256 ' + htmlRev.sha256);
  const parsed = require('node:child_process').spawnSync(process.execPath, ['--check', path.join(PANEL, 'panel.js')], { encoding: 'utf8' });
  say('  node --check app/panel/panel.js -> rc=' + parsed.status);
  if (parsed.status !== 0) { say('VERDICT: FAIL'); process.exit(1); }

  const shipped = {};
  say('');
  say('--- AS SHIPPED ---');
  for (const [id, title] of ARMS) {
    shipped[id] = await runArm(id, null);
    say('  ' + (shipped[id].ok ? 'GREEN' : 'RED  ') + ' ' + id + '  ' + title);
    say('        ' + shipped[id].detail);
  }
  const allGreen = ARMS.every(([id]) => shipped[id].ok);
  say('');
  say('AS-SHIPPED COLOURS: ' + ARMS.map(([id]) => id + '=' + (shipped[id].ok ? 'GREEN' : 'RED')).join(' '));
  if (!NEG) { say(''); say('VERDICT: ' + (allGreen ? 'PASS' : 'FAIL')); process.exit(allGreen ? 0 : 1); }

  say('');
  say('--- NEG-ARM: one English writer restored per mutant ---');
  let selective = true;
  for (const m of MUTANTS) {
    const hits = rev.text.split(m.from).length - 1;
    if (hits !== 1) { say('SETUP ERROR: anchor of ' + m.id + ' appears ' + hits + ' times'); process.exit(2); }
    const mutated = rev.text.replace(m.from, m.to);
    if (mutated === rev.text) { say('SETUP ERROR: mutant ' + m.id + ' changed nothing'); process.exit(2); }
    const colours = {};
    for (const [id] of ARMS) colours[id] = (await runArm(id, mutated)).ok;
    const red = m.mustRed.filter((id) => !colours[id]);
    const leaked = m.mustGreen.filter((id) => !colours[id]);
    const ok = red.length === m.mustRed.length && leaked.length === 0;
    if (!ok) selective = false;
    say('  ' + (ok ? 'OK  ' : 'BAD ') + ' ' + m.id + '  red=' + (red.join(',') || 'NONE')
      + '  leaked=' + (leaked.join(',') || 'none'));
  }
  say('');
  say('NEG-ARM VERDICT: ' + (selective ? 'PASS -- every mutant reddened its own arm(s) only' : 'FAIL -- a mutant was blind or leaked'));
  say('VERDICT: ' + (allGreen && selective ? 'PASS' : 'FAIL'));
  /* House convention (botoes-lane-oracle.js:366-376): a negative arm that CATCHES
   * every mutant exits 1 BY DESIGN; a surviving mutant exits 0. */
  process.exit(allGreen && selective ? 1 : 0);
}

if (require.main === module) {
  main().catch((err) => { say('SETUP ERROR: ' + (err && err.stack || err)); process.exit(2); });
}

/* Reused by `_main/botoes-lane-oracle.js` B3: the LIVE label the PAGE actually
 * paints, not the static HTML bytes. */
async function runtimeLiveLabel(dir) {
  try {
    const p = await buildPanel(dir, null, { wired: true });
    const el = p.document.getElementById('strip-live-label');
    return el ? el.textContent : 'ABSENT';
  } catch (err) {
    return 'JSDOM ERROR: ' + (err && err.message);
  }
}
module.exports = { buildPanel, runtimeLiveLabel, paintedStrings, isEnglish };
