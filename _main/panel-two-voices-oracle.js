/* panel-two-voices-oracle.js -- DOES THE PANEL ACTUALLY GIVE EACH PERSON A LINE?
 *
 * OWNER, 2026-10-18, verbatim:
 *   "e mostra pra mim ... o parakeet processando os audios do discord meu e dos
 *    meus amigos. de forma natural, encaixa no sotto"
 *
 * THE GAP THIS CLOSES, in the previous receipt's own words: "o que o PAINEL
 * mostra com duas fontes -- NAO VISTO". Everything upstream of the panel was
 * proven: the worker stamps one `source` per voice, and the two upstream oracles
 * say so with 70/70 and 20/20. But a claim about what the panel DOES with two
 * sources, made without ever showing the panel two sources, is a claim and not
 * a measurement.
 *
 * So this runs the real `app/panel/` -- the real `panel.html`, the real CSS, the
 * real eleven scripts in document order -- under JSDOM, and feeds it captions
 * from TWO DIFFERENT `source` values. No window, no WebView2, no audio, no
 * network, no model, nothing launched. Seconds, not minutes.
 *
 * WHAT IS ACTUALLY BEING TESTED, and it is a property the panel PROMISES in its
 * own comments (`panel.js:449-451`):
 *
 *   "the panel never feeds a fragment to another source's engine"
 *
 * Two people talking over each other is the normal case in a call, and if the
 * panel collapsed both voices into one row the transcript would read as one
 * person switching subject mid-sentence, with no way to tell it from that.
 *
 * THE ARMS:
 *   two sources        two provisional rows, not one
 *   the identity       each row carries its own `data-source`
 *   no interleaving    each row shows ITS OWN words
 *   independence       updating voice A does not touch voice B's row
 *   one source         still ONE row -- the common case is unchanged
 *   no source          still ONE row with NO data-source, i.e. byte-identical
 *                      to the day before sources existed
 *
 * THE NEGATIVE ARM re-runs the identical checks against two broken copies of
 * the panel. Both mutants are the mistake a careless edit would make: throw the
 * source key away, or stop stamping it on the row.
 *
 *   node _main/panel-two-voices-oracle.js             expect VERDICT: PASS, rc=0
 *   node _main/panel-two-voices-oracle.js --neg-arm   expect every mutant RED
 */
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (err) {
  console.log('SETUP ERROR: jsdom is required (' + (err && err.message) + ').');
  process.exit(2);
}

const REPO = path.join(__dirname, '..');
const PANEL = path.join(REPO, 'app', 'panel');
const NEG = process.argv.indexOf('--neg-arm') >= 0;

const DEVICE = 'device:CABLE Output (VB-Audio Virtual Cable)';
const VOICE_A = DEVICE + '/voice:speaker-1';
const VOICE_B = DEVICE + '/voice:speaker-2';

let arm = '';
const rows = [];

function check(name, real, want) {
  const good = JSON.stringify(real) === JSON.stringify(want);
  rows.push({ arm, name, ok: good, real, want });
  console.log('  [' + (good ? 'PASS' : 'FAIL') + '] ' + name);
  if (!good) {
    console.log('         real = ' + JSON.stringify(real));
    console.log('        want = ' + JSON.stringify(want));
  }
  return good;
}

function scriptSources(html) {
  return Array.from(html.matchAll(/<script\s+src="([^"]+)"[^>]*><\/script>/g)).map(function (m) { return m[1]; });
}

/* The bridge the real shell provides. Only `onCaption` and the private emitter
 * matter here; the history calls answer with nothing because these checks read
 * the LIVE caption list and never touch the transcript. */
