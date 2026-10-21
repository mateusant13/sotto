/* panel-voice-dot-oracle.js -- IS THE VOICE ACTUALLY VISIBLE, AND DOES IT COST
 * ANYTHING WHEN THERE IS NO VOICE?
 *
 * THE GAP. Everything upstream was proven; the DISPLAY was not. The owner's own
 * words (2026-10-18) were "mostra pra mim ... de forma natural, encaixa no
 * sotto" -- and `panel.js` had exactly ONE occurrence of the word "speaker", a
 * status string. The per-voice `source` rode to the panel as `data-source` and
 * was never painted. Two people produced two rows and NOTHING said which was
 * which. A feature that cannot be seen is not finished.
 *
 * THE CONTRACT THIS GATE ENFORCES
 * -------------------------------
 *  1. NO VOICE -> NOTHING ADDED. A row with no voice gets no element, no
 *     attribute, and no CSS match. The DOM the owner sees today, byte for byte.
 *  2. TWO VOICES -> TWO DIFFERENT MARKS. Different `data-voice`, different hue.
 *  3. THE SAME VOICE -> THE SAME MARK, in every row, forever. This is the whole
 *     point: the colour is how a human reads "these two lines are one person".
 *  4. `source` IS AN OPAQUE KEY AND STAYS ONE. A device whose NAME contains
 *     "voice" gets no dot -- the match is anchored, not a substring test.
 *  5. THE DISPLAY IS NOT THE IDENTITY. `data-source` and `data-start` are what
 *     `rowIdentity` hashes, and the dot must not reach them.
 *
 * THE NEGATIVE ARM mutates `rowIdentity` itself so that the DISPLAY VALUE leaks
 * into the KEY -- the exact failure the opaque `source` exists to prevent: rename
 * a voice, and its lines jump to a different row. That mutant must go RED on the
 * identity arm. If it does not, this gate is not measuring the thing it claims.
 *
 *   node _main/panel-voice-dot-oracle.js             expect VERDICT: PASS, rc=0
 *   node _main/panel-voice-dot-oracle.js --neg-arm   expect every mutant RED
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
const V1 = DEVICE + '/voice:speaker-1';
const V2 = DEVICE + '/voice:speaker-2';

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

function bridgeStub(window) {
  const subs = { caption: [], status: [] };
  const bridge = {
    onCaption: function (cb) { subs.caption.push(cb); },
    onStatus: function (cb) { subs.status.push(cb); },
    onGeometry: function () {}, hide: function () {}, toggle: function () {}, quit: function () {},
    setPointerInteractive: function () {},
    captionApplied: function () {}, statusApplied: function () {}, ready: function () {},
    clearApplied: function () {},
    getInfo: function () { return Promise.resolve({ hotkey: 'Alt+C', versions: { shell: 'voice-dot-oracle' } }); },
    HOTKEY: 'Alt+C', platform: 'win32',
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
  const list = window.document.querySelector('#caption-list')
    || window.document.querySelector('#captions')
    || window.document.querySelector('[data-caption-list]');
  return { window, document: window.document, bridge, errors, list };
}

/* The SAME event shape `_main/panel-two-voices-oracle.js` emits. Measured the
 * hard way in this repo: feeding the panel `{type: ...}` instead of
 * `{text, meta}` produces zero rows, and feeding `meta.final` alone does NOT
 * commit a line -- it only records it. The commit needs `closed` as well. A
 * caption oracle that invents its own event shape tests nothing. */
function captionEvent(source, text, start, end, final) {
  return {
    text: text,
    meta: {
      source: source,
      start: start,
      chunk_start: end,
      final: Boolean(final),
      closed: Boolean(final),
      producer: 'redux',
    },
  };
}

function emit(panel, text, meta) {
  panel.bridge.__emit('caption', { text: text, meta: meta });
}

function committedRows(panel) {
  return Array.from(panel.list.querySelectorAll('li'));
}

function dotOf(row) {
  const d = row.querySelector('.caption__voice');
  return d ? d.style.getPropertyValue('--voice-hue') : null;
}

function hueOf(panel, row) {
  void panel;
  return row.querySelector('.caption__voice') ? dotOf(row) : null;
}

/* A fresh copy of the panel directory, with one string replaced. The mutant is
 * the DISPLAY LEAKING INTO THE KEY -- the failure mode the opaque `source`
 * exists to make impossible. */
function makeMutant(label, from, to) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sotto-voice-' + label + '-'));
  for (const f of fs.readdirSync(PANEL)) {
    const src = path.join(PANEL, f);
    if (fs.statSync(src).isDirectory()) continue;
    if (!/\.(js|css|html)$/.test(f)) continue;
    fs.copyFileSync(src, path.join(dir, f));
  }
  const p = path.join(dir, 'panel.js');
  const text = fs.readFileSync(p, 'utf8');
  if (text.indexOf(from) < 0) throw new Error('mutant anchor not found: ' + label);
  fs.writeFileSync(p, text.split(from).join(to), 'utf8');
  return dir;
}

function runReal(label, dir) {
  const panel = buildPanel(dir);
  if (panel.errors.length) console.log('  (script errors: ' + panel.errors.join(' | ') + ')');

  // --- ARM: no voice at all -- THE COMMON CASE, and it must cost nothing -----
  arm = label + ' / no voice';
  panel.bridge.__emit('caption', captionEvent(null, 'linha sem voz nenhuma', 1.0, 1.4, false));
  panel.bridge.__emit('caption', captionEvent(null, 'linha sem voz nenhuma', 2.0, 2.6, true));
  const plain = committedRows(panel).filter(function (r) { return !r.dataset.source; });
  check('a linha sem voz nao ganha elemento nenhum',
    plain.map(function (r) { return r.querySelectorAll('.caption__voice').length; }), [0]);
  check('a linha sem voz nao ganha data-voice',
    plain.map(function (r) { return r.dataset.voice === undefined ? null : r.dataset.voice; }), [null]);
  check('a linha sem voz fica byte-identica: sem elemento, sem atributo',
    plain.map(function (r) {
      return r.outerHTML.indexOf('caption__voice') < 0
          && r.outerHTML.indexOf('data-voice') < 0;
    }), [true]);

  // --- ARM: two voices, two marks -------------------------------------------
  arm = label + ' / two voices';
  panel.bridge.__emit('caption', captionEvent(V1, 'a ana disse', 10.0, 10.4, false));
  panel.bridge.__emit('caption', captionEvent(V1, 'a ana disse mais', 10.0, 10.9, true));
  panel.bridge.__emit('caption', captionEvent(V2, 'o bruno disse', 11.0, 11.4, false));
  panel.bridge.__emit('caption', captionEvent(V2, 'o bruno disse mais', 11.0, 11.9, true));
  const withVoice = committedRows(panel).filter(function (r) { return r.dataset.voice; });
  check('duas vozes, duas linhas marcadas', withVoice.length, 2);
  check('cada linha carrega a SUA voz',
    withVoice.map(function (r) { return r.dataset.voice; }).sort(), ['speaker-1', 'speaker-2']);
  const hues = withVoice.map(function (r) { return hueOf(panel, r); });
  check('as duas cores sao diferentes', hues[0] !== hues[1], true);

  // --- ARM: the same voice keeps its mark, in EVERY row ----------------------
  arm = label + ' / same voice twice';
  panel.bridge.__emit('caption', captionEvent(V1, 'outra frase da mesma pessoa', 20.0, 20.4, false));
  panel.bridge.__emit('caption', captionEvent(V1, 'outra frase da mesma pessoa', 20.0, 20.9, true));
  const v1rows = committedRows(panel).filter(function (r) { return r.dataset.voice === 'speaker-1'; });
  const v1hues = v1rows.map(function (r) { return hueOf(panel, r); });
  check('a mesma voz tem UM tom so, em todas as linhas',
    new Set(v1hues).size, 1);
  check('e conserva o tom que ela ja tinha na linha anterior',
    v1hues[v1hues.length - 1], v1hues[0]);

  // --- ARM: a device whose NAME contains "voice" is not a voice --------------
  arm = label + ' / not a voice';
  panel.bridge.__emit('caption', captionEvent('device:voice of my heart', ' microfone voice da mesa', 30.0, 30.4, false));
  panel.bridge.__emit('caption', captionEvent('device:voice of my heart', ' microfone voice da mesa', 30.0, 30.9, true));
  const fake = committedRows(panel).filter(function (r) { return r.dataset.source === 'device:voice of my heart'; });
  check('um device chamado "voice" NAO ganha ponto',
    fake.map(function (r) { return r.querySelectorAll('.caption__voice').length; }), [0]);
  check('e nao ganha data-voice',
    fake.map(function (r) { return r.dataset.voice === undefined ? null : r.dataset.voice; }), [null]);

  // --- ARM: the KEY is untouched by the display -----------------------------
  arm = label + ' / identity';
  check('data-source continua a ser a chave opaca',
    withVoice.map(function (r) { return r.dataset.source; }).sort(), [V1, V2]);
  /* MEASURED, and this is why the arm does NOT assert data-start: these rows
   * are PROVISIONAL -- the same state _main/panel-two-voices-oracle.js drives,
   * and the state the owner is looking at while a sentence forms. A provisional
   * row carries NO data-start; it is stamped on commit. The first version of
   * this arm asserted "10" / "11", went RED, and had nothing to do with the
   * dot. An arm that fails for the wrong reason is how a real defect gets waved
   * through as "flaky". */
  check('a linha provisional nao ganha data-start por causa do ponto',
    withVoice.map(function (r) { return r.dataset.start === undefined; }), [true, true]);
  const keys = withVoice.map(function (r) {
    return r.dataset.source + ' ' + r.dataset.start;
  });
  check('duas linhas nunca colidem na chave', new Set(keys).size, keys.length);

  // --- ARM: the same voice number on TWO devices must stay two rows ---------
  /* This is the arm that gives the negative arm something to bite on. A key
   * built only from the voice number would make these two lines collide, and
   * that is not a hypothetical mistake: the whole reason `source` is
   * `<device>/voice:speaker-<n>` is that the device half keeps two apps apart.
   * A mutant that keys on the voice number alone is RED here and nowhere else. */
  arm = label + ' / two devices, one voice number';
  panel.bridge.__emit('caption', captionEvent('device:discord/voice:speaker-1', 'no discord', 40.0, 40.4, false));
  panel.bridge.__emit('caption', captionEvent('device:youtube/voice:speaker-1', 'no youtube', 40.0, 40.4, false));
  const twoDev = committedRows(panel).filter(function (r) {
    return r.dataset.voice === 'speaker-1'
        && (r.dataset.source === 'device:discord/voice:speaker-1'
            || r.dataset.source === 'device:youtube/voice:speaker-1');
  });
  check('o mesmo numero de voz em DOIS dispositivos sao DUAS linhas', twoDev.length, 2);
  check('e cada uma guarda o seu dispositivo',
    twoDev.map(function (r) { return r.dataset.source; }).sort(),
    ['device:discord/voice:speaker-1', 'device:youtube/voice:speaker-1']);

  /* AND NOW THE COMMIT PATH, which is where `rowIdentity` actually runs.
   * MEASURED: with only provisional captions, the `voice-number-only` mutant
   * stayed GREEN through 30 arms -- provisional rows are keyed by the
   * `provisionalRows` Map on the raw `source`, never by `rowIdentity`, so a
   * broken key cannot show up there at all. A status change flushes every
   * engine (`panel.js:3076`) and that is what commits a line; so the same two
   * captions are emitted once more and then CLOSED, and the assertion is made
   * against committed rows where the key is the thing under test. */
  arm = label + ' / committed, two devices';
  panel.bridge.__emit('caption', captionEvent('device:discord/voice:speaker-1', 'no discord outra vez', 50.0, 50.4, false));
  panel.bridge.__emit('caption', captionEvent('device:youtube/voice:speaker-1', 'no youtube outra vez', 50.0, 50.4, false));
  panel.bridge.__emit('status', { text: 'a ouvir', kind: 'info' });
  const committedTwo = committedRows(panel).filter(function (r) {
    return (r.dataset.source === 'device:discord/voice:speaker-1'
            || r.dataset.source === 'device:youtube/voice:speaker-1')
        && !r.classList.contains('caption--provisional');
  });
  check('DEPOIS DE COMMITAR, o mesmo numero em dois dispositivos continua a ser DUAS linhas',
    committedTwo.length, 2);
  check('e o ponto de voz sobrevive ao commit',
    committedTwo.map(function (r) { return r.dataset.voice; }), ['speaker-1', 'speaker-1']);
  check('as duas linhas commitadas partilham o MESMO start -- e mesmo assim nao colidem',
    new Set(committedTwo.map(function (r) { return r.dataset.start; })).size, 1);

  return panel;
}

