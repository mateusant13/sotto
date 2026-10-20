'use strict';

/**
 * _main/panel-live-box-oracle.js — THE LIVE BOX SHOWS THE LINE.
 *
 * WHAT IT RUNS. Not a fixture: `app/panel/panel.html` is loaded from disk, its
 * OWN `<script src>` list is executed by jsdom in the order the markup names,
 * and every arm below asks the resulting DOCUMENT. The files under test are the
 * ones the app ships; `panel.js` is never stubbed, re-implemented or edited
 * here. A MUTANT is a real copy of `app/panel` on disk with ONE thing broken
 * in `panel.js`, and the arms are run against that copy — so the arms that
 * notice a broken panel are arms that ran the real bytes.
 *
 * WHY IT EXISTS (the owner's complaint, 2026-10-20, 00:44:14). The owner sent
 * a photo of an EMPTY panel and said the app "parece viva mas nao entrega
 * nada". The measurement (`_main/panel-state.json`, 02:22:35, the app running
 * with the owner's YouTube open) says:
 *
 *     live.count = 1, live.hidden = true, placeholder.hidden = false
 *     live.lines = [{ provisional: true, text: "demais para este video , mas aqui" }]
 *
 * The caption HAD ARRIVED and was INVISIBLE. The mechanism, read in the code:
 * `panel.html` ships `<ol class="captions__list" id="caption-list" hidden>` and
 * `panel.css` makes that attribute bite (`.captions__list[hidden] { display:
 * none; }`), so the box is hidden until something is in it. The attribute was
 * taken off in ONE place only — `addCaption`, the path a COMMITTED line takes.
 * A line that is still PROVISIONAL (the player's own captions, the ASR
 * hypothesis still growing) never goes through `addCaption`, so it was painted
 * into a box that stayed `display: none`, and the placeholder — which only
 * `addCaption` hides — stayed on screen. The owner saw a placeholder and an
 * empty box while the caption was in the DOM.
 *
 * ARMS
 *   A  a painted line shows the box and hides the placeholder;
 *   B  the INITIAL state (list hidden, no rows) keeps the placeholder visible;
 *   C  after the box empties, the placeholder comes back;
 *   D  the painted line carries the cue the owner actually saw.
 *
 * MUTANTS (the negative arm, RUN — not described). Each is a real copy of the
 * panel with ONE break, and each must go RED on the claim it breaks:
 *   M1  re-hides the list after painting it  -> RED on A;
 *   M2  hides the placeholder but not the list -> RED on A;
 *   M3  never shows the placeholder again      -> RED on C.
 *
 *   node _main/panel-live-box-oracle.js
 *
 * POINTING IT AT ANOTHER PANEL. `SOTTO_PANEL_DIR=<dir>` runs the ARMS against
 * another copy of the panel — the same trick `_main/_panel2-dom-probe.js`
 * uses — and SKIPS the mutant phase, because the mutants' anchors are the
 * fixed panel's own lines. That is how the PRE-FIX panel is measured: the
 * arms must go RED on the claim the fix repaired.
 *
 * Exit codes: 0 every arm passed and every mutant went RED | 1 an arm failed
 * (printed with real/want) or a mutant stayed GREEN | 2 setup error (jsdom
 * absent, a panel file missing, the panel threw while loading).
 *
 * No window, no browser, no audio, no network, and the running app is never
 * touched: jsdom loads the panel's files over `file://` and nothing else.
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const SHIPPED_PANEL = path.join(REPO, 'app', 'panel');
// WHICH PANEL. The shipped one by default; `SOTTO_PANEL_DIR` points the ARMS
// at another copy (the pre-fix panel, for the "before" measurement) and skips
// the mutant phase, whose anchors are the fixed panel's own lines.
const PANEL_DIR = process.env.SOTTO_PANEL_DIR
  ? path.resolve(process.env.SOTTO_PANEL_DIR)
  : SHIPPED_PANEL;
const PANEL_HTML = path.join(PANEL_DIR, 'panel.html');
const ARMS_ONLY = Boolean(process.env.SOTTO_PANEL_DIR);

// THE CUE THE OWNER SAW, verbatim from the app's own state file
// (`_main/panel-state.json`, 2026-10-20 02:22:35), on the YouTube route.
const CUE = 'demais para este video , mas aqui';
const CUE_SOURCE = 'external:youtube:track';
// THE TAIL MARKER the panel paints on a forming line (`panel.js`'s `.caption__mark`).
const MARK = '▍';

const fileUrl = (p) => `file:///${p.replace(/\\/g, '/')}`;

function squeeze(text) {
  return String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
}

/** Collapse DOM whitespace, so an assertion compares words, not indentation. */
function readBox(p) {
  const list = p.document.getElementById('caption-list');
  const placeholder = p.document.getElementById('placeholder');
  const computed = (el) => (el ? p.window.getComputedStyle(el).display : null);
  return {
    rows: list ? list.childElementCount : -1,
    listHidden: list ? !!list.hidden : null,
    listDisplay: computed(list),
    placeholderHidden: placeholder ? !!placeholder.hidden : null,
    placeholderDisplay: computed(placeholder),
  };
}