function bridgeStub(window) {
  const subs = { caption: [], status: [] };
  const bridge = {
    onCaption: function (cb) { subs.caption.push(cb); },
    onStatus: function (cb) { subs.status.push(cb); },
    onGeometry: function () {},
    hide: function () {}, toggle: function () {}, quit: function () {},
    setPointerInteractive: function () {},
    captionApplied: function () {}, statusApplied: function () {}, ready: function () {},
    clearApplied: function () {},
    getInfo: function () { return Promise.resolve({ hotkey: 'Alt+C', versions: { shell: 'two-voices-oracle' } }); },
    HOTKEY: 'Alt+C',
    platform: 'win32',
    history: {
      append: function () { return Promise.resolve({ entry: null }); },
      tail: function () { return Promise.resolve({ entries: [], root: 'H:/sotto/history', canonicalProducer: 'redux' }); },
      search: function () { return Promise.resolve({ hits: [] }); },
      root: function () { return Promise.resolve({ root: 'H:/sotto/history', canonicalProducer: 'redux' }); },
      reveal: function () {},
    },
    setLiveEnabled: function () { return Promise.resolve({ liveEnabled: false }); },
    pause: function () { return Promise.resolve({ paused: false }); },
    setPanelSurface: function () { return Promise.resolve({ surface: 'panel' }); },
    __emit: function (kind, payload) { for (const cb of subs[kind] || []) cb(payload); },
  };
  window.sotto = bridge;
  return bridge;
}

function buildPanel(dir) {
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
  const bridge = bridgeStub(window);
  const errors = [];
  for (const src of scriptSources(html)) {
    const file = path.resolve(dir, src);
    if (!fs.existsSync(file)) { errors.push('missing ' + src); continue; }
    try { window.eval(fs.readFileSync(file, 'utf8')); } catch (err) { errors.push(src + ': ' + (err && err.message)); }
  }
  try { window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true })); }
  catch (err) { errors.push('DOMContentLoaded: ' + (err && err.message)); }
  const list = window.document.querySelector('#caption-list')
    || window.document.querySelector('#captions')
    || window.document.querySelector('[data-caption-list]');
  return { window, document: window.document, bridge, errors, list };
}

/* A caption as the BRIDGE delivers it, which is NOT the worker's own dict.
 *
 * MEASURED, after a first draft of this file fed `panel.js` the worker's event
 * shape directly and measured ZERO rows. `panel.js:985` reads
 * `bridge.onCaption(({ text, meta }) => ...)` and takes the engine key from
 * `meta.source` (`panel.js:993`), not from the event's top level. Feeding the
 * flat shape would have measured a panel being handed something the shell never
 * sends -- and would have "proved" that two voices do not get two lines.
 *
 * The `meta` keys below are the ones `LineFormer._event` stamps on a sourced
 * live event, so what arrives here is what the worker really emits. */
function captionEvent(source, text, start, end, final) {
  const meta = {
    start: start,
    end: end,
    chunk_start: end,
    chunks: [[start, end, text]],
    final: Boolean(final),
    closed: Boolean(final),
  };
  if (source !== null && source !== undefined) meta.source = source;
  return { text: text, meta: meta };
}

function provisionalRows(list) {
  if (!list) return [];
  return Array.from(list.querySelectorAll('li[data-source]'));
}

/* Lift one function out of the SHIPPED file by brace matching, so an arm tests
 * the code that ships rather than a copy of it written out here. The technique
 * is the one `_main/caption-independent-oracle.js` already uses. */
function functionSource(text, name) {
  const at = text.indexOf('function ' + name + '(');
  if (at < 0) return null;
  let i = text.indexOf('{', at);
  let depth = 0;
  for (; i < text.length; i += 1) {
    if (text[i] === '{') depth += 1;
    else if (text[i] === '}') { depth -= 1; if (depth === 0) return text.slice(at, i + 1); }
  }
  return null;
}

function rowText(row) {
  /* The row paints a timestamp and a typing caret around the words. Both are
   * decoration and both belong to the panel, not to the text being attributed,
   * so they are stripped before comparing -- otherwise every check fails for a
   * reason that has nothing to do with speakers. The clock is NOT compared:
   * two rows rendered in the same millisecond is the normal case and means
   * nothing either way. */
  if (!row) return null;
  return row.textContent
    .replace(/\s+/g, ' ')
    .replace(/^\d{2}:\d{2}:\d{2}/, '')
    .replace(/[\u2588-\u258F\u25AE]/g, '')
    .trim();
}