const dirs = [];
try {
  arm = 'real';
  runReal('real', PANEL);

  if (NEG) {
    arm = 'mutant';
    // THE FAITHFUL MUTANT: the key forgets the DEVICE half of source and
    // keeps only the voice number. That is the mistake source exists to
    // prevent -- and it is observable: two lines from two apps carrying the same
    // speaker-1 collapse into one row. The first mutant leaked the display
    // HUE into the key, which changed nothing measurable: every row already had
    // a unique source, so adding one more unique term to the key is a no-op.
    // A mutant that cannot change an outcome is not a mutant.
    const d = makeMutant('voice-number-only',
      'return source === null || source === undefined ? start : String(source)',
      'return source === null || source === undefined ? start : String(String(source).split("/voice:").pop())');
    dirs.push(d);
    runReal('mutant voice-number-only', d);  }

  const failed = rows.filter(function (r) { return !r.ok; });
  const mutantRows = rows.filter(function (r) { return r.arm !== 'real'; });
  console.log('\narms ' + (rows.length - failed.length) + '/' + rows.length);
  if (NEG) {
    const mutantFailed = mutantRows.filter(function (r) { return !r.ok; }).length;
    const ok = mutantFailed > 0;
    console.log('NEG-ARM: o mutante tem de falhar em ' + mutantFailed + ' arm(s) -> ' + (ok ? 'RED-OK' : 'NAO CAIU (inerte)'));
    console.log('VERDICT: ' + (ok ? 'PASS' : 'FAIL'));
    process.exit(ok ? 0 : 1);
  }
  console.log('VERDICT: ' + (failed.length ? 'FAIL' : 'PASS'));
  process.exit(failed.length ? 1 : 0);
} finally {
  for (const d of dirs) { try { fs.rmSync(d, { recursive: true, force: true }); } catch (e) { /* temp */ } }
}