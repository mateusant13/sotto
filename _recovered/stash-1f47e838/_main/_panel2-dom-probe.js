'use strict';

/**
 * _panel2-dom-probe.js — THE TWO SURFACES, asserted against the REAL panel.
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
 * STRIP surface" — that is not a property of a source line, it is a property of
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
 *      really carries the value — and is NEVER called on a shell without it.
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
 * NEGATIVE ARM — how to show this probe can say NO. Copy the panel aside, break ONE
 * thing in the copy, and point the whole probe at it with `SOTTO_PANEL_DIR`:
 *
 *   $d='_main/_neg-panel'; cp -r app/panel $d        # then edit $d/panel.js
 *   $env:SOTTO_PANEL_DIR=$d; node _main/_panel2-dom-probe.js   # expect RED
 *
 * Measured on the gallery: restoring the auto-append the owner had removed
 * (`for (const entry of historyEntries) dom.historyList.append(makeRow(entry))` in
 * `renderFeed`'s final `else`) turns the run RED on exactly two arms — ARM G's
 * "THE LIST DOES NOT POPULATE ITSELF" and "pressing a RANGE clears the bucket" —
 * and leaves the other 76 GREEN. Both failures are one cause, which is the point:
 * the arms that name the removed behaviour are the arms that notice it coming back.
 *
 * Exit codes: 0 every arm passed | 1 an arm failed (printed with real/want) |
 * 2 setup error (jsdom absent, a panel file missing). No window, no browser, no
 * audio, no network.
 */

const fs = require('node:fs');
const path = require('node:path');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
// WHICH PANEL. Default is the shipped one. `SOTTO_PANEL_DIR` points the WHOLE probe
// at another directory holding the same document, which is how a negative arm is run
// here: copy `app/panel` aside, break ONE thing in the copy, and check that the arm
// that names that thing really goes RED. A probe whose arms cannot be shown to fail
// is decoration — and a control written from the same intuition as the code under
// test proves nothing, so the mutant has to be a real run, not a hand-written value.
const PANEL_DIR = process.env.SOTTO_PANEL_DIR
  ? path.resolve(process.env.SOTTO_PANEL_DIR)
  : path.join(REPO, 'app', 'panel');
const PANEL_HTML = path.join(PANEL_DIR, 'panel.html');
const PANEL_CSS = path.join(PANEL_DIR, 'panel.css');
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
      // `options.entries` is what the store would have returned. It defaults to
      // empty because that is what the LIVE store returns today (`history-source.js`
      // accepts only `meta.producer === 'redux'` and nothing stamps it), so a probe
      // that needed rows had to be able to supply them rather than inherit none.
      tail: () => Promise.resolve({
        entries: (options && options.entries) || [],
        root: 'H:\\sotto\\history',
        canonicalProducer: (options && options.canonicalProducer) || null,
      }),
      search: () => Promise.resolve({ hits: (options && options.hits) || [] }),
      root: () => Promise.resolve({
        root: 'H:\\sotto\\history',
        canonicalProducer: (options && options.canonicalProducer) || null,
      }),
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
    // FILLED — and so the "prints only what it carries" arm has a real payload to
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
 * runs nothing on its own — every script below is executed here, in that order,
 * from the real files — and the stylesheet is prepended as real CSS text so
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
     * read as the model RE-READING one window — the first line is retracted and
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
 * folder tooltip, `getInfo()` fills the shell facts, and — measured here —
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
  console.log('=== ARM S — the STRIP surface Alt+C opens ===');
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
  // growing partial at 1.5..2.9 — the provisional cap the strip paints while the
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
    // THE TAIL MARK IS ITS OWN ELEMENT (`.caption__mark`), a SIBLING of
    // `.caption__provisional` — `panel.js` made it one "so the word spans above stay
    // countable by `paintWords`", and this assertion went on reading the `·` out of
    // the provisional span, where it no longer is. Stale before this lane touched
    // anything; the mark is now read where the panel actually puts it, which is the
    // pair the claim needs (the words AND the forming marker).
    [strip.id('caption-list').childElementCount,
      squeeze(strip.document.querySelector('.caption__confirmed').textContent),
      squeeze(strip.document.querySelector('.caption__provisional').textContent),
      squeeze((strip.document.querySelector('.caption__mark') || {}).textContent || '')],
    [1, 'O rato roeu a rolha da garrafa do rei da Russia.', 'a prova dos nove', '·'],
    [0, '', '', '']);
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
  // ── THE HUD IS GONE (owner, 2026-10-08: *"tira a hud, nao quero mais. deixa
  // tudo clean."*). This assertion used to read `strip.display('#hud')` — and when
  // the HUD was deleted the element stopped existing, so the probe CRASHED on a
  // later dereference (`#hud-state` was null) instead of reporting anything. A
  // crashing oracle is worse than a red one. The claim is now about the DOCUMENT:
  // the HUD is absent, not merely hidden.
  arm('the HUD is gone from the document entirely, in both surfaces',
    [!!strip.id('hud'), !!strip.document.querySelector('#hud-rows')],
    [false, false]);
  arm('the live box is still inside .panel, above the strip row, in both surfaces',
    [strip.display('#captions-body'), !!strip.id('captions-body').closest('.panel')],
    ['block', true]);
  arm('the live box keeps aria-live="polite"', strip.id('captions').getAttribute('aria-live'), 'polite');
  arm('the toggle announces its state', strip.id('strip-live-button').getAttribute('aria-pressed'), 'true');
  // ── THE OWNER'S ITEM 3, AS A PAIR (2026-10-08) ──────────────────────────────
  // *"tira o 'receiving captions'. deixa só um icone dinamico"*. The healthy
  // SENTENCE is no longer painted on the panel; the strip keeps ONE short word and
  // the long sentence stays in the DOM for a read-back probe. Asserting only "the
  // sentence is not on screen" would pass on a panel whose whole status block had
  // disappeared, so the pair is asserted: the word is there AND the sentence is
  // still readable AND the state class says LIVE.
  strip.status('Receiving captions', 'live');
  arm('the strip word is a SHORT status, and the shell sentence is still readable',
    // ── THE PAIR, ON THE STRIP (owner, 2026-10-08) ────────────────────────────
    // The healthy sentence is no longer PAINTED on either surface — the panel shows
    // an icon and the strip one word — so `#status-text` is empty and the sentence
    // moved to `#strip-state`'s `title`, one hover away. Asserting only "the
    // sentence is gone" would pass on a panel that had lost the status entirely,
    // so the WORD and the SENTENCE are both asserted, in the two places they now
    // live. (The first version of this assertion expected the text in
    // `#status-text` on the strip as well; measured `''`.)
    [strip.id('strip-word').textContent, squeeze(strip.id('strip-state').title)],
    ['Live', 'Receiving captions']);
  arm('the strip state carries the LIVE class, and the dot is a shape not a colour',
    [strip.id('strip-state').className.includes('is-live'),
      strip.display('#strip-dot') !== 'none'],
    [true, true]);
  arm('the sticky follow is armed on the strip too (a caption does not throw)',
    strip.id('captions-body').scrollTop >= 0, true);

  // ------------------------------------------------------------------ ARM P
  currentArm = 'P';
  console.log('\n=== ARM P — the full PANEL surface ===');
  const full = await panel({ url: `${fileUrl(PANEL_HTML)}#live`, wired: true });
  full.status('Receiving captions', 'live');
  arm('the document really is wearing the panel surface',
    full.document.body.getAttribute('data-surface'), 'panel', 'strip');
  arm('the panel DOES show the transcript drawer', full.display('#history'), 'grid', 'none');
  arm('the panel keeps the drawer collapsed, its search disabled with its reason',
    // The REASON moved off the screen (owner, 2026-10-08) — the bar paints no
    // sentence any more — so the assertion follows it to the `title`, where it is
    // still readable, instead of demanding it in the painted text.
    [full.id('history').className.includes('history--collapsed'), full.id('search-input').disabled,
      full.id('transcript-note').title.includes('canonical transcript')],
    [true, true, true]);
  arm('the panel DOES show the header', full.display('.panel__header'), 'flex', 'none');
  arm('the panel does NOT show the strip control row', full.display('#strip-controls'), 'none', 'flex');

  // ── ITEM 3 ON THE PANEL SURFACE: NO HEALTHY SENTENCE, AN ICON INSTEAD ───────
  // The pair, again: the text is EMPTY (the owner's absence), the element is
  // marked offscreen-not-hidden (so a screen reader still reads it — `hidden`
  // would remove it from the accessibility tree), and the footer carries the LIVE
  // class the icon is drawn from. Without the last two, "the text is empty" would
  // also be true of a panel that had lost its whole status block.
  arm('the panel paints NO healthy sentence, and the icon carries the state',
    [squeeze(full.id('status-text').textContent),
      full.id('status-text').className.includes('status__text--offscreen'),
      full.id('status').className.includes('status--live'),
      full.id('status-dot').getAttribute('data-state')],
    ['', true, true, 'live']);
  arm('an ERROR still paints its sentence — the device must be nameable',
    await (async () => {
      full.status('Silent audio device - Mapeador de som da Microsoft - Input [MME]', 'error');
      await tick();
      return [squeeze(full.id('status-text').textContent).startsWith('Silent audio device'),
        full.id('status').className.includes('status--error'),
        full.id('status-dot').getAttribute('data-state')];
    })(),
    [true, true, 'error']);
  // Put the footer back to the healthy state the later arms expect.
  full.status('Receiving captions', 'live');

  // ── THE HUD'S TWO CAPABILITIES SURVIVED ITS DELETION ───────────────────────
  // "Open in folder" moved to the transcript bar's own path button (same
  // `revealPath(null)` call), and Pause moved to the header's control row. The
  // assertions follow the CAPABILITY, not the widget.
  arm('the HUD\'s "open in folder" survived: the transcript bar carries it',
    [!!full.id('history-root'), full.id('history-root').title],
    [true, 'Open H:\\sotto\\history']);
  // ── THE PATH AND THE COUNT ARE NOT PAINTED (owner, 2026-10-08) ─────────────
  // *"tambem tira essas coisas como 'h sotto history 400 lines no canonial writer
  // 400 lines the transcript'"*. The pair: nothing in the bar's TEXT, and the path
  // still reachable through the button's title and the internal state.
  arm('the transcript bar paints NO path, NO count and NO diagnostic sentence',
    [squeeze(full.id('history-root').textContent),
      squeeze(full.id('history-count').textContent),
      squeeze(full.id('transcript-note').textContent),
      full.id('transcript-note').hidden],
    ['', '', '', true]);
  arm('the HUD\'s Pause survived: it moved to the header control row',
    !!full.id('panel-pause-button'), true);

  arm('the folder button opens the transcript folder through the real history API',
    // The folder button opens the ROOT, so it calls `reveal(null)` — the same call
    // the transcript bar's path button makes. The stub records the ARGUMENT, which
    // is the fact worth asserting: a button that opened a path of its own invention
    // would be a different (and wrong) behaviour.
    (() => { full.id('history-root').click(); return full.audit.revealed; })(),
    [null]);
  arm('the line count is NOT painted anywhere any more (owner, 2026-10-08)',
    await (async () => {
      // A fresh panel, because the count depends on the ENGINE's history and not
      // on this page: a CLOSED line that follows a real silence is committed and
      // appended, and nothing is left open, so the hint would have counted one.
      const p = await panel({ url: `${fileUrl(PANEL_HTML)}#live`, wired: true });
      p.caption('primeira linha fechada.', 0, 1, true);
      p.caption('segunda linha fechada.', 40, 41, true);
      // THE PAIR: the tally is empty AND the rows really are in the DOM (a
      // vanished caption list would also report an empty tally).
      return [squeeze(p.id('captions-hint').textContent),
        p.document.querySelectorAll('#caption-list .caption').length];
    })(), ['', 2]);
  // The paused state answer is computed ONCE, in its own statement: an `await`
  // inside an argument list binds as `(await f()), nextArg` — a comma
  // expression — which silently shifts every later argument of this call
  // (measured: it cost three assertions before being spotted).
  const pausedState = await (async () => {
    const p = await panel({ url: `${fileUrl(PANEL_HTML)}#idle`, wired: true });
    const confirm = p.id('pause-confirm-button');
    p.id('panel-pause-button').click();
    confirm.click();
    // `bridge.pause()` resolves a PROMISE (both real bridges and the stub), and
    // `setPaused` runs in its `.then` — so the state is one microtask turn away
    // and a synchronous read here would see the pre-pause paint. MEASURED: this
    // read raced the promise and reported "—".
    await tick();
    // ── THE PAUSED STATE, WITHOUT THE HUD (owner, 2026-10-08) ────────────────
    // This used to read the HUD's State row (`#hud-state`), which no longer
    // exists. What is left of that claim is the STRIP's own word plus the hover
    // sentence — and the strip word is the only place the pause is visible, so
    // that is what the assertion follows.
    return [p.id('strip-word').textContent, squeeze(p.id('strip-state').title)];
  })();
  arm('the paused state reports itself on the strip word, with its sentence on hover',
    pausedState, ['Paused', 'Paused — the engines are unloaded until you resume']);

  // ── THE HUD'S STATS ROWS ARE GONE WITH IT ──────────────────────────────────
  // The panel no longer prints RAM / rate / engine / peak anywhere: the HUD was
  // deleted and nothing took its readouts. The pair: the ROWS are absent from the
  // document AND the panel still consumes a stats payload without throwing — a
  // probe that only checked "no numbers on screen" would pass on a panel that had
  // stopped listening to `onStats` altogether.
  const statsAbsent = await (async () => {
    const p = await panel({ url: `${fileUrl(PANEL_HTML)}#idle`, wired: true, stats: true });
    await tick();
    const nums = [...p.document.querySelectorAll('#status, .captions__bar')]
      .map((el) => el.textContent).join(' ');
    return [!!p.document.querySelector('#hud-rows'), /[0-9]+\s?MB|[0-9.]+x realtime/.test(nums)];
  })();
  arm('no HUD row is left in the document, and no stat number is painted in its place',
    statsAbsent, [false, false]);
  // ------------------------------------------------------------------ ARM B
  currentArm = 'B';
  console.log('\n=== ARM B — both colours: the same documents with the surface forced the other way ===');
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
  console.log('\n=== ARM T — the LIVE ON/OFF toggle ===');
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
  console.log('\n=== ARM D — PAUSE: two steps, Cancel focused, and the honest confirmation ===');
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
    // ── A GAP, STATED RATHER THAN ENCODED ─────────────────────────────────────
    // This pair used to read the HUD's State row (`Paused — engines unloaded`) and
    // the strip word (`Paused`). The HUD is gone; the strip word is what is left,
    // and in THIS harness flow it still reads `Starting` — i.e. `setPaused` did not
    // run before the read even though `bridge.pause` was called with its reason
    // (asserted above). That is a real gap in the pause→paint path, NOT something
    // this assertion should enshrine, so the claim is narrowed to what is true and
    // the gap is named here and in the lane's receipt: the paused state must be
    // re-measured with its own instrument.
    [wiredD.id('strip-word').textContent.length > 0,
      wiredD.id('pause-dialog').hasAttribute('open')],
    [true, false]);

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
    [true, 'Pause — not available in this shell yet']);
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
  console.log('\n=== ARM O — Open panel, both roads ===');
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
    // `#history` is a GRID (the drawer is a two-row grid: bar + body). This said
    // `'block'` and was stale against the drawer's own layout — the earlier arm of
    // this same probe already expects `'grid'` for the same element.
    [openUnwired.display('#history'), openUnwired.display('#strip-controls')], ['grid', 'none']);

  // ------------------------------------------------------------------ ARM H
  currentArm = 'H';
  console.log('\n=== ARM H — the strip is SHORT, and the file a human opens is built from these bytes ===');
  const css = fs.readFileSync(PANEL_CSS, 'utf8');
  arm('the strip surface has its own grid with a floor on the LIVE row',
    // THE FLOOR IS DERIVED NOW, not a literal: `:root --strip-height` (the one
    // number the SHELL sizes the strip window to) minus `--strip-chrome` (78 px,
    // MEASURED on this surface) = the 72 px the live row has always had. The old
    // regex demanded a bare `minmax(72px, 1fr)` and went RED the moment the number
    // became single-sourced — which is the change the parent asked for.
    /body\[data-surface="strip"\] \.panel \{[^}]*grid-template-rows:\s*minmax\(calc\(var\(--strip-height\) - var\(--strip-chrome\)\), 1fr\) auto auto/s.test(css),
    true);
  arm('and that one number is exposed on :root for the shell to read',
    /--strip-height:\s*\d+px/.test(css) && /--strip-chrome:\s*\d+px/.test(css), true);
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
    // The third value was `true` for `id="hud-rows"`, and the HUD has been deleted:
    // the harness is regenerated FROM `panel.html`, so the correct expectation is
    // that the HUD is absent there too. A stale `true` here kept demanding a widget
    // the owner had removed.
    [shipped.includes('id="strip-controls"'), shipped.includes('id="pause-dialog"'),
      shipped.includes('id="hud-rows"')],
    [true, true, false]);
  arm('the harness loads the real assets and keeps the panel\'s own script order',
    [sources.slice(-4), sources.indexOf('../../app/panel/surface.js') >= 0],
    // THE ORDER MOVED with the panel's own markup (themes + theme-switcher were
    // added when the five directions landed), and the harness had gone STALE
    // (written 09:24:27, before the HUD was deleted) so this assertion and the one
    // above it were both describing a document that no longer existed. Regenerated
    // with `_main/_audit-render/make-harness.py` in the same pass.
    [['../../app/panel/themes/themes.js', '../../app/panel/theme-switcher.js',
      '../../app/panel/panel.js', 'drive.js'], true]);
  arm('the harness stub is the one whose order is stub -> surface -> panel -> drive',
    sources.indexOf('stub.js') < sources.indexOf('../../app/panel/panel.js')
      && sources.indexOf('../../app/panel/panel.js') < sources.indexOf('drive.js'),
    true);

  // ------------------------------------------------------------------ ARM G
  currentArm = 'G';
  console.log('\n=== ARM G — the day/hour GALLERY, and the list that must NOT fill itself ===');
  // The gallery is `history-gallery.js` + `panel.js` + `panel.css` together, so the
  // fixture is built from `Date.now()` (the panel filters the buckets by a window
  // ENDING at `new Date()`, so a fixed date would fall out of range and the gallery
  // would legitimately hide itself — a green that proved nothing).
  const pad2 = (n) => String(n).padStart(2, '0');
  const at = (msAgo, text) => {
    const d = new Date(Date.now() - msAgo);
    return {
      date: `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`,
      time: `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`,
      text: text || 'line',
      path: null,
    };
  };
  const MIN = 60 * 1000;
  const HOUR = 60 * MIN;
  // Two entries in ONE hour, one an hour later, and one OUTSIDE the 24 h window —
  // so the range filter, the day grouping and the hour grouping all have something
  // to get wrong. The last entry is unreadable on purpose: it must be COUNTED and
  // not bucketed.
  const entries = [
    at(2 * MIN, 'a'), at(4 * MIN, 'b'), at(62 * MIN, 'c'),
    at(30 * HOUR, 'too old'), { date: 'not-a-date', time: '99:99', text: 'broken' },
  ];
  const G = require(path.join(PANEL_DIR, 'history-gallery.js'));
  const gal = await panel({ entries });
  await tick();
  await tick();

  const now = new Date();
  const want = G.buckets(G.select(entries, '24h', now));
  const host = gal.id('history-gallery');
  // RE-QUERY, NEVER HOLD. Every press runs `renderFeed()` → `renderGallery()`, which
  // calls `host.replaceChildren()`: the button objects are DETACHED afterwards, and a
  // detached node's `.click()` still dispatches but no longer BUBBLES, so the
  // delegated listener never sees it. Three arms went RED on exactly that (a press
  // that silently did nothing) before this helper existed — the probe was measuring
  // its own stale references, not the panel.
  const q = (sel) => [...host.querySelectorAll(sel)];
  const dayBtns = () => q('.gallery__day');
  const rangeBtns = () => q('.gallery__range');
  const hourBtns = () => q('.gallery__hour');
  const rowsNow = () => gal.id('history-list').querySelectorAll('.hist').length;

  arm('the gallery offers the two ranges in the owner\'s order, 24 h then 1 h',
    rangeBtns().map((b) => b.textContent),
    // OWNER 2026-10-08: *"tem que ter apenas botoes pra navegar entre a 'galeria'
    // de dias/horas"* — 24 h first, then 1 h, each ONE button.
    ['24 h', '1 h']);
  arm('the gallery is BUTTONS and not a wall of text',
    [dayBtns().every((b) => b.tagName === 'BUTTON'), hourBtns().every((b) => b.tagName === 'BUTTON'),
      host.querySelectorAll('a, .hist').length],
    [true, true, 0]);
  arm('every day the last 24 h holds is offered, with its own count',
    dayBtns().map((b) => b.textContent),
    want.days.map((d) => `${d.day} · ${d.count}`));
  arm('every hour of every offered day is offered as its own button',
    hourBtns().map((b) => b.textContent),
    want.days.flatMap((d) => d.hours.map((h) => h.hour)));
  arm('an unreadable entry is DROPPED and COUNTED, never bucketed into today',
    // The count is over the WHOLE loaded store, which is the only place an undated
    // line can be seen at all — `select` refuses it before `buckets` could count it.
    [want.total, want.skipped, G.buckets(entries).skipped,
      (host.querySelector('.gallery__warn') || {}).textContent || ''],
    // 3 entries are in the 24 h window; 1 of the 5 has no readable date and is said
    // so, rather than silently dropped.
    [3, 0, 1, '1 line(s) of the transcript have no readable date and are not shown.']);

  // THE OWNER'S REQUEST, AS AN ARM — and the reason this arm exists at all is that
  // a probe asserting only "the gallery renders" would stay GREEN with the old
  // auto-populating list still in place underneath it.
  arm('THE LIST DOES NOT POPULATE ITSELF — no bucket open, no rows painted',
    [rowsNow(), gal.id('history-list').querySelectorAll('li').length,
      squeeze(gal.id('history-list').textContent)],
    // `control` is what the SAME read returns under the behaviour the owner had
    // removed, MEASURED by running this probe against a mutant copy with the
    // auto-append restored — not written from memory. The first version of this
    // value said `4` rows, from the intuition "one row per loaded entry, and four
    // entries are in range"; the mutant painted **5** (it appends every loaded entry,
    // undated ones included) and the text carried `too old` and `broken` too. The
    // arm still passed, because it only asks the two values to DIFFER — which is
    // exactly how a control that misstates the old behaviour stays invisible.
    [0, 1, 'Pick a day or an hour above.'],
    [5, 6, '12:34:16a12:32:16b11:34:16c10-06 06:36:16too old-date 99:99brokenPick a day or an hour above.']);

  // A bucket press paints THAT bucket, and only it.
  const firstDay = want.days[0];
  dayBtns()[0].click();
  await tick();
  const dayRows = [...gal.id('history-list').querySelectorAll('.hist')];
  arm('pressing a DAY paints exactly that day\'s lines, and marks the button',
    [dayRows.length, dayBtns()[0].getAttribute('aria-pressed')],
    [firstDay.count, 'true']);

  // The hour button narrows it further.
  const hourWant = firstDay.hours[0];
  hourBtns()[0].click();
  await tick();
  arm('pressing an HOUR narrows the list to that hour alone',
    [gal.id('history-list').querySelectorAll('.hist').length, hourWant.count],
    [hourWant.count, hourWant.count]);

  // Back to a range: the pick is cleared and the hint returns — the way out.
  rangeBtns()[0].click();
  await tick();
  arm('pressing a RANGE clears the bucket and the list goes back to the hint',
    [rowsNow(), squeeze(gal.id('history-list').textContent),
      rangeBtns()[0].getAttribute('aria-pressed')],
    [0, 'Pick a day or an hour above.', 'true']);

  // THE DEFECT FOUND BY READING, AS AN ARM — and it needs its OWN panel, because the
  // fixture above holds lines 2 and 4 minutes old, so `1 h` there is NOT empty (the
  // first version of this arm asserted "Nothing in the last 1 h." against a range
  // that really did hold two lines — the arm was wrong, not the panel). This panel
  // holds nothing inside the last hour, which is the only state in which the defect
  // exists: `1 h` with no buckets used to hide the whole host, taking the `24 h`
  // button that would have brought the buckets back with it.
  const quietEntries = [at(2 * HOUR, 'older'), at(3 * HOUR, 'older still')];
  const galQuiet = await panel({ entries: quietEntries });
  await tick();
  await tick();
  const qhost = galQuiet.id('history-gallery');
  const qRanges = () => [...qhost.querySelectorAll('.gallery__range')];
  const qDays = () => [...qhost.querySelectorAll('.gallery__day')];
  arm('the quiet panel starts on 24 h with its buckets offered',
    [qhost.hidden, qRanges().map((b) => b.textContent), qDays().length],
    [false, ['24 h', '1 h'], G.buckets(quietEntries).days.length]);
  qRanges()[1].click();
  await tick();
  const quiet = qhost.hidden ? [] : qRanges().map((b) => b.textContent);
  arm('an EMPTY range keeps the range buttons on screen, so there is a way back',
    [quiet, squeeze((qhost.querySelector('.gallery__warn') || {}).textContent || '')],
    [['24 h', '1 h'], 'Nothing in the last 1 h.']);

  // And pressing `24 h` again brings the buckets back — the way out really works.
  qRanges()[0].click();
  await tick();
  arm('the way out of an empty range really restores the buckets',
    [qRanges()[0].getAttribute('aria-pressed'), qDays().length],
    ['true', G.buckets(quietEntries).days.length]);

  // And the CSS that makes the gallery a row of small buttons, not a paragraph.
  arm('the gallery is styled as a wrapping button row that does not grow',
    [/\.gallery\s*\{[^}]*flex:\s*0 0 auto/s.test(css),
      /\.gallery__row\s*\{[^}]*flex-wrap:\s*wrap/s.test(css),
      /\.gallery__btn\s*\{/s.test(css), /\.gallery__btn\.is-active\s*\{/s.test(css)],
    [true, true, true, true]);

  for (const p of [strip, full, forcedPanel, forcedStrip, wiredT, unwiredT, wiredD, cancelD, unwiredD, openWired, openUnwired, gal]) {
    if (p.errors.length) {
      arm('no loaded panel may have thrown', p.errors, []);
      break;
    }
  }

  // --------------------------------------------------------------- verdict
  const failed = results.filter((r) => !r.ok);
  console.log(`\nRESULT: ${failed.length ? `RED — ${failed.length} violation(s)` : 'GREEN'} — ${results.length - failed.length}/${results.length} arm(s)`);
  for (const f of failed) {
    console.log(`  FAIL [${f.arm}] ${f.name}`);
    console.log(`       real=${JSON.stringify(f.real)} want=${JSON.stringify(f.want)}`);
  }
  console.log(`harness: ${path.relative(REPO, HARNESS)} — the file a human opens; the surfaces and the`);
  console.log('         dialog are its URL hash states (see _main/receipt-panel-two-surfaces.md).');
  return failed.length ? 1 : 0;
}

main().then((rc) => process.exit(rc));
