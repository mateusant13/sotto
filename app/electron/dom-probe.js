'use strict';

/**
 * Sotto M0 — the panel DOM probe.
 *
 * Loads panel.html in a real Electron BrowserWindow at the real window size,
 * with the real preload bridge, and dumps what the renderer actually LAYS OUT:
 * every probed element's box and computed style, the document's scroll extent
 * against the viewport, the scroll overflow of the caption area, and the WCAG
 * contrast of every piece of text against the paint behind it.
 *
 * Why this exists: the owner saw a panel that was "completamente bugado/errado"
 * while the caption pipeline was proven. A CSS defect that makes an element
 * collapse, an element paint no ink, or a scroll container invent a scrollbar
 * is INVISIBLE to a pipeline test and obvious to an eye. This probe is the eye,
 * as numbers.
 *
 * Two states are probed, both reached through the production code path:
 *   idle — the panel as it loads, with the empty-state placeholder up.
 *   live — after main has sent a real caption over IPC, through preload.js into
 *          panel.js, so the DOM state under test is the one the owner sees.
 *
 * It never opens a visible window: `show:false`, and the whole run is bounded
 * by WALL_CLOCK_MS. Exit code is non-zero if any contract below is broken.
 *
 * Run it (the ./node_modules form gives rc=127 on this box):
 *   node_modules/electron/dist/electron.exe dom-probe.js
 *   node_modules/electron/dist/electron.exe dom-probe.js > dump.json
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('node:path');

const APP_DIR = __dirname;
const PANEL_HTML = path.join(APP_DIR, 'panel.html');
const PANEL_PRELOAD = path.join(APP_DIR, 'preload.js');

// --- the contract this probe holds the surface to -----------------------------

/** Mirrors PANEL_WIDTH / PANEL_HEIGHT in main.js:39-40. */
const PANEL_WIDTH = 380;
const PANEL_HEIGHT = 900;

/**
 * How far inside the window `.panel` is allowed to sit.
 *
 * dockRight() (main.js:131-169) sizes the WINDOW to the panel
 * (`width: geometry.width, height: geometry.height`, main.js:200-201) and puts
 * PANEL_MARGIN outside it, between the window and the work-area edge
 * (`x = work.x + w - panelWidth - margin`, main.js:148). So the window rectangle
 * IS the slab and the intended margin is already spent: a slab inset further
 * than this is eating its own footprint.
 */
const EXPECTED_PANEL_INSET = 0;

/** WCAG AA for body text. Everything in this panel is well under 18.66px. */
const CONTRAST_MIN = 4.5;

/** Boxes may miss by a rounding step, not by a design decision. */
const TOLERANCE_PX = 1;

/** Header mark and header controls should share a centre line. */
const ALIGN_TOLERANCE_PX = 2;

/** Hard wall on the run. The probe must never hang on a missing signal. */
const WALL_CLOCK_MS = 20000;

/** Wait for the renderer's DOM to exist. Layout is computed on demand, so
 *  nothing here waits for a paint: a `show:false` window never gets one, and
 *  waiting on requestAnimationFrame would hang forever. */
const DOM_READY_TIMEOUT_MS = 8000;

/**
 * What must be on screen, in which state, and whether it carries text.
 * `visibleIn` is a state contract in BOTH directions: an element inside it must
 * render, and an element outside it must NOT render. The second half is how
 * "an empty list box that never goes away" gets caught, instead of being waved
 * through as "it had area".
 *
 *   idle    — the panel as it loads: placeholder up, no lines.
 *   live    — after main sent real captions over IPC (preload -> panel.js).
 *   cleared — after the Clear button was really clicked and came back empty.
 */
const TARGETS = [
  { selector: '#panel', visibleIn: ['idle', 'live', 'cleared'] },
  { selector: '.panel__header', visibleIn: ['idle', 'live', 'cleared'] },
  { selector: '.wordmark__name', visibleIn: ['idle', 'live', 'cleared'], text: true },
  { selector: '.icon-button', visibleIn: ['idle', 'live', 'cleared'], all: true },
  { selector: '.captions', visibleIn: ['idle', 'live', 'cleared'] },
  { selector: '#placeholder', visibleIn: ['idle', 'cleared'], text: true },
  { selector: '#caption-list', visibleIn: ['live'], text: false },
  { selector: '.caption', visibleIn: ['live'], text: false },
  { selector: '.caption__text', visibleIn: ['live'], text: true },
  { selector: '.caption__time', visibleIn: ['live'], text: true },
  { selector: '.status', visibleIn: ['idle', 'live', 'cleared'], text: true },
  { selector: '.status__text', visibleIn: ['idle', 'live', 'cleared'], text: true },
  { selector: '.status__hint', visibleIn: ['idle', 'live', 'cleared'], text: true },
  { selector: 'kbd', visibleIn: ['idle', 'live', 'cleared'], text: true, all: true },
  { selector: '.wordmark__tag', visibleIn: ['idle', 'live', 'cleared'], text: true },
  {
    selector: '.captions__placeholder-title',
    visibleIn: ['idle', 'cleared'],
    text: true,
  },
  {
    selector: '.captions__placeholder-body',
    visibleIn: ['idle', 'cleared'],
    text: true,
  },
];

/** Scroll containers whose overflow is a defect rather than a feature. */
const SCROLL_CONTAINERS = ['.captions'];

// --- the in-page dump ---------------------------------------------------------

/**
 * Runs inside the renderer. Returns raw measurements only; every judgement
 * happens on this side of the bridge so a failure names a contract, not a style
 * string. Thrown as source text, never defined here.
 */
function pageDump() {
  const round = (n) => Math.round(n * 100) / 100;

  function parseColor(value) {
    const match = String(value).match(/rgba?\(([^)]+)\)/);
    if (!match) return null;
    const parts = match[1]
      .split(/[\s,/]+/)
      .filter(Boolean)
      .map(Number);
    if (parts.length < 3 || parts.some(Number.isNaN)) return null;
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
  }

  const channel = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const luminance = ({ r, g, b }) =>
    0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
  const over = (fg, bg) => ({
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  });

  /**
   * The window is transparent, so the terminal backdrop is the desktop — an
   * unknown. `--bg` (#0b0f14) is used instead because it is the darkest stop of
   * the slab gradient the panel actually paints (rgba(11,15,20,0.98) over
   * rgba(8,11,16,0.55) over rgba(17,24,35,0.97)), so compositing down to it is
   * within a couple of RGB steps of what the owner sees. An assumption, stated
   * here, rather than a number pretending to be a pixel read.
   */
  const TERMINAL_BACKDROP = { r: 0x0b, g: 0x0f, b: 0x14, a: 1 };

  function backdropOf(el) {
    let acc = TERMINAL_BACKDROP;
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
      const bg = parseColor(getComputedStyle(node).backgroundColor);
      if (bg && bg.a > 0) acc = over(bg, acc);
    }
    return acc;
  }

  function contrastOf(color, backdrop) {
    const l1 = luminance(color);
    const l2 = luminance(backdrop);
    const hi = Math.max(l1, l2);
    const lo = Math.min(l1, l2);
    return round((hi + 0.05) / (lo + 0.05));
  }

  function rectOf(el) {
    const r = el.getBoundingClientRect();
    return { x: round(r.x), y: round(r.y), width: round(r.width), height: round(r.height) };
  }

  const elements = [];
  for (const spec of window.__probeTargets) {
    const found = Array.from(document.querySelectorAll(spec.selector));
    if (found.length === 0) {
      elements.push({ selector: spec.selector, missing: true });
      continue;
    }
    const list = spec.all ? found : [found[0]];
    list.forEach((el, index) => {
      const cs = getComputedStyle(el);
      const rect = rectOf(el);
      const color = parseColor(cs.color);
      const backdrop = backdropOf(el);
      elements.push({
        selector: spec.selector,
        index,
        matchCount: found.length,
        text: spec.text === true,
        rect,
        area: round(rect.width * rect.height),
        display: cs.display,
        position: cs.position,
        visibility: cs.visibility,
        opacity: round(Number(cs.opacity)),
        color: cs.color,
        colorAlpha: color ? color.a : null,
        webkitTextFillColor: cs.webkitTextFillColor || null,
        backgroundColor: cs.backgroundColor,
        backgroundImage: cs.backgroundImage === 'none' ? 'none' : 'present',
        backgroundClip: cs.backgroundClip || null,
        fontSize: cs.fontSize,
        fontWeight: cs.fontWeight,
        hiddenAttribute: el.hasAttribute('hidden'),
        textSample: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60),
        backdrop: spec.text === true
          ? { r: Math.round(backdrop.r), g: Math.round(backdrop.g), b: Math.round(backdrop.b) }
          : null,
        contrast: spec.text === true && color ? contrastOf(color, backdrop) : null,
      });
    });
  }

  const containers = {};
  for (const selector of window.__probeScrollContainers) {
    const el = document.querySelector(selector);
    if (!el) {
      containers[selector] = { missing: true };
      continue;
    }
    containers[selector] = {
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      overflowY: el.scrollHeight - el.clientHeight,
      overflowX: el.scrollWidth - el.clientWidth,
      rect: rectOf(el),
    };
  }

  const panel = document.querySelector('#panel');
  const panelRect = panel ? panel.getBoundingClientRect() : null;
  const viewport = {
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
  };

  const mark = document.querySelector('.wordmark__mark');
  const button = document.querySelector('.icon-button');
  const alignment =
    mark && button
      ? round(
          mark.getBoundingClientRect().top +
            mark.getBoundingClientRect().height / 2 -
            (button.getBoundingClientRect().top + button.getBoundingClientRect().height / 2),
        )
      : null;

  const panelStyle = panel ? getComputedStyle(panel) : null;
  const captionCount = document.querySelectorAll('.caption').length;
  // CONTENT, not just geometry. A panel can satisfy every box assertion while
  // showing the wrong words or splitting them wrongly, and the only way to
  // catch that is to read back what was actually rendered.
  const captionLines = Array.from(document.querySelectorAll('.caption__text')).map((n) =>
    n.textContent.replace(/\s+/g, ' ').trim(),
  );
  const provisionalCount = document.querySelectorAll('.caption--provisional').length;

  return {
    viewport,
    panel: {
      rect: panelRect
        ? {
            x: round(panelRect.x),
            y: round(panelRect.y),
            width: round(panelRect.width),
            height: round(panelRect.height),
          }
        : null,
      gapToWindowEdge: panelRect
        ? {
            top: round(panelRect.top),
            right: round(viewport.innerWidth - panelRect.right),
            bottom: round(viewport.innerHeight - panelRect.bottom),
            left: round(panelRect.left),
          }
        : null,
      paintsOwnBackground: panelStyle
        ? panelStyle.backgroundImage !== 'none' ||
          (parseColor(panelStyle.backgroundColor) || { a: 0 }).a > 0
        : false,
    },
    document: {
      bodyScrollWidth: document.body.scrollWidth,
      bodyScrollHeight: document.body.scrollHeight,
      docScrollWidth: document.documentElement.scrollWidth,
      docScrollHeight: document.documentElement.scrollHeight,
      clientWidth: document.documentElement.clientWidth,
      clientHeight: document.documentElement.clientHeight,
      overflowX: document.documentElement.scrollWidth - viewport.innerWidth,
      overflowY: document.documentElement.scrollHeight - viewport.innerHeight,
    },
    headerAlignmentDeltaY: alignment,
    captionCount,
    captionLines,
    provisionalCount,
    containers,
    elements,
  };
}

// --- judgement ----------------------------------------------------------------

function judge(state, dump, config) {
  const failures = [];
  const fail = (code, detail) => failures.push({ state, code, detail });
  const visible = (entry) =>
    entry.display !== 'none' &&
    entry.visibility === 'visible' &&
    entry.opacity > 0 &&
    entry.rect.width > 0 &&
    entry.rect.height > 0;

  if (!dump.panel.rect) {
    fail('panel-missing', '#panel is not in the DOM');
  } else {
    const gap = dump.panel.gapToWindowEdge;
    for (const side of ['top', 'right', 'bottom', 'left']) {
      const delta = Math.abs(gap[side] - config.expectedPanelInset);
      if (delta > config.tolerancePx) {
        fail(
          'panel-inset',
          `#panel sits ${gap[side]}px from the window's ${side} edge; the window is sized ` +
            `to the slab, so the inset must be ${config.expectedPanelInset}px (off by ${delta}px)`,
        );
      }
    }
    if (dump.viewport.innerWidth < config.panelWidth || dump.viewport.innerHeight < config.panelHeight) {
      fail(
        'viewport-too-small',
        `viewport ${dump.viewport.innerWidth}x${dump.viewport.innerHeight} is smaller than the ` +
          `panel window ${config.panelWidth}x${config.panelHeight}`,
      );
    }
    if (!dump.panel.paintsOwnBackground) {
      fail(
        'slab-transparent',
        '#panel paints neither a background-color nor a background-image, so the transparent ' +
          'window lets the desktop through the whole slab',
      );
    }
  }

  for (const side of ['overflowX', 'overflowY']) {
    if (dump.document[side] > config.tolerancePx) {
      fail(
        'document-overflow',
        `document scrolls ${dump.document[side]}px on ${side === 'overflowX' ? 'X' : 'Y'} ` +
          `(${dump.document.docScrollWidth}x${dump.document.docScrollHeight} against a ` +
          `${dump.viewport.innerWidth}x${dump.viewport.innerHeight} viewport)`,
      );
    }
  }

  for (const [selector, box] of Object.entries(dump.containers)) {
    if (box.missing) {
      fail('container-missing', `${selector} is not in the DOM`);
      continue;
    }
    // "empty" is a property of the DOM, not of the probe: any state whose
    // caption count is zero must not leave the scroll area over-full.
    if (dump.captionCount === 0 && box.overflowY > config.tolerancePx) {
      fail(
        'phantom-scroll',
        `${selector} overflows by ${box.overflowY}px while it holds nothing (scrollHeight ` +
          `${box.scrollHeight} > clientHeight ${box.clientHeight}) in state "${state}": a box ` +
          'that should be out of the flow is still taking up space, so the empty panel shows a ' +
          'scrollbar with nothing to scroll',
      );
    }
    if (box.overflowX > config.tolerancePx) {
      fail(
        'horizontal-overflow',
        `${selector} overflows by ${box.overflowX}px horizontally ` +
          `(scrollWidth ${box.scrollWidth} > clientWidth ${box.clientWidth})`,
      );
    }
  }

  if (
    dump.headerAlignmentDeltaY !== null &&
    Math.abs(dump.headerAlignmentDeltaY) > config.alignTolerancePx
  ) {
    fail(
      'header-misaligned',
      `the header mark and the header controls are ${dump.headerAlignmentDeltaY}px apart on ` +
        'their centre line',
    );
  }

  const bySelector = new Map();
  for (const entry of dump.elements) {
    if (!bySelector.has(entry.selector)) bySelector.set(entry.selector, []);
    bySelector.get(entry.selector).push(entry);
  }

  for (const spec of config.targets) {
    const entries = bySelector.get(spec.selector) || [];
    const expected = spec.visibleIn.includes(state);
    if (entries.length === 0 || entries[0].missing) {
      // A selector that does not match at all is only a defect in a state where
      // it was supposed to be on screen. `.caption` is absent in the idle panel
      // for the same reason it is absent from a fresh document, and calling that
      // a failure would teach everyone to ignore the real ones.
      if (expected) {
        fail(
          'selector-missing',
          `no element matches ${spec.selector}, but state "${state}" requires it on screen`,
        );
      }
      continue;
    }
    for (const entry of entries) {
      const label = entries.length > 1 ? `${spec.selector}[${entry.index}]` : spec.selector;
      const isVisible = visible(entry);

      if (expected && !isVisible) {
        fail(
          entry.display === 'none' ? 'not-rendered' : 'zero-area',
          `${label} must be on screen in state "${state}" but measured ` +
            `display=${entry.display} visibility=${entry.visibility} opacity=${entry.opacity} ` +
            `box=${entry.rect.width}x${entry.rect.height}`,
        );
        continue;
      }
      if (!expected && isVisible) {
        fail(
          'unexpectedly-visible',
          `${label} is rendering (${entry.rect.width}x${entry.rect.height}, ` +
            `display=${entry.display}) in state "${state}", where the contract says it must not ` +
            `be — hidden=${entry.hiddenAttribute}`,
        );
        continue;
      }
      if (!isVisible || !spec.text) continue;

      if (entry.colorAlpha === 0) {
        fail(
          'no-ink',
          `${label} has color ${entry.color}, so it paints nothing; text sample ` +
            `"${entry.textSample}"`,
        );
      } else if (entry.contrast !== null && entry.contrast < config.contrastMin) {
        fail(
          'low-contrast',
          `${label} contrast ${entry.contrast}:1 against its painted backdrop ` +
            `rgb(${entry.backdrop.r},${entry.backdrop.g},${entry.backdrop.b}) at ` +
            `${entry.fontSize}/${entry.fontWeight} — below AA ${config.contrastMin}:1; ` +
            `text sample "${entry.textSample}"`,
        );
      }
      if (entry.backgroundClip === 'text') {
        fail(
          'background-clip-text',
          `${label} is legible only through background-clip:text; if that is unsupported ` +
            'the text is invisible',
        );
      }
    }
  }

  return failures;
}

// --- run ----------------------------------------------------------------------

const failures = [];
const dumps = {};

function bail(err) {
  const message = err && err.stack ? err.stack : String(err);
  process.stdout.write(
    `${JSON.stringify(
      {
        tool: 'dom-probe',
        ok: false,
        error: message,
        expectation: 'a load or measurement failure is a FAILURE, not an empty dump',
      },
      null,
      2,
    )}\n`,
  );
  app.exit(2);
}

function emit() {
  const report = {
    tool: 'dom-probe',
    target: path.basename(PANEL_HTML),
    window: { width: PANEL_WIDTH, height: PANEL_HEIGHT },
    expectations: {
      expectedPanelInset: EXPECTED_PANEL_INSET,
      contrastMin: CONTRAST_MIN,
      tolerancePx: TOLERANCE_PX,
      alignTolerancePx: ALIGN_TOLERANCE_PX,
      targets: TARGETS,
    },
    states: dumps,
    failures,
    ok: failures.length === 0,
  };
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  app.exit(failures.length === 0 ? 0 : 1);
}

const wallClock = setTimeout(() => {
  bail(new Error(`probe exceeded ${WALL_CLOCK_MS}ms without completing`));
}, WALL_CLOCK_MS);

async function main() {
  // The renderer sends receipts on channels main.js owns. They are swallowed
  // here on purpose: this probe measures the SURFACE, and an unhandled ipcMain
  // send would throw inside the renderer and hide the layout under test.
  for (const channel of [
    'sotto:caption-observed',
    'sotto:status-observed',
    'sotto:hide',
    'sotto:toggle',
    'sotto:quit',
    'sotto:pointer',
    'sotto:caption-applied',
    'sotto:status-applied',
    'sotto:renderer-ready',
    'sotto:caption-cleared',
  ]) {
    ipcMain.on(channel, () => {});
  }
  ipcMain.handle('sotto:info', () => ({
    hotkey: 'Alt+C',
    platform: process.platform,
    geometry: { width: PANEL_WIDTH, height: PANEL_HEIGHT },
  }));

  const win = new BrowserWindow({
    width: PANEL_WIDTH,
    height: PANEL_HEIGHT,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    focusable: false,
    webPreferences: {
      preload: PANEL_PRELOAD,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  const wc = win.webContents;
  const loaded = new Promise((resolve, reject) => {
    wc.once('did-finish-load', resolve);
    wc.once('did-fail-load', (_e, code, desc) =>
      reject(new Error(`did-fail-load ${code} ${desc}`)),
    );
  });
  win.loadFile(PANEL_HTML);
  await loaded;

  await wc.executeJavaScript(
    `window.__probeTargets = ${JSON.stringify(TARGETS)};` +
      `window.__probeScrollContainers = ${JSON.stringify(SCROLL_CONTAINERS)};`,
  );

  const domReady = Date.now() + DOM_READY_TIMEOUT_MS;
  for (;;) {
    // eslint-disable-next-line no-await-in-loop
    const ok = await wc.executeJavaScript(
      `document.readyState === 'complete' && !!document.getElementById('panel')`,
    );
    if (ok) break;
    if (Date.now() > domReady) throw new Error('the panel DOM never appeared');
    await new Promise((r) => setTimeout(r, 50));
  }

  const dumpSource = `(${pageDump.toString()})()`;
  const config = {
    targets: TARGETS,
    expectedPanelInset: EXPECTED_PANEL_INSET,
    contrastMin: CONTRAST_MIN,
    tolerancePx: TOLERANCE_PX,
    alignTolerancePx: ALIGN_TOLERANCE_PX,
    panelWidth: PANEL_WIDTH,
    panelHeight: PANEL_HEIGHT,
  };

  // State 1: idle — exactly as the panel loads, placeholder up.
  const idle = await wc.executeJavaScript(dumpSource);
  dumps.idle = idle;
  failures.push(...judge('idle', idle, config));

  // State 2: live — real captions over real IPC, through the real preload,
  // carrying the AUDIO metadata the worker actually sends.
  //
  // The old assertion was `captionCount >= 2` for two captions. That counted
  // the M0 contract, where every caption became its own line; under
  // LocalAgreement-2 two fragments are deliberately ONE held line, so the
  // probe was failing a correct renderer. The contract that matters now is
  // the WORDS and where they are split, so that is what is asserted below.
  // Shaped like what the worker ACTUALLY emits: `sotto_worker.py:1047-1048`
  // derives start/end from the chunk index, so the windows are strictly
  // contiguous and never re-read the same audio. An earlier draft of this
  // probe fed word-repeating fragments with a re-read span, which measured a
  // revision path the live worker cannot reach — a probe that certifies an
  // unreachable path certifies nothing.
  //
  // Also kept SHORT: at ~81 characters the hard cap (SENTENCE_MAX_CHARS)
  // closes the line, and a probe that trips the cap measures the cap.
  wc.send('sotto:caption', { text: 'going along', meta: { start: 0.0, end: 0.56 } });
  wc.send('sotto:caption', { text: 'slush country', meta: { start: 0.56, end: 1.12 } });
  wc.send('sotto:caption', { text: 'road today', meta: { start: 1.12, end: 1.68 } });

  // The A4 boundary, end to end over real IPC: a fragment 11.20 s of AUDIO
  // later must close the line. The wall clock between these two sends is a few
  // milliseconds, so a line split here can only have come from the audio gap
  // — which is exactly the distinction the old 1200 ms wall-clock rule could
  // not make, and the one this probe exists to pin.
  wc.send('sotto:caption', { text: 'roads are closed', meta: { start: 12.88, end: 14.0 } });
  wc.send('sotto:caption', { text: 'tonight', meta: { start: 14.0, end: 14.56 } });
  await new Promise((r) => setTimeout(r, 300));

  const live = await wc.executeJavaScript(dumpSource);
  dumps.live = live;
  failures.push(...judge('live', live, config));

  if (!live.captionLines || live.captionLines.length === 0) {
    failures.push({
      state: 'live',
      code: 'captions-did-not-render',
      detail:
        'main sent 5 captions over IPC and the panel rendered 0 .caption__text nodes — ' +
        'the probe cannot certify a surface that never got content',
    });
  } else {
    const shown = live.captionLines.join(' ').toLowerCase();
    // Case-insensitive on purpose: `formulate()` capitalises the first letter
    // and adds the terminal mark, so a case-sensitive check here would fail a
    // correct renderer for doing its job.
    for (const wanted of ['going along slush country road today', 'roads are closed tonight']) {
      if (!shown.includes(wanted)) {
        failures.push({
          state: 'live',
          code: 'caption-content-wrong',
          detail: `expected the rendered captions to contain ${JSON.stringify(wanted)}, got ${JSON.stringify(live.captionLines)}`,
        });
      }
    }
    // A pause must SPLIT, and a burst must NOT. Both directions in one state:
    //   line 0 = the contiguous burst 0.00 -> 1.68 s  (no silence inside)
    //   line 1 = what follows the 11.20 s audio silence
    // If the renderer ever split the burst, or refused to split at the pause,
    // this is the assertion that catches it — and the wall clock between the
    // sends was milliseconds, so the split cannot be credited to it.
    if (live.captionLines.length !== 2) {
      failures.push({
        state: 'live',
        code: 'segmentation-wrong',
        detail:
          `expected exactly 2 lines — one for the contiguous burst and one after the ` +
          `11.20 s audio pause — got ${live.captionLines.length}: ` +
          JSON.stringify(live.captionLines),
      });
    } else if (!live.captionLines[0].toLowerCase().includes('going along slush country road today')) {
      failures.push({
        state: 'live',
        code: 'segmentation-boundary-misplaced',
        detail:
          `the burst must stay whole on line 0, got ${JSON.stringify(live.captionLines[0])}`,
      });
    }
  }

  // State 3: cleared — the non-happy path a user actually takes. The Clear
  // button is really clicked, so panel.js's own handler runs: it empties the
  // list, sets `list.hidden = true` and brings the placeholder back. This is
  // where an author `display` rule silently beats the user-agent `[hidden]`
  // rule and leaves an empty box on screen.
  await wc.executeJavaScript(`document.getElementById('clear-button').click();`);
  await new Promise((r) => setTimeout(r, 100));

  const cleared = await wc.executeJavaScript(dumpSource);
  dumps.cleared = cleared;
  failures.push(...judge('cleared', cleared, config));

  if (cleared.captionCount !== 0) {
    failures.push({
      state: 'cleared',
      code: 'clear-did-not-empty',
      detail:
        `the Clear button was clicked and ${cleared.captionCount} .caption lines are still ` +
        'in the DOM',
    });
  }

  clearTimeout(wallClock);
  win.destroy();
  emit();
}

app.whenReady().then(main).catch(bail);