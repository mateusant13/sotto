'use strict';

/**
 * _panel2-repeat-probe.js — THE SAME LINE MUST NOT BE DRAWN TWICE.
 *
 * THE OWNER'S ORDER (2026-10-08, verbatim): *"essa repeticao de linhas tem que
 * acabar. nao sei como faria, mas nao tem que repetir linha e com append na
 * proxima."* — and the rule he wants is LINE IDENTITY = `start`: one live-box row
 * per worker segment, a later commit for a `start` ALREADY on screen REPLACES
 * that row's text, and only a NEW `start` appends.
 *
 * WHAT THIS DRIVES, and nothing else: the REAL `app/panel/panel.html` parsed
 * and its REAL scripts run under jsdom against a stub bridge, then a fixture of
 * worker caption events is pushed through the panel's OWN subscription — the same
 * path the shell uses (`bridge.onCaption` → `engine.ingest` → `onCommit` →
 * `addCaption` → the row). No panel logic is re-implemented here; the assertions
 * read the DOM the panel painted.
 *
 * THE FIXTURE carries BOTH shapes, and says which is which in its own header:
 *   * the cumulative partial stream of a REAL worker run
 *     (`_main/_route-stream-long.jsonl`, first ~24 s), where the last partial and
 *     the `final` text agree;
 *   * the REVISION shape, which the recorded run does not contain (0 revisions in
 *     its 135 segments — re-measured while writing this): the five
 *     `BRIDGE_CAPTION_SENT` lines quoted by the dispatch from the owner's own
 *     `_main/webview-run.log`, where `start=20.16` appears twice and the final
 *     text is NOT the last partial. Without that second half the probe would pass
 *     on a panel that cannot survive the shape the owner is looking at.
 *
 * ARMS
 *   A  NO TWO COMMITTED ROWS SHARE A `start`.
 *   B  NO ROW'S TEXT IS THE REPEATED PREFIX OF THE NEXT ROW (the owner's symptom):
 *      for every adjacent pair, the shorter text may not be a prefix of the
 *      longer once whitespace is normalised.
 *   C  THE ROW COUNT EQUALS THE NUMBER OF DISTINCT SEGMENTS in the fixture.
 *   D  THE REVISION IS SHOWN IN PLACE: a row's `data-revision="true"` is set on
 *      the row that was rewritten, and the revision's text is the row's CURRENT
 *      text — the stale wording is nowhere in the box.
 *   E  BOTH COLOURS, in this one command: the same fixture against a COPY of
 *      `panel.js` with the identity rule disabled (`--revert`, the two lines that
 *      make the lookup return nothing) must go RED on A/B/C and print the
 *      duplicated rows.
 *
 *   node _main/_panel2-repeat-probe.js
 *   node _main/_panel2-repeat-probe.js --revert      (the negative control)
 *
 * WAS DEAD IN BOTH COLOURS UNTIL 2026-10-08 — measured, then fixed, and the
 * shape is worth keeping: ARM D read `p.document.getElementById('caption-list')`
 * AFTER `p.window.close()`, and a CLOSED jsdom Document answers `null` (it held
 * `#caption-list` 200 lines earlier). Both colours therefore died with
 * `TypeError: Cannot read properties of null (reading 'textContent')`, rc=1, no
 * verdict line of any kind, ARM D never evaluated — and the mutant copy
 * `_main/_panel2-repeat-panel-mutant.js` was LEFT ON DISK, because
 * `fs.rmSync(MUTANT)` sat after the crash point. An instrument that cannot pass
 * in either colour is worse than none. The cure: the box text is captured while
 * the document is live, `closeWindow()` replaces the bare `close()`, the arms
 * run in a closure whose THROW is a recorded FAIL rather than an uncaught crash,
 * and the removal of the control copy sits in a `finally` that prints
 * `control copy removed: true|false` on EVERY run (a removal that fails is
 * itself a failed arm, so no run reports success with the copy left behind).
 *
 * Exit codes: 0 every arm passed (or, with `--revert`, the control went RED as
 * expected) | 1 an arm failed | 2 setup error. No window, no browser, no audio.
 */

const fs = require('node:fs');
const path = require('node:path');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const PANEL_HTML = path.join(REPO, 'app', 'panel', 'panel.html');
const PANEL_JS = path.join(REPO, 'app', 'panel', 'panel.js');
const PANEL_CSS = path.join(REPO, 'app', 'panel', 'panel.css');
const FIXTURE = path.join(HERE, '_panel2-repeat-fixture.jsonl');
const MUTANT = path.join(HERE, '_panel2-repeat-panel-mutant.js');