function runChecks(dir) {
  const p = buildPanel(dir);
  const list = p.list;
  const emit = p.bridge.__emit;

  arm = 'SETUP';
  check('every script ran without throwing', p.errors, []);
  check('the caption list is in the document', Boolean(list), true);

  /* --- two voices, interleaved, the way a call actually sounds ---------- */
  arm = 'TWO VOICES';
  emit('caption', captionEvent(VOICE_A, 'e eu quero que o alt c', 0.0, 0.8, false));
  emit('caption', captionEvent(VOICE_B, 'e ai pessoal tudo bem', 0.0, 0.9, false));
  let rowsNow = provisionalRows(list);
  check('two voices -> TWO provisional rows', rowsNow.length, 2);
  check('each row carries its own source',
    rowsNow.map(function (r) { return r.dataset.source; }).sort(),
    [VOICE_A, VOICE_B].sort());
  check('each row shows ITS OWN words -- no interleaving',
    rowsNow.map(rowText).sort(),
    ['e ai pessoal tudo bem', 'e eu quero que o alt c'].sort());

  /* --- one voice keeps talking: the other must not move ----------------- */
  arm = 'INDEPENDENCE';
  const bBefore = rowText(rowsNow.filter(function (r) { return r.dataset.source === VOICE_B; })[0]);
  emit('caption', captionEvent(VOICE_A, 'e eu quero que o alt c mostre as transcricoes', 0.0, 1.8, false));
  rowsNow = provisionalRows(list);
  check('still two rows after voice A grows', rowsNow.length, 2);
  check("voice B's row did not change",
    rowText(rowsNow.filter(function (r) { return r.dataset.source === VOICE_B; })[0]),
    bBefore);
  check("voice A's row did grow",
    rowText(rowsNow.filter(function (r) { return r.dataset.source === VOICE_A; })[0]),
    'e eu quero que o alt c mostre as transcricoes');

  /* --- the common case: ONE source is still ONE row --------------------- */
  arm = 'ONE VOICE';
  const solo = buildPanel(dir);
  solo.bridge.__emit('caption', captionEvent(DEVICE, 'uma linha so', 0.0, 0.6, false));
  solo.bridge.__emit('caption', captionEvent(DEVICE, 'uma linha so e meia', 0.0, 1.2, false));
  const soloRows = provisionalRows(solo.list);
  check('one source -> ONE row', soloRows.length, 1);
  check('and it holds the latest text', rowText(soloRows[0]), 'uma linha so e meia');

  /* --- no source at all: the DOM must be what it always was -------------- */
  arm = 'NO SOURCE';
  const bare = buildPanel(dir);
  bare.bridge.__emit('caption', captionEvent(null, 'sem fonte nenhuma', 0.0, 0.6, false));
  const bareRows = provisionalRows(bare.list);
  check('no source -> no row is stamped as sourced', bareRows.length, 0);
  const anyLi = bare.list ? bare.list.querySelectorAll('li.caption--provisional').length : 0;
  check('no source -> the row still paints, unstamped', anyLi, 1);

  /* --- the COMMITTED row key, tested as the function it is ---------------- */
  /* NOT PROVEN END-TO-END, and the receipt says so.
   *
   * Two attempts to drive a real commit under JSDOM both produced rows with no
   * `data-start`, which means no `addCaption` ran and what was being counted
   * were PROVISIONAL rows again -- the very thing already proven above. A third
   * attempt found why: `meta.final` does not commit, it only records the
   * worker's vote (`caption-formulation.js:901`), and the panel closes a line
   * on a status change (`panel.js:3010`). Getting a genuine commit out of this
   * harness needs more scaffolding than the property is worth.
   *
   * What IS proven here is the key itself, lifted out of the LIVE `panel.js` by
   * brace matching and run over real values. That is the whole mechanism:
   * `addCaption` calls `rowIdentity(source, start)` and reuses the row it
   * returns, so two voices are kept apart exactly when their identities differ
   * -- and a per-voice `source` makes them differ MORE than the single shared
   * device source did. The change cannot merge two people who were not already
   * merged; it can only stop them colliding. */
  arm = 'ROW KEY';
  const panelSrc = fs.readFileSync(path.join(dir, 'panel.js'), 'utf8');
  const rowIdentitySrc = functionSource(panelSrc, 'rowIdentity');
  check('the committed-row key was found in the panel', Boolean(rowIdentitySrc), true);
  if (rowIdentitySrc) {
    const rowIdentity = new Function('return (' + rowIdentitySrc + ')')();
    const keyA = rowIdentity(VOICE_A, 12.0);
    const keyB = rowIdentity(VOICE_B, 12.0);
    const keyA2 = rowIdentity(VOICE_A, 12.0);
    check('two voices at the SAME audio second get DIFFERENT keys',
      keyA !== keyB, true);
    check('...and the keys really do carry the source',
      // `String()` on purpose: a mutant that drops the source returns a NUMBER,
      // and calling `.indexOf` on it crashed the whole oracle instead of
      // reporting RED -- which loses every later arm as collateral.
      [String(keyA).indexOf(VOICE_A) >= 0, String(keyB).indexOf(VOICE_B) >= 0],
      [true, true]);
    check('the same voice at the same second gets the SAME key -- replace, '
      + 'not duplicate', keyA === keyA2, true);
    check('a different second is a different key',
      rowIdentity(VOICE_A, 13.0) !== keyA, true);
    check('no source at all is still keyed by the second',
      rowIdentity(null, 12.0), 12.0);
    check('no start at all has no identity, and the caller appends',
      rowIdentity(VOICE_A, null), null);
  }

  return rows;
}