/** ONE player cue, on the channel the shell really uses (`external-caption`). */
function paintExternal(p, final) {
  const payload = {
    text: CUE,
    meta: { start: 1, end: 2, chunk_start: 1, chunks: [[1, 2, CUE]], final: Boolean(final), source: CUE_SOURCE },
  };
  for (const cb of p.subs.external) cb(payload);
}

/**
 * A bridge stub with the surface the real shell installs.
 *
 * `window.sotto` MUST exist before the page parses — the shell loads its own
 * `stage.html` first for exactly this reason — so it is installed in
 * `beforeParse`.
 */
function bridgeStub(subs) {
  const bridge = {
    onCaption: (cb) => subs.caption.push(cb),
    onExternalCaption: (cb) => subs.external.push(cb),
    onStatus: (cb) => subs.status.push(cb),
    onGeometry: () => {},
    hide: () => {}, toggle: () => {}, quit: () => {}, setPointerInteractive: () => {},
    captionApplied: () => {}, statusApplied: () => {}, ready: () => {}, clearApplied: () => {},
    getInfo: () => Promise.resolve({ hotkey: 'Alt+C', versions: { shell: 'oracle' } }),
    HOTKEY: 'Alt+C',
    platform: 'win32',
    history: {
      append: () => Promise.resolve({ entry: null }),
      tail: () => Promise.resolve({ entries: [], root: 'H:\\sotto\\history', canonicalProducer: null }),
      search: () => Promise.resolve({ hits: [] }),
      root: () => Promise.resolve({ root: 'H:\\sotto\\history', canonicalProducer: null }),
      reveal: () => {},
    },
  };
  return bridge;
}

/**
 * ONE loaded panel: the real markup, the real stylesheets, the real scripts.
 *
 * The scripts run as CLASSIC scripts (jsdom's `runScripts: 'dangerously'` with
 * `resources: 'usable'`), not through `window.eval`: a classic script's
 * top-level function declarations are properties of the global object, which is
 * what lets an arm ask the panel to do something the bridge does not offer
 * (arm C retires the open row). The bridge is installed in `beforeParse`, so
 * the page finds it exactly as it finds the shell's.
 */
async function loadPanel(panelDir) {
  const html = fs.readFileSync(path.join(panelDir, 'panel.html'), 'utf8');
  const subs = { caption: [], external: [], status: [] };
  const pageErrors = [];
  const resourceErrors = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (err) => {
    const message = String((err && err.message) || err);
    if (/Uncaught|unhandled/i.test(message)) pageErrors.push(message);
    else resourceErrors.push(message);
  });
  virtualConsole.on('error', (...args) => resourceErrors.push(args.map(String).join(' ')));

  const dom = new JSDOM(html, {
    url: fileUrl(path.join(panelDir, 'panel.html')),
    runScripts: 'dangerously',
    resources: 'usable',
    pretendToBeVisual: true,
    virtualConsole,
    beforeParse(window) {
      window.sotto = bridgeStub(subs);
      window.addEventListener('error', (event) => {
        pageErrors.push(String((event && event.error && event.error.stack) || (event && event.message) || event));
      });
    },
  });
  const { window } = dom;
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('the panel never finished loading')), 60000);
    window.addEventListener('load', () => { clearTimeout(timer); resolve(); });
  });
  if (pageErrors.length) {
    window.close();
    throw new Error(`the panel threw while loading: ${pageErrors[0]}`);
  }
  return { window, subs, document: window.document, resourceErrors };
}