const REVERT = process.argv.includes('--revert');

let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (err) {
  console.log(`SETUP ERROR: jsdom is required (${err && err.message}).`);
  process.exit(2);
}

const results = [];
function arm(name, real, want, control) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  const differs = control === undefined || JSON.stringify(real) !== JSON.stringify(control);
  const good = ok && differs;
  results.push(good);
  console.log(`[${good ? 'PASS' : 'FAIL'}] ${name}`);
  console.log(`       real    = ${JSON.stringify(real)}`);
  console.log(`       want    = ${JSON.stringify(want)}`);
  if (control !== undefined) console.log(`       control = ${JSON.stringify(control)}`);
}

/** The fixture: every line that parses as JSON, in order. */
function readFixture() {
  return fs.readFileSync(FIXTURE, 'utf8')
    .split(/\r?\n/)
    .filter((l) => l.trim() && !l.trim().startsWith('//'))
    .map((l) => JSON.parse(l))
    .filter((e) => e.type === 'caption' && typeof e.text === 'string');
}

/**
 * The panel under test, with the real scripts and a stub bridge. `panelSource`
 * lets the negative control run a COPY of panel.js with only the identity rule
 * disabled.
 */
function panelUnderTest(panelSource) {
  const html = fs.readFileSync(PANEL_HTML, 'utf8');
  const dom = new JSDOM(html, {
    url: `file:///${PANEL_HTML.replace(/\\/g, '/')}#panel`,
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  const { window } = dom;
  const style = window.document.createElement('style');
  style.textContent = fs.readFileSync(PANEL_CSS, 'utf8');
  window.document.head.prepend(style);

  const subs = { caption: [], status: [] };
  window.sotto = {
    onCaption: (cb) => subs.caption.push(cb),
    onStatus: (cb) => subs.status.push(cb),
    onGeometry: () => {},
    hide: () => {}, toggle: () => {}, quit: () => {}, setPointerInteractive: () => {},
    captionApplied: () => {}, statusApplied: () => {}, ready: () => {}, clearApplied: () => {},
    getInfo: () => Promise.resolve({ hotkey: 'Alt+C' }),
    HOTKEY: 'Alt+C',
    platform: 'win32',
    history: {
      append: () => Promise.resolve({ entry: null }),
      tail: () => Promise.resolve({ entries: [], root: '', canonicalProducer: null }),
      search: () => Promise.resolve({ hits: [] }),
      root: () => Promise.resolve({ root: '', canonicalProducer: null }),
      reveal: () => {},
    },
  };

  const errors = [];
  for (const src of [...html.matchAll(/<script src="([^"]+)"><\/script>/g)].map((m) => m[1])) {
    const file = src === 'panel.js' ? null : path.resolve(path.dirname(PANEL_HTML), src);
    const source = file ? fs.readFileSync(file, 'utf8') : panelSource;
    try { window.eval(source); } catch (err) { errors.push(`${src}: ${err && err.message}`); }
  }
  window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true }));

  return {
    window,
    document: window.document,
    errors,
    /** Push one worker event through the panel's own caption subscription. */
    feed(event) {
      const meta = {};
      for (const k of Object.keys(event)) if (k !== 'type' && k !== 'text') meta[k] = event[k];
      for (const cb of subs.caption) cb({ text: event.text, meta });
    },
    /** Push one worker STATUS through the panel's own subscription (the flush). */
    status(text, kind) {
      for (const cb of subs.status) cb({ text, kind: kind || 'busy' });
    },
    /** Every committed row, oldest first, as (start, text). */    rows() {
      return [...window.document.querySelectorAll('#caption-list .caption')]
        .filter((li) => !li.className.includes('caption--provisional'))
        .map((li) => ({
          start: li.dataset ? li.dataset.start : null,
          revision: li.dataset ? li.dataset.revision : null,
          text: String(li.querySelector('.caption__text')
            ? li.querySelector('.caption__text').textContent : '').replace(/\s+/g, ' ').trim(),
        }));
    },
    /** Every row, provisional included — what the owner's eye sees. */
    allRows() {
      return [...window.document.querySelectorAll('#caption-list .caption')]
        .map((li) => ({
          provisional: li.className.includes('caption--provisional'),
          start: li.dataset ? li.dataset.start : null,
          text: String(li.textContent).replace(/\s+/g, ' ').trim(),
        }));
    },
  };
}