/* ARRAY LITERALS, NOT PARENTHESES. A first draft wrote these as
 * `(label, old, new)` inside the array, which in JavaScript is the COMMA
 * OPERATOR: `MUTANTS` came out flat, and the destructure below pulled
 * `label='c', old='o', new='n'` out of a string. Every mutant then rewrote the
 * whole panel, replacing the letter `o` with `n`, and went red for the wrong
 * reason -- a negative arm that "catches" a mutant by destroying the file is
 * decoration, and it would have hidden a genuinely blind gate. */
const MUTANTS = [
  ['the-source-key-is-thrown-away',
   'const key = source === null || source === undefined ? null : String(source);',
   'const key = null;'],
  ['the-row-stops-advertising-its-source',
   'if (key !== null && line.dataset) line.dataset.source = key;',
   'if (false && line.dataset) line.dataset.source = key;'],
  // The one that would merge two PEOPLE. `rowIdentity` is the only thing
  // keeping a per-voice `source` apart on the COMMITTED transcript, and two
  // speakers whose sentences begin in the same audio second are the ordinary
  // case in a call, not the exotic one. Key on `start` alone and the second
  // person silently replaces the first.
  ['the-committed-row-key-forgets-the-source',
   'return source === null || source === undefined ? start : String(source) + "\\u0000" + start;',
   'return start;'],
];

function copyPanel() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'two-voices-'));
  const dst = path.join(tmp, 'panel');
  fs.cpSync(PANEL, dst, { recursive: true });
  return { tmp, dst };
}

function main() {
  console.log('PANEL: TWO VOICES, ONE LINE EACH' + (NEG ? '  (negative arm)' : ''));
  runChecks(PANEL);

  if (NEG) {
    console.log('\nNEGATIVE ARM (broken panels must go RED)');
    const original = fs.readFileSync(path.join(PANEL, 'panel.js'), 'utf8');
    for (const [label, oldText, newText] of MUTANTS) {
      if (original.indexOf(oldText) < 0) {
        console.log('  [FAIL] mutant "' + label + '" ANCHOR MISSING -- the oracle is stale');
        rows.push({ arm: 'NEG', name: label, ok: false });
        continue;
      }
      const { tmp, dst } = copyPanel();
      fs.writeFileSync(path.join(dst, 'panel.js'), original.split(oldText).join(newText), 'utf8');
      const before = rows.length;
      const got = runChecks(dst);
      const mutantRows = got.slice(before);
      const reds = mutantRows.filter(function (r) { return !r.ok; }).map(function (r) { return r.name; });
      /* The mutant's checks are SUPPOSED to be red. Counting them in the global
       * tally made a negative arm that caught everything report FAIL, which is
       * backwards: the rows are rolled back and replaced by one verdict row. */
      rows.length = before;
      if (reds.length) {
        console.log('  [PASS] mutant "' + label + '" caught by: ' + reds.slice(0, 3).join('; '));
        rows.push({ arm: 'NEG', name: 'mutant: ' + label, ok: true });
      } else {
        console.log('  [FAIL] mutant "' + label + '" SURVIVED -- the gate is blind here');
        rows.push({ arm: 'NEG', name: 'mutant: ' + label, ok: false });
      }
      fs.rmSync(tmp, { recursive: true, force: true });
    }
  }

  const bad = rows.filter(function (r) { return !r.ok; });
  console.log('\n' + (rows.length - bad.length) + '/' + rows.length + ' checks green');
  console.log('VERDICT: ' + (bad.length ? 'FAIL' : 'PASS'));
  return bad.length ? 1 : 0;
}

process.exit(main());