// ---------------------------------------------------------------------------
// THE ARMS
// ---------------------------------------------------------------------------

const ARMS = [
  {
    id: 'A',
    name: 'a painted line shows the box and hides the placeholder',
    async run(panelDir) {
      const p = await loadPanel(panelDir);
      try {
        paintExternal(p, false);
        const s = readBox(p);
        return {
          real: {
            rows: s.rows,
            listHidden: s.listHidden,
            listVisible: s.listDisplay !== 'none',
            placeholderHidden: s.placeholderHidden,
            placeholderVisible: s.placeholderDisplay !== 'none',
          },
          want: {
            rows: 1,
            listHidden: false,
            listVisible: true,
            placeholderHidden: true,
            placeholderVisible: false,
          },
        };
      } finally { p.window.close(); }
    },
  },
  {
    id: 'B',
    name: 'the INITIAL state keeps the placeholder and the box hidden',
    async run(panelDir) {
      const p = await loadPanel(panelDir);
      try {
        const s = readBox(p);
        return {
          real: {
            rows: s.rows,
            listHidden: s.listHidden,
            listVisible: s.listDisplay !== 'none',
            placeholderHidden: s.placeholderHidden,
            placeholderVisible: s.placeholderDisplay !== 'none',
          },
          want: {
            rows: 0,
            listHidden: true,
            listVisible: false,
            placeholderHidden: false,
            placeholderVisible: true,
          },
        };
      } finally { p.window.close(); }
    },
  },
  {
    id: 'C',
    name: 'the placeholder comes back when the box empties',
    async run(panelDir) {
      const p = await loadPanel(panelDir);
      try {
        paintExternal(p, false);
        const list = p.document.getElementById('caption-list');
        const row = list ? list.firstElementChild : null;
        // THE ORACLE DELETES THE LINE. The row goes; the panel is then told its
        // own open row is gone (`retireProvisional` is the panel's OWN emptying
        // event, the one `addCaption` calls before it writes the closed line).
        if (row && row.parentNode === list) list.removeChild(row);
        if (typeof p.window.retireProvisional !== 'function') {
          throw new Error('setup: the panel does not expose retireProvisional');
        }
        p.window.retireProvisional(CUE_SOURCE);
        const s = readBox(p);
        return {
          real: {
            rows: s.rows,
            listHidden: s.listHidden,
            placeholderHidden: s.placeholderHidden,
            placeholderVisible: s.placeholderDisplay !== 'none',
          },
          want: {
            rows: 0,
            listHidden: true,
            placeholderHidden: false,
            placeholderVisible: true,
          },
        };
      } finally { p.window.close(); }
    },
  },
  {
    id: 'D',
    name: 'the painted line carries the cue the owner saw',
    async run(panelDir) {
      const p = await loadPanel(panelDir);
      try {
        paintExternal(p, false);
        const row = p.document.querySelector('#caption-list .caption--provisional');
        const body = row ? row.querySelector('.caption__text') : null;
        const mark = row ? row.querySelector('.caption__mark') : null;
        const words = squeeze(body ? body.textContent : '').replace(/\s*▍\s*$/, '');
        return {
          real: {
            words,
            marker: mark ? mark.textContent : null,
            provisional: !!(row && row.classList.contains('caption--provisional')),
            source: row && row.dataset ? row.dataset.source : null,
          },
          want: {
            words: CUE,
            marker: MARK,
            provisional: true,
            source: CUE_SOURCE,
          },
        };
      } finally { p.window.close(); }
    },
  },
];

// ---------------------------------------------------------------------------
// THE MUTANTS — the negative arm, RUN
// ---------------------------------------------------------------------------

/**
 * Each mutant breaks ONE thing in a real copy of the panel.
 *
 * The anchors are the panel's own lines, and a mutant whose anchor does not
 * match EXACTLY ONCE is a setup error, not a silent no-op: a mutant that did
 * not apply would leave the arms GREEN and prove nothing.
 */
const MUTANTS = [
  {
    id: 'M1',
    name: 're-hides the list right after painting it',
    expectRed: 'A',
    oldText: [
      '    syncCaptionBox();',
      '    paintedWordsBySource.set(key, { confirmed: [], provisional: [], total: 0 });',
    ].join('\n'),
    newText: [
      '    syncCaptionBox();',
      '    dom.list.hidden = true;',
      '    paintedWordsBySource.set(key, { confirmed: [], provisional: [], total: 0 });',
    ].join('\n'),
  },
  {
    id: 'M2',
    name: 'hides the placeholder but does NOT show the list',
    expectRed: 'A',
    oldText: [
      '  if (dom.list.childElementCount > 0) {',
      '    dom.list.hidden = false;',
    ].join('\n'),
    newText: [
      '  if (dom.list.childElementCount > 0) {',
    ].join('\n'),
  },
  {
    id: 'M3',
    name: 'never shows the placeholder again',
    expectRed: 'C',
    oldText: [
      '  } else {',
      '    dom.list.hidden = true;',
      '    if (dom.placeholder) dom.placeholder.hidden = false;',
      '  }',
    ].join('\n'),
    newText: [
      '  } else {',
      '    dom.list.hidden = true;',
      '  }',
    ].join('\n'),
  },
];

/** Apply a mutant's break to the shipped `panel.js` text (CRLF preserved). */
function breakPanelJs(text, mutant) {
  const oldText = mutant.oldText.replace(/\n/g, '\r\n');
  const newText = mutant.newText.replace(/\n/g, '\r\n');
  const count = text.split(oldText).length - 1;
  if (count !== 1) {
    throw new Error(`setup: mutant ${mutant.id} anchor matched ${count} times (expected 1)`);
  }
  return text.replace(oldText, newText);
}

/** A real copy of the panel on disk, so the mutant is bytes on a filesystem. */
function copyPanel(dest) {
  fs.rmSync(dest, { recursive: true, force: true });
  fs.cpSync(PANEL_DIR, dest, {
    recursive: true,
    // `_fonts/` is a 20 MB font cache that no arm reads; the copy skips it so
    // the gate stays fast. Every file the panel LOADS is copied.
    filter: (src) => path.basename(src) !== '_fonts',
  });
  return dest;
}

/** Count the line endings of a file, because the repo measures them. */
function endings(file) {
  const bytes = fs.readFileSync(file);
  let crlf = 0;
  let bare = 0;
  for (let i = 0; i < bytes.length; i += 1) {
    if (bytes[i] === 0x0a) {
      if (i > 0 && bytes[i - 1] === 0x0d) crlf += 1;
      else bare += 1;
    }
  }
  return { crlf, bare };
}

// ---------------------------------------------------------------------------

function report(label, arm, result) {
  const ok = JSON.stringify(result.real) === JSON.stringify(result.want);
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${label} ${arm.id} — ${arm.name}`);
  console.log(`       real    = ${JSON.stringify(result.real)}`);
  console.log(`       want    = ${JSON.stringify(result.want)}`);
  return ok;
}

async function main() {
  if (!fs.existsSync(PANEL_HTML)) {
    console.log(`SETUP ERROR: missing ${path.relative(REPO, PANEL_HTML)}`);
    return 2;
  }
  const shipped = path.join(PANEL_DIR, 'panel.js');
  const shippedEndings = endings(shipped);
  console.log(`panel: ${PANEL_DIR}`);
  console.log(`panel.js: ${fs.statSync(shipped).size} B, CRLF=${shippedEndings.crlf} bareLF=${shippedEndings.bare}`);
  if (shippedEndings.bare) {
    console.log('SETUP ERROR: the panel.js under test is not CRLF pure');
    return 2;
  }

  // ---------------------------------------------------------------- CONTROL
  console.log('=== CONTROL — the panel under test ===');
  const control = [];
  for (const arm of ARMS) {
    try {
      const result = await arm.run(PANEL_DIR);
      control.push({ arm: arm.id, ok: report('control', arm, result) });
    } catch (err) {
      console.log(`[FAIL] control ${arm.id} — ${err && err.message}`);
      control.push({ arm: arm.id, ok: false });
    }
  }
  const armsOk = control.filter((r) => r.ok).length;
  console.log(`arms : ${armsOk}/${ARMS.length}`);

  // -------------------------------------------------------------- MUTANTS
  if (ARMS_ONLY) {
    console.log('mutantes : skipped (SOTTO_PANEL_DIR — the arms only)');
    const good = armsOk === ARMS.length;
    console.log(`VERDICT: ${good ? 'PASS' : 'FAIL'}  (arms ${armsOk}/${ARMS.length})`);
    return good ? 0 : 1;
  }
  const tmpRoot = path.join(
    process.env.TMPDIR || (fs.existsSync('I:\\cc-tmp') ? 'I:\\cc-tmp' : os.tmpdir()),
    'sotto-panel-live-box-oracle',
  );
  const mutantDir = path.join(tmpRoot, 'mutant-panel');
  let mutantsOk = 0;
  const mutantResults = [];
  try {
    copyPanel(mutantDir);
    const pristine = fs.readFileSync(shipped, 'utf8');
    for (const mutant of MUTANTS) {
      let broken;
      try {
        broken = breakPanelJs(pristine, mutant);
      } catch (err) {
        console.log(`[FAIL] mutant ${mutant.id} — ${err && err.message}`);
        mutantResults.push({ id: mutant.id, ok: false });
        continue;
      }
      fs.writeFileSync(path.join(mutantDir, 'panel.js'), broken, 'utf8');
      const brokenEndings = endings(path.join(mutantDir, 'panel.js'));
      if (brokenEndings.bare) {
        console.log(`[FAIL] mutant ${mutant.id} — the broken copy is not CRLF pure`);
        mutantResults.push({ id: mutant.id, ok: false });
        continue;
      }
      console.log(`=== MUTANT ${mutant.id} — ${mutant.name} (expects RED on ${mutant.expectRed}) ===`);
      const reds = [];
      for (const arm of ARMS) {
        let result;
        try {
          result = await arm.run(mutantDir);
        } catch (err) {
          console.log(`[FAIL] mutant ${mutant.id} arm ${arm.id} — ${err && err.message}`);
          reds.push(arm.id);
          continue;
        }
        const ok = JSON.stringify(result.real) === JSON.stringify(result.want);
        console.log(`[${ok ? 'GREEN' : 'RED' }] mutant ${mutant.id} arm ${arm.id} — ${arm.name}`);
        if (!ok) {
          console.log(`       real    = ${JSON.stringify(result.real)}`);
          console.log(`       want    = ${JSON.stringify(result.want)}`);
        }
        if (!ok) reds.push(arm.id);
      }
      // The mutant must go RED on the claim it breaks, and on NOTHING else: an
      // arm that cannot tell the difference is decoration.
      const expectedRed = reds.includes(mutant.expectRed);
      const onlyExpected = reds.length === 1 && reds[0] === mutant.expectRed;
      const ok = expectedRed && onlyExpected;
      console.log(`mutant ${mutant.id}: RED on [${reds.join(', ') || 'none'}] — `
        + `${ok ? 'PASS' : 'FAIL'} (expected exactly [${mutant.expectRed}])`);
      mutantResults.push({ id: mutant.id, ok, reds });
      if (ok) mutantsOk += 1;
    }
  } finally {
    try { fs.rmSync(tmpRoot, { recursive: true, force: true }); } catch (err) { /* best effort */ }
  }
  console.log(`mutantes : ${mutantsOk}/${MUTANTS.length} RED`);

  const good = armsOk === ARMS.length && mutantsOk === MUTANTS.length;
  console.log(`VERDICT: ${good ? 'PASS' : 'FAIL'}  (arms ${armsOk}/${ARMS.length}, mutantes ${mutantsOk}/${MUTANTS.length} RED)`);
  return good ? 0 : 1;
}

main().then((code) => process.exit(code)).catch((err) => {
  console.log(`SETUP ERROR: ${(err && err.stack) || err}`);
  process.exit(2);
});