/**
 * Replaces `window.close()`. MEASURED 2026-10-08: after jsdom's `window.close()`
 * the captured Document object is no longer usable — on line 263
 * `p.document.getElementById('caption-list')` returned **null**
 * (`TypeError: Cannot read properties of null (reading 'textContent')`) even
 * though the document held `#caption-list` when it was captured 200 lines
 * earlier. Dropping the window's own timers is enough for this probe to exit,
 * so the Document the arms read is never a closed one.
 */
function closeWindow(window) {
  try {
    for (let id = window.setTimeout(() => {}, 0); id > 0; id -= 1) window.clearTimeout(id);
  } catch (err) {
    console.log(`NOTE: could not clear jsdom timer ${err && err.message}`);
  }
  try { window.close(); } catch (err) { console.log(`NOTE: window.close() threw ${err && err.message}`); }
}

function main() {
  for (const file of [PANEL_HTML, PANEL_JS, PANEL_CSS, FIXTURE]) {
    if (!fs.existsSync(file)) {
      console.log(`SETUP ERROR: missing ${path.relative(REPO, file)}`);
      return 2;
    }
  }
  const events = readFixture();
  if (!events.length) {
    console.log('SETUP ERROR: the fixture holds no caption event');
    return 2;
  }
  const distinct = new Set(events.map((e) => String(e.start))).size;

  let panelSource = null;
  if (REVERT) {
    // THE NEGATIVE CONTROL: a copy of the REAL panel.js with the identity rule
    // disabled and NOTHING else changed — the lookup that decides "this commit
    // belongs to a row already on screen" always misses, so every commit appends.
    // This is the pre-fix behaviour, reproduced exactly rather than described.
    const src = fs.readFileSync(PANEL_JS, 'utf8');
    const anchor = '  const existing = start === null ? null : committedByStart.get(start) || null;';
    if (!src.includes(anchor)) {
      console.log('SETUP ERROR: the identity lookup anchor is not in panel.js — the control cannot be built.');
      return 2;
    }
    panelSource = src.replace(anchor, '  const existing = null; // CONTROL: identity rule disabled');
    fs.writeFileSync(MUTANT, panelSource, 'utf8');
    console.log(`control : ${path.relative(REPO, MUTANT)} — a COPY of panel.js with the identity rule disabled\n`);
  }

  console.log(`fixture : ${path.relative(REPO, FIXTURE)} — ${events.length} caption event(s), ${distinct} distinct start(s)`);
  console.log(`panel   : ${REVERT ? 'the CONTROL copy (identity rule OFF)' : path.relative(REPO, PANEL_JS)}\n`);

  const p = panelUnderTest(REVERT ? panelSource : fs.readFileSync(PANEL_JS, 'utf8'));
  if (p.errors.length) {
    console.log(`SETUP ERROR: the panel threw: ${JSON.stringify(p.errors)}`);
    return 2;
  }
  for (const e of events) p.feed(e);
  // THE SHELL'S OWN LAST EVENT. A worker run ends with a status (the worker's
  // `done`), and the panel flushes the engine on every status change — that is
  // what turns a line the worker closed into a committed row. The fixture carries
  // caption events only, so the probe sends the same status the shell does;
  // without it the final segment would sit as the open provisional row and the
  // revision arm would have nothing committed to read.
  p.status('done', 'busy');

  const rows = p.rows();
  const printed = p.allRows();
  console.log(`--- the rows the panel painted (${rows.length} committed, ${printed.length} total) ---`);
  for (const r of printed) {
    console.log(`  ${r.provisional ? 'OPEN ' : 'LINE '} start=${JSON.stringify(r.start)}  ${JSON.stringify(r.text)}`);
  }
  // `#caption-list`'s text is read by ARM D, and the READING of a closed jsdom
  // Document is what broke this probe in BOTH colours: ARM D sat AFTER
  // `p.window.close()` (2026-10-08: `TypeError: Cannot read properties of null
  // (reading 'textContent')` at the old `:263`, rc=1 with no verdict line in
  // either colour, and the mutant copy left on disk because `fs.rmSync(MUTANT)`
  // sat after the crash point). The text is therefore CAPTURED here, while the
  // document is live, and every arm below reads this copy.
  const boxText = String(p.document.getElementById('caption-list').textContent);

  // ── ARM A ────────────────────────────────────────────────────────────────
  const starts = rows.map((r) => r.start);
  const duplicates = starts.filter((s, i) => s !== null && starts.indexOf(s) !== i);
  const prefixPairs = [];
  for (let i = 0; i + 1 < rows.length; i += 1) {
    const a = rows[i].text.toLowerCase();
    const b = rows[i + 1].text.toLowerCase();
    if (!a || !b) continue;
    if (b.startsWith(a) || a.startsWith(b)) {
      prefixPairs.push({ at: i, a: rows[i].text, b: rows[i + 1].text });
    }
  }
  const revisionRows = rows.filter((r) => r.revision === 'true');
  const lastStart = String(events[events.length - 1].start);
  const revised = rows.find((r) => r.start === lastStart) || null;

  /**
   * Every arm, run AFTER the window is released. Defined as a closure because
   * its FAILURE is a possibility that must not take the cleanup path with it.
   */
  const runArms = () => {
    arm('ARM A no two committed rows share a `start`', duplicates, [],
      REVERT ? ['(the control duplicates by construction)'] : undefined);

    // ── ARM B ──────────────────────────────────────────────────────────────
    arm('ARM B no row repeats the next row\'s words (the owner\'s symptom)',
      prefixPairs, [], REVERT ? [{ at: 0, a: '(control)', b: '(control)' }] : undefined);
    for (const pair of prefixPairs) {
      console.log(`       repeated: ${JSON.stringify(pair.a)}  ->  ${JSON.stringify(pair.b)}`);
    }

    // ── ARM C ──────────────────────────────────────────────────────────────
    arm('ARM C one committed row per distinct segment in the fixture',
      rows.length, distinct, REVERT ? distinct + 1 : undefined);

    // ── ARM D ──────────────────────────────────────────────────────────────
    arm('ARM D the revision was applied IN PLACE, and the stale wording is gone',
      [revisionRows.length > 0, revised ? revised.text : null,
        boxText.includes('and on the right')],
      [true, 'Problems and use this skill and that skill and on the.', false],
      REVERT ? [false, null, true] : undefined);
  };

  // The jsdom window keeps timers alive; clear them, and ONLY THEN release it —
  // every DOM read the arms need has already been taken above.
  console.log('');
  closeWindow(p.window);
  try {
    // ARMs A-C and the ARM D index were read before the release; the arm calls
    // themselves run no DOM code, so they stay unchanged in the output.
    runArms();
  } catch (err) {
    const where = (err && err.stack ? String(err.stack).split('\n')[1] : '') || '';
    results.push(false);
    console.log(`[FAIL] an arm threw — ${err && err.message}${where ? ` at${where.replace(/^\s*at\s*/, ' ')}` : ''}`);
    console.log(`       (the instrument is broken: a crash is a FAIL, never a pass)`);
  } finally {
    // ALWAYS, and in the SAME closure as the writing run: the copy's own
    // `fs.rmSync` used to sit after the crash point, which is why the
    // instrument's mutant survived every broken run. A removal that FAILS is
    // also counted as a failed arm, so no run can report success while leaving
    // the broken copy on disk.
    if (panelSource !== null) {
      try { fs.rmSync(MUTANT, { force: true }); } catch (err) {
        console.log(`control copy removal threw: ${err && err.message}`);
      }
      const gone = !fs.existsSync(MUTANT);
      console.log(`control copy removed: ${gone}${gone ? '' : ` — *** ${path.relative(REPO, MUTANT)} IS STILL ON DISK ***`}`);
      if (!gone) results.push(false);
    }
  }

  // ── verdict ──────────────────────────────────────────────────────────────
  const failed = results.filter((r) => !r).length;
  if (REVERT) {
    const wentRed = failed > 0;
    console.log(`\nCONTROL: arms failed = ${failed} of ${results.length} — want > 0`);
    console.log(`CONTROL ${wentRed ? 'PASS' : 'FAIL'} — ${wentRed
      ? 'the identity rule is what removes the repetition: with it disabled every commit appends'
      : 'THE CONTROL STAYED GREEN: these arms do not measure the identity rule'}`);
    console.log(`RESULT: ${wentRed ? 'GREEN' : 'RED'} — control behaved as required`);
    return wentRed ? 0 : 1;
  }
  console.log(`\nRESULT: ${failed ? `RED — ${failed} violation(s)` : 'GREEN'} — ${results.length - failed}/${results.length} arm(s)`);
  console.log(`  run the control too: node ${path.relative(REPO, path.join(HERE, '_panel2-repeat-probe.js'))} --revert`);
  return failed ? 1 : 0;
}

process.exit(main());
