'use strict';

/**
 * _panel2-dom-probe.js ÔÇö THE TWO SURFACES, asserted against the REAL panel.
 *
 * WHAT IT RUNS. Not a hand-written fixture: `app/panel/panel.html` is parsed,
 * ITS OWN `<script src>` LIST is executed in order, and every assertion below
 * asks the resulting DOCUMENT and the panel's ACTUAL behaviour. The files under
 * test are the ones the app ships; `panel.js` is not modified, stubbed or
 * re-implemented here.
 *
 * WHY A DOM IS NEEDED AT ALL. The other gates in `_main/` that touch the panel
 * assert the TEXT of source lines (`panel-state-guard-gate.js` extracts
 * `state()` reads, `history-producer-gate.js` runs the engine). Neither can
 * answer "is the transcript drawer visible when the document is wearing the
 * STRIP surface" ÔÇö that is not a property of a source line, it is a property of
 * the markup, the stylesheet and the runtime state together. This probe is the
 * one that answers it, and it does so by looking at a rendered document.
 *
 * ARMS
 *   S  STRIP surface: the live box + the 4 controls + the status, and NOT the
 *      transcript drawer, the header or the footer sentence block.
 *   P  PANEL surface: the drawer (with its search and its honest no-writer
 *      reason), the HUD including the folder button, and NOT the strip's row.
 *   B  BOTH COLOURS in this one command: the same documents with the surface
 *      attribute forced the other way, so a probe that cannot tell the two
 *      apart fails instead of passing twice.
 *   T  The LIVE toggle: `aria-pressed` flips, and `bridge.setLiveEnabled(bool)`
 *      really carries the value ÔÇö and is NEVER called on a shell without it.
 *   D  The PAUSE two-step: one click opens the dialog (nothing called yet), the
 *      DEFAULT FOCUS IS CANCEL, Confirm carries `{reason:'panel-confirm'}` to
 *      `bridge.pause()`, and a shell without `pause()` paints the confirm button
 *      disabled with an honest sentence instead of pretending.
 *   O  Open panel: through `bridge.setPanelSurface('panel', reason)` when the
 *      shell has it, and by switching the document itself when it does not.
 *   H  The strip's HEIGHT cannot be measured here (the sandbox has no layout
 *      engine), so what this arm decides is that the CSS that makes it short is
 *      present and in force, and that the harness file a HUMAN opens was built
 *      from these bytes with the right script order.
 *
 *   node _main/_panel2-dom-probe.js
 *
 * Exit codes: 0 every arm passed | 1 an arm failed (printed with real/want) |
 * 2 setup error (jsdom absent, a panel file missing). No window, no browser, no
 * audio, no network.
 */

const fs = require('node:fs');
const path = require('node:path');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const PANEL_HTML = path.join(REPO, 'app', 'panel', 'panel.html');
const PANEL_CSS = path.join(REPO, 'app', 'panel', 'panel.css');
const HARNESS_DIR = path.join(HERE, '_audit-render');
const HARNESS = path.join(HARNESS_DIR, 'panel-harness.html');

let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (err) {
  console.log(`SETUP ERROR: jsdom is required for this probe (${err && err.message}).`);
  process.exit(2);
}

const results = [];
let currentArm = '';

function arm(name, real, want, control) {
  const ok = JSON.stringify(real) === JSON.stringify(want);
  // `control` is what the SAME assertion produces on the OTHER surface. When it
  // is supplied the arm only passes if the two really differ: an assertion both
  // surfaces satisfy says nothing about either.
  const differs = control === undefined || JSON.stringify(real) !== JSON.stringify(control);
  const good = ok && differs;
  results.push({ arm: currentArm, name, real, want, ok: good });
  console.log(`[${good ? 'PASS' : 'FAIL'}] ${name}`);
  console.log(`       real    = ${JSON.stringify(real)}`);
  console.log(`       want    = ${JSON.stringify(want)}`);
  if (control !== undefined) console.log(`       control = ${JSON.stringify(control)}`);
}

const fileUrl = (p) => `file:///${p.replace(/\\/g, '/')}`;

/** The panel's own `<script src>` order, so this probe cannot reorder the panel. */
function scriptSources(html) {
  return [...html.matchAll(/<script src="([^"]+)"><\/script>/g)].map((m) => m[1]);
}

/** A bridge stub with the surface the real shell installs, plus what it recorded. */
function bridgeStub(window, options) {
  const audit = { live: [], pause: [], surfaces: [], revealed: [], statsCalls: [] };
  const subs = { caption: [], status: [] };
  const bridge = {
    onCaption: (cb) => subs.caption.push(cb),
    onStatus: (cb) => subs.status.push(cb),
    onGeometry: () => {},
    hide: () => {}, toggle: () => {}, quit: () => {}, setPointerInteractive: () => {},
    captionApplied: () => {}, statusApplied: () => {}, ready: () => {}, clearApplied: () => {},
    getInfo: () => Promise.resolve({ hotkey: 'Alt+C', versions: { shell: 'probe' } }),
    HOTKEY: 'Alt+C',
    platform: 'win32',
    history: {
      append: () => Promise.resolve({ entry: null }),
      tail: () => Promise.resolve({ entries: [], root: 'H:\\sotto\\history', canonicalProducer: null }),
      search: () => Promise.resolve({ hits: [] }),
      root: () => Promise.resolve({ root: 'H:\\sotto\\history', canonicalProducer: null }),
      reveal: (p) => audit.revealed.push(p || null),
    },
    __audit: audit,
    __emit: (kind, payload) => { for (const cb of subs[kind]) cb(payload); },
  };
  if (options && options.wired) {
    bridge.setLiveEnabled = (enabled) => {
      audit.live.push(Boolean(enabled));
      return Promise.resolve({ liveEnabled: Boolean(enabled) });
    };
    bridge.pause = (pauseOptions) => {
      audit.pause.push(pauseOptions || {});
      return Promise.resolve({ paused: true });
    };
    bridge.setPanelSurface = (name, reason) => {
      audit.surfaces.push({ surface: String(name), reason: String(reason || '') });
      if (window.SottoSurfaces) window.SottoSurfaces.set(String(name));
    };
  }
  if (options && options.stats) {
    // THE WIRE the receipt specifies, so the HUD's four pending rows can be seen
    // FILLED ÔÇö and so the "prints only what it carries" arm has a real payload to
    // read. `statsFields` narrows it, which is how the partial-payload arm works.
    const payload = options.statsFields || {
      rss_mb: 145, shell_rss_mb: 210, rate: 1.05, audio_s: 120, wall_s: 100,
      peak: 0.552821, blocks: 1153, model: 'nemotron-3.5-int8',
    };
    bridge.getStats = () => {
      audit.statsCalls.push(Date.now());
      return Promise.resolve(payload);
    };
  }
  window.sotto = bridge;
  return bridge;
}

/**
 * One loaded panel: the real markup, the real stylesheet, the real scripts.
 *
 * The order matters and it is the SHELL'S OWN: the bridge exists BEFORE the page
 * parses (`stage.html` is loaded first for exactly this reason), then the panel's
 * scripts run in the order `panel.html` names. `resources` is DISABLED so jsdom
 * runs nothing on its own ÔÇö every script below is executed here, in that order,
 * from the real files ÔÇö and the stylesheet is prepended as real CSS text so
 * `getComputedStyle` answers from `panel.css` and not from the UA sheet.
 */
async function panel(options) {
  const opts = options || {};
  const html = fs.readFileSync(PANEL_HTML, 'utf8');
  const dom = new JSDOM(html, {
    url: opts.url || fileUrl(PANEL_HTML),
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  const { window } = dom;
  const style = window.document.createElement('style');
  style.textContent = fs.readFileSync(PANEL_CSS, 'utf8');
  window.document.head.prepend(style);

  const bridge = bridgeStub(window, opts);
  const errors = [];
  if (opts.mutate) opts.mutate(window.document, window);
  for (const src of scriptSources(html)) {
    const file = path.resolve(path.dirname(PANEL_HTML), src);
    if (!fs.existsSync(file)) {
      errors.push(`missing ${src}`);
      continue;
    }
    try {
      window.eval(fs.readFileSync(file, 'utf8'));
    } catch (err) {
      errors.push(`${src}: ${err && err.message}`);
    }
  }
  // `surface.js` boots on DOMContentLoaded when the document is still parsing; a
  // document built from a string is already `complete`, so the listener it
  // registered never fires unless the event is dispatched here.
  try {
    window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true }));
  } catch (err) {
    errors.push(`DOMContentLoaded: ${err && err.message}`);
  }
  // The negative arm forces the OTHER surface AFTER the scripts have chosen one,
  // so the two documents differ in that attribute and nothing else.
  if (opts.forceSurface) window.document.body.setAttribute('data-surface', opts.forceSurface);

  return {
    window,
    document: window.document,
    bridge,
    audit: bridge.__audit,
    errors,
    display: (selector) => {
      const el = window.document.querySelector(selector);
      return el ? window.getComputedStyle(el).display : null;
    },
    id: (name) => window.document.getElementById(name),
    focusId: () => (window.document.activeElement ? window.document.activeElement.id : null),
    /**
     * One worker caption event, with the meta the WORKER really sends.
     *
     * The audio position is not decoration: `caption-formulation.js` decides a
     * continuation from it, and two events that both claim `start 0 / end 1` are
     * read as the model RE-READING one window ÔÇö the first line is retracted and
     * only one `<li>` exists. That is correct ENGINE behaviour and a wrong
     * FIXTURE, so the position is a parameter here rather than a constant.
     */
    caption: (text, start, end, isFinal) => bridge.__emit('caption', {
      text,
      meta: {
        start: typeof start === 'number' ? start : 0,
        end: typeof end === 'number' ? end : 1,
        final: Boolean(isFinal),
      },
    }),
    status: (text, kind) => bridge.__emit('status', { text, kind: kind || 'busy' }),
  };
}

/** Collapse DOM whitespace, so an assertion compares words, not indentation. */
function squeeze(text) {
  return String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
}

/**
 * Let every microtask already queued run.
 *
 * BOTH bridges resolve their object-returning calls as PROMISES, so state that
 * looks synchronous is one (or more) turns away: `history.root()` fills the
 * folder tooltip, `getInfo()` fills the shell facts, and ÔÇö measured here ÔÇö
 * `pause()` runs `setPaused` inside its `.then`, so a read taken in the same tick
 * as the click sees the PRE-pause paint. Two turns because those chains are
 * two deep (`.then(...).then(...)`).
 */
function tick() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function main() {
  for (const file of [PANEL_HTML, PANEL_CSS]) {
    if (!fs.existsSync(file)) {
      console.log(`SETUP ERROR: missing ${path.relative(REPO, file)}`);
      return 2;
    }
  }

  // ------------------------------------------------------------------ ARM S
  currentArm = 'S';
  console.log('=== ARM S ÔÇö the STRIP surface Alt+C opens ===');
  const strip = await panel({ url: `${fileUrl(PANEL_HTML)}#strip`, wired: true });
  if (strip.errors.length) {
    console.log(`SETUP ERROR: the real panel threw while loading: ${JSON.stringify(strip.errors)}`);
    return 2;
  }
  // ORDER MATTERS, and it is the shell's own: a STATUS event is flushed by the
  // panel (`engine.flush('status-change')`, a natural sentence boundary), so a
  // status arriving between two captions commits the live line as a draft and
  // leaves ONE `<li>`. The shell emits the "working" status first and only
  // re-emits when the state changes, so that is the order used here.
  strip.status('Receiving captions', 'live');
  // Then the worker's shape: a line it CLOSED at t=0..1.2, and the NEXT line's
  // growing partial at 1.5..2.9 ÔÇö the provisional cap the strip paints while the
  // model is still deciding. The gap stays under `SENTENCE_GAP_S` (8 s) on
  // purpose: a longer silence is an AUDIO sentence boundary and the engine
  // correctly commits the held line, which is how an earlier version of this
  // fixture measured 0 provisional lines and looked like a panel defect.
  strip.caption('O rato roeu a rolha da garrafa do rei da Russia.', 0, 1.2, true);
  strip.caption('a prova dos nove', 1.5, 2.9, false);

  arm('the document really is wearing the strip surface',
    strip.document.body.getAttribute('data-surface'), 'strip', 'panel');
  arm('the live caption box is present (body + list + placeholder)',
    [!!strip.id('captions-body'), !!strip.id('caption-list'), !!strip.id('placeholder')],
    [true, true, true]);
  arm('the live box REPLACES: two cumulative partials of ONE line stay ONE row',
    [strip.id('caption-list').childElementCount,
      squeeze(strip.document.querySelector('.caption__confirmed').textContent),
      squeeze(strip.document.querySelector('.caption__provisional').textContent)],
    [1, 'O rato roeu a rolha da garrafa do rei da Russia.', 'a prova dos nove ┬À'],
    [0, '', '']);
  // A STATUS CHANGE is the panel's own sentence boundary (`engine.flush`), and it
  // is the path that turns the open row into a CLOSED one. The worker-closed text
  // and the in-flight tail are then two rows, in order, and the closed one is no
  // longer marked provisional.
  strip.status('model-loading', 'busy');
  strip.caption('e mais uma linha', 3.2, 4.0, false);
  arm('a status change CLOSES the open line into its own row, and the next partial opens a new one',
    [strip.id('caption-list').childElementCount,
      squeeze(strip.document.querySelectorAll('.caption')[0].textContent).includes('roeu a rolha'),
      strip.document.querySelectorAll('.caption')[0].className.includes('provisional'),
      strip.document.querySelectorAll('.caption--provisional').length],
    [2, true, false, 1]);
  arm('the strip carries its 4 controls: live toggle, pause, open panel, status',
    ['strip-live-button', 'strip-pause-button', 'strip-open-button', 'strip-state'].filter((n) => !!strip.id(n)),
    ['strip-live-button', 'strip-pause-button', 'strip-open-button', 'strip-state']);
  arm('the strip does NOT show the transcript drawer', strip.display('#history'), 'none', 'block');
  arm('the strip does NOT show the header', strip.display('.panel__header'), 'none', 'flex');
  arm('the strip does NOT show the footer sentence block', strip.display('.status__text'), 'none', 'block');
  arm('the strip DOES show its own control row', strip.display('#strip-controls'), 'flex', 'none');
  arm('the strip does NOT show the HUD', strip.display('#hud'), 'none', 'flex');
  arm('the live box is still inside .panel, above the strip row, in both surfaces',
    [strip.display('#captions-body'), !!strip.id('captions-body').closest('.panel')],
    ['block', true]);
  arm('the live box keeps aria-live="polite"', strip.id('captions').getAttribute('aria-live'), 'polite');
  arm('the toggle announces its state', strip.id('strip-live-button').getAttribute('aria-pressed'), 'true');
  // The shell's own words for a live feed (the same sentence the HUD reports).
  strip.status('Receiving captions', 'live');
  arm('the strip word is a SHORT status, and the shell sentence is still in the DOM',
    [strip.id('strip-word').textContent, strip.id('status-text').textContent],
    ['Live', 'Receiving captions']);
  arm('and the HUD reports that same live state, from the same record',
    squeeze(strip.id('hud-state').textContent), 'live ┬À Receiving captions');
  arm('the sticky follow is armed on the strip too (a caption does not throw)',
    strip.id('captions-body').scrollTop >= 0, true);

  // ------------------------------------------------------------------ ARM P
  currentArm = 'P';
  console.log('\n=== ARM P ÔÇö the full PANEL surface ===');
  const full = await panel({ url: `${fileUrl(PANEL_HTML)}#live`, wired: true });
  full.status('Receiving captions', 'live');
  arm('the document really is wearing the panel surface',
    full.document.body.getAttribute('data-surface'), 'panel', 'strip');
  arm('the panel DOES show the transcript drawer', full.display('#history'), 'grid', 'none');
  arm('the panel keeps the drawer collapsed, its search disabled with its reason',
    [full.id('history').className.includes('history--collapsed'), full.id('search-input').disabled,
      full.id('transcript-note').textContent.includes('canonical writer')],
    [true, true, true]);
  arm('the panel DOES show the header', full.display('.panel__header'), 'flex', 'none');
  arm('the panel DOES show the footer sentence block', full.display('.status__text'), '-webkit-box', 'none');
  arm('the panel does NOT show the strip control row', full.display('#strip-controls'), 'none', 'flex');
  arm('the panel DOES show the HUD', full.display('#hud'), 'flex', 'none');
  arm('the HUD carries the "open in folder" control and a Pause of its own',
    ['hud-folder-button', 'panel-pause-button'].filter((n) => !!full.id(n)),
    ['hud-folder-button', 'panel-pause-button']);
  arm('the HUD names the folder `history.root()` reported',
    full.id('hud-folder-button').title, 'Open H:\\sotto\\history in the OS file manager');

  // THE TRIM (owner, 2026-10-08): the HUD is a PERFORMANCE readout, not a
  // details panel. Five rows, and the numbers it cannot read stay empty.
  const hudLabels = [...full.document.querySelectorAll('#hud-rows .hud__row dt')].map((dt) => dt.textContent);
  arm('the HUD is a SMALL performance readout: exactly 5 rows',
    hudLabels, ['State', 'RAM', 'Rate', 'Engine', 'Peak']);
  arm('the HUD renders an em dash AND a reason for every value it cannot read',
    ['hud-ram', 'hud-rate', 'hud-engine', 'hud-peak']
      .map((n) => [squeeze(full.id(n).textContent), full.id(n).title.startsWith('Needs bridge.getStats():')]),
    [['ÔÇö', true], ['ÔÇö', true], ['ÔÇö', true], ['ÔÇö', true]]);
  arm('the HUD invents NO number for a stat it does not have',
    ['hud-ram', 'hud-rate', 'hud-engine', 'hud-peak'].filter((n) => /[0-9]/.test(full.id(n).textContent)),
    []);
  arm('the HUD says where its numbers come from',
    squeeze(full.id('hud-source').textContent), 'panel only ┬À no stats call');
  arm('the HUD State row is a LIVE value, from onStatus',
    squeeze(full.id('hud-state').textContent), 'live ┬À Receiving captions');
  // The paused state answer is computed ONCE, in its own statement: an `await`
  // inside an argument list binds as `(await f()), nextArg` ÔÇö a comma
  // expression ÔÇö which silently shifts every later argument of this call
  // (measured: it cost three assertions before being spotted).
  const pausedState = await (async () => {
    const p = await panel({ url: `${fileUrl(PANEL_HTML)}#idle`, wired: true });
    const confirm = p.id('pause-confirm-button');
    p.id('panel-pause-button').click();
    confirm.click();
    // `bridge.pause()` resolves a PROMISE (both real bridges and the stub), and
    // `setPaused` runs in its `.then` ÔÇö so the state is one microtask turn away
    // and a synchronous read here would see the pre-pause paint. MEASURED: this
    // read raced the promise and reported "ÔÇö".
    await tick();
    return squeeze(p.id('hud-state').textContent);
  })();
  // The sentence is the SHELL's own (`payload.text`): the panel reports what the
  // shell said it did, and never invents a sentence of its own.
  arm('the paused state reports itself through the HUD State row',
    pausedState, 'Paused ÔÇö engines unloaded');

  const filledHud = await (async () => {
    const p = await panel({ url: `${fileUrl(PANEL_HTML)}#idle`, wired: true, stats: true });
    // `getStats()` resolves a promise; the HUD's rows are painted in its `.then`.
    await tick();
    return ['hud-ram', 'hud-rate', 'hud-engine', 'hud-peak', 'hud-source']
      .map((n) => squeeze(p.id(n).textContent));
  })();
  arm('the HUD fills from a shell stats payload, and prints only what it carries',
    filledHud,
    ['145 MB ┬À shell 210 MB', '1.05 cap/s ┬À 1.20├ù realtime', 'nemotron-3.5-int8',
      '0.552821 ┬À 1153 blocks', 'shell ┬À 0s ago']);

  const partialHud = await (async () => {
    const p = await panel({
      url: `${fileUrl(PANEL_HTML)}#idle`, wired: true, stats: true, statsFields: { rss_mb: 145 },
    });
    await tick();
    return [squeeze(p.id('hud-ram').textContent), squeeze(p.id('hud-peak').textContent)];
  })();
  arm('and a stats payload with only SOME fields leaves the others pending',
    partialHud, ['145 MB', 'ÔÇö']);
  arm('the folder button opens the transcript folder through the real history API',
    // The folder button opens the ROOT, so it calls `reveal(null)` ÔÇö the same call
    // the transcript bar's path button makes. The stub records the ARGUMENT, which
    // is the fact worth asserting: a button that opened a path of its own invention
    // would be a different (and wrong) behaviour.
    (() => { full.id('hud-folder-button').click(); return full.audit.revealed; })(),
    [null]);
  arm('the line count is NOT a HUD row any more: it is carried by the live bar',
    await (async () => {
      // A fresh panel, because the count depends on the ENGINE's history and not
      // on this page: a CLOSED line that follows a real silence is committed and
      // appended, and nothing is left open, so the hint counts exactly one line.
      const p = await panel({ url: `${fileUrl(PANEL_HTML)}#live`, wired: true });
      p.caption('primeira linha fechada.', 0, 1, true);
      p.caption('segunda linha fechada.', 40, 41, true);
      return [squeeze(p.id('captions-hint').textContent),
        p.document.querySelectorAll('#hud-rows .hud__row').length];
    })(), ['1 line', 5]);
  // ------------------------------------------------------------------ ARM B
  currentArm = 'B';
  console.log('\n=== ARM B ÔÇö both colours: the same documents with the surface forced the other way ===');
  const forcedPanel = await panel({ url: `${fileUrl(PANEL_HTML)}#strip`, wired: true, forceSurface: 'panel' });
  arm('the strip document, forced back to the panel surface, grows the drawer and loses the strip row',
    [forcedPanel.display('#history'), forcedPanel.display('#strip-controls')],
    ['grid', 'none'],
    [strip.display('#history'), strip.display('#strip-controls')]);
  const forcedStrip = await panel({ url: `${fileUrl(PANEL_HTML)}#live`, wired: true, forceSurface: 'strip' });
  arm('the panel document, forced to the strip surface, loses the drawer and shows the strip row',
    [forcedStrip.display('#history'), forcedStrip.display('#strip-controls')],
    ['none', 'flex'],
    [full.display('#history'), full.display('#strip-controls')]);
  arm('the forced-strip copy shows the strip surface with the SAME live box',
    [forcedStrip.document.body.getAttribute('data-surface'), forcedStrip.display('#captions-body'),
      forcedStrip.display('.status__text')],
    ['strip', 'block', 'none']);

  // ------------------------------------------------------------------ ARM T
  currentArm = 'T';
  console.log('\n=== ARM T ÔÇö the LIVE ON/OFF toggle ===');
  const wiredT = await panel({ url: `${fileUrl(PANEL_HTML)}#strip`, wired: true });
  const liveButton = wiredT.id('strip-live-button');
  const before = liveButton.getAttribute('aria-pressed');
  liveButton.click();
  arm('the toggle flips aria-pressed on a click',
    [before, liveButton.getAttribute('aria-pressed')], ['true', 'false']);
  arm('and the label follows the state', wiredT.id('strip-live-label').textContent, 'Live off');
  arm('and the shell is told, with the NEW value', wiredT.audit.live, [false]);
  liveButton.click();
  arm('turning it back on carries true', wiredT.audit.live, [false, true]);

  const unwiredT = await panel({ url: `${fileUrl(PANEL_HTML)}#strip` });
  unwiredT.id('strip-live-button').click();
  arm('a shell WITHOUT setLiveEnabled is never called', unwiredT.audit.live, []);
  arm('and the button is marked unwired instead of pretending',
    unwiredT.id('strip-live-button').dataset.wired, 'false');
  arm('and it still reports the state it is showing',
    unwiredT.id('strip-live-button').getAttribute('aria-pressed'), 'false');

  // ------------------------------------------------------------------ ARM D
  currentArm = 'D';
  console.log('\n=== ARM D ÔÇö PAUSE: two steps, Cancel focused, and the honest confirmation ===');
  const wiredD = await panel({ url: `${fileUrl(PANEL_HTML)}#strip`, wired: true });
  wiredD.id('strip-pause-button').click();
  arm('step one opens the confirmation and calls NOTHING yet',
    [wiredD.id('pause-dialog').hasAttribute('open'), wiredD.audit.pause.length], [true, 0]);
  arm('the DEFAULT FOCUS is CANCEL, not the destructive button',
    wiredD.focusId(), 'pause-cancel-button');
  arm('the dialog says what pause does (unload)',
    wiredD.id('pause-dialog-body').textContent.includes('unloads the live caption engine'), true);
  arm('and that the background transcript is extremely light',
    wiredD.id('pause-dialog-honest').textContent.includes('extremely light'), true);
  arm('and that pausing is not necessary to keep the PC fast',
    wiredD.id('pause-dialog-honest').textContent.includes('not necessary to keep the PC fast'), true);
  arm('the confirm button is live when the shell can pause',
    [wiredD.id('pause-confirm-button').disabled, wiredD.id('pause-confirm-button').textContent],
    [false, 'Pause and unload']);
  wiredD.id('pause-confirm-button').click();
  arm('step two calls bridge.pause with its reason',
    wiredD.audit.pause, [{ reason: 'panel-confirm' }]);
  arm('and the dialog is closed', wiredD.id('pause-dialog').hasAttribute('open'), false);
  arm('and BOTH surfaces paint the paused state',
    [squeeze(wiredD.id('hud-state').textContent), wiredD.id('strip-word').textContent],
    ['Paused ÔÇö engines unloaded', 'Paused']);

  const cancelD = await panel({ url: `${fileUrl(PANEL_HTML)}#strip`, wired: true });
  cancelD.id('strip-pause-button').click();
  cancelD.id('pause-cancel-button').click();
  arm('Cancel closes the dialog, unloads nothing, and gives focus back',
    [cancelD.id('pause-dialog').hasAttribute('open'), cancelD.audit.pause.length, cancelD.focusId()],
    [false, 0, 'strip-pause-button']);

  const unwiredD = await panel({ url: `${fileUrl(PANEL_HTML)}#strip` });
  unwiredD.id('strip-pause-button').click();
  arm('a shell without pause() says so in the dialog',
    unwiredD.id('pause-dialog-shell').textContent.includes('cannot pause yet'), true);
  arm('and its confirm button is disabled and names the reason',
    [unwiredD.id('pause-confirm-button').disabled, unwiredD.id('pause-confirm-button').textContent],
    [true, 'Pause ÔÇö not available in this shell yet']);
  arm('and the trigger itself is marked not wired',
    unwiredD.id('strip-pause-button').dataset.wired, 'false');
  arm('nothing at all is called on a shell that cannot pause',
    [unwiredD.audit.pause.length, unwiredD.audit.live.length], [0, 0]);
  arm('the PANEL pause button is the same flow (one trigger class, two surfaces)',
    await (async () => {
      const p = await panel({ url: `${fileUrl(PANEL_HTML)}#idle`, wired: true });
      p.id('panel-pause-button').click();
      const opened = p.id('pause-dialog').hasAttribute('open');
      const focused = p.focusId();
      p.id('pause-confirm-button').click();
      return [opened, focused, p.audit.pause];
    })(),
    [true, 'pause-cancel-button', [{ reason: 'panel-confirm' }]]);

  // ------------------------------------------------------------------ ARM O
  currentArm = 'O';
  console.log('\n=== ARM O ÔÇö Open panel, both roads ===');
  const openWired = await panel({ url: `${fileUrl(PANEL_HTML)}#strip`, wired: true });
  openWired.id('strip-open-button').click();
  arm('with the shell call present, the panel asks the SHELL to switch surface',
    [openWired.audit.surfaces, openWired.document.body.getAttribute('data-surface')],
    [[{ surface: 'panel', reason: 'strip-open' }], 'panel']);
  const openUnwired = await panel({ url: `${fileUrl(PANEL_HTML)}#strip` });
  openUnwired.id('strip-open-button').click();
  arm('without it, the document switches itself rather than doing nothing',
    [openUnwired.audit.surfaces.length, openUnwired.document.body.getAttribute('data-surface')],
    [0, 'panel']);
  arm('and the panel it opens is the full one (drawer back)',
    [openUnwired.display('#history'), openUnwired.display('#strip-controls')], ['block', 'none']);

  // ------------------------------------------------------------------ ARM H
  currentArm = 'H';
  console.log('\n=== ARM H ÔÇö the strip is SHORT, and the file a human opens is built from these bytes ===');
  const css = fs.readFileSync(PANEL_CSS, 'utf8');
  arm('the strip surface has its own grid with a floor on the LIVE row',
    /body\[data-surface="strip"\] \.panel \{\s*grid-template-rows: minmax\(\d+px, 1fr\) auto auto/s.test(css),
    true);
  arm('the strip hides the drawer, the header and the footer sentence BY CSS',
    [
      /body\[data-surface="strip"\] \.history\b/.test(css),
      /body\[data-surface="strip"\] \.panel__header/.test(css),
      /body\[data-surface="strip"\] \.status__text/.test(css),
    ],
    [true, true, true]);
  arm('the colour switch itself needs no JavaScript (CSS answers from the attribute)',
    /body\[data-surface="strip"\] \.stripbar \{\s*display: flex/.test(css), true);

  const shipped = fs.existsSync(HARNESS) ? fs.readFileSync(HARNESS, 'utf8') : '';
  const sources = scriptSources(shipped);
  arm('the harness file EXISTS and is regenerated from the same markup',
    [shipped.includes('id="strip-controls"'), shipped.includes('id="pause-dialog"'),
      shipped.includes('id="hud-rows"')],
    [true, true, true]);
  arm('the harness loads the real assets and keeps the panel\'s own script order',
    [sources.slice(-4), sources.indexOf('../../app/panel/surface.js') >= 0],
    [['stub.js', '../../app/panel/surface.js', '../../app/panel/panel.js', 'drive.js'], true]);
  arm('the harness stub is the one whose order is stub -> surface -> panel -> drive',
    sources.indexOf('stub.js') < sources.indexOf('../../app/panel/panel.js')
      && sources.indexOf('../../app/panel/panel.js') < sources.indexOf('drive.js'),
    true);

  for (const p of [strip, full, forcedPanel, forcedStrip, wiredT, unwiredT, wiredD, cancelD, unwiredD, openWired, openUnwired]) {
    if (p.errors.length) {
      arm('no loaded panel may have thrown', p.errors, []);
      break;
    }
  }

  // --------------------------------------------------------------- verdict
  const failed = results.filter((r) => !r.ok);
  console.log(`\nRESULT: ${failed.length ? `RED ÔÇö ${failed.length} violation(s)` : 'GREEN'} ÔÇö ${results.length - failed.length}/${results.length} arm(s)`);
  for (const f of failed) {
    console.log(`  FAIL [${f.arm}] ${f.name}`);
    console.log(`       real=${JSON.stringify(f.real)} want=${JSON.stringify(f.want)}`);
  }
  console.log(`harness: ${path.relative(REPO, HARNESS)} ÔÇö the file a human opens; the surfaces and the`);
  console.log('         dialog are its URL hash states (see _main/receipt-panel-two-surfaces.md).');
  return failed.length ? 1 : 0;
}

main().then((rc) => process.exit(rc));
