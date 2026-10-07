'use strict';

/**
 * Sotto M0 — the shell. Electron main process.
 *
 * M0's only job is to exist measurably: the panel opens, Alt+C toggles it, and
 * the window behaviour is provable from stdout without a screenshot. There is no
 * audio capture and no model in THIS file — the caption area is a receiver, and
 * the Python ASR worker that will feed it is attached by `worker-bridge.js`
 * (spawn, JSONL captions/statuses, restart with backoff). Pressing Alt+C now
 * brings that worker up, so the panel reports the worker's real state instead of
 * a static "Waiting for audio".
 *
 * Why Electron and not the Tauri build next door: the Tauri/Rust tree at
 * ../src-tauri cannot be built on this host — cargo hangs at "Updating
 * crates.io index" on both the gnu and msvc toolchains while curl on the same
 * host returns in 0.15 s. Rust is out of scope for this milestone; this file is
 * the shell, and nothing under ../src-tauri is read at runtime or written to.
 */

const { app, BrowserWindow, globalShortcut, ipcMain, screen } = require('electron');
const path = require('node:path');
const { createBridge, DEFAULT_WORKER_PATH, DEFAULT_COMMAND } = require('./worker-bridge');
const { createHotReload, DEBOUNCE_MS } = require('./hot-reload');
const { runBridgeSelfTest, printResult } = require('./bridge-selftest');
const historyStore = require('./history-store');

/** The global toggle. Global rather than window-local is the whole point: the
 *  panel is hidden most of the time, so a hotkey that only worked while the
 *  panel had focus would never fire. Matches HOTKEY in ../src-tauri/src/main.rs.
 *  `--hotkey=` overrides it for a hermetic run: Alt+C is a GLOBAL accelerator, so
 *  on a machine where an earlier instance still owns it, a single-instance test
 *  cannot show the winner registering at all. Overriding proves the guard itself
 *  instead of the machine's accelerator state. Test-only; default unchanged. */
/** Resolved just below, once argValue() exists — see the note there. */
let HOTKEY = 'Alt+C';

/** Panel size in DIP (CSS) pixels. The Rust shell used 360 x full-height with a
 *  10 px margin; the Electron brief asks for a fixed slab, so this is 380 x 900
 *  vertically centred instead. Both honour the same work-area clamping rules. */
const PANEL_WIDTH = 380;
const PANEL_HEIGHT = 900;

/** Transparent breathing room between the panel and the window edge, so the
 *  rounded corners are not clipped by the window rectangle. */
const PANEL_MARGIN = 12;

/** The panel never takes more than this fraction of the work-area width. */
const PANEL_MAX_WORK_FRACTION = 0.34;

/** How many caption lines the panel keeps before dropping the oldest. */
const MAX_CAPTIONS = 200;

const APP_DIR = __dirname;

/** stdout receipts. `run.log` is the acceptance artefact; these lines are how a
 *  claim in it can be checked without watching the screen. */
function log(message) {
  console.log(`sotto: ${message}`);
}

function warn(message) {
  console.error(`sotto: ${message}`);
}

/** Flags for the self-test run. Nothing here changes production behaviour. */
const ARGS = new Set(process.argv.slice(1).filter((a) => a.startsWith('--')));
const argValue = (name) => {
  const hit = process.argv.slice(1).find((a) => a.startsWith(`${name}=`));
  return hit ? hit.slice(name.length + 1) : null;
};

// HOTKEY is resolved HERE, after argValue exists. It used to be assigned at the
// top of the file, which threw `ReferenceError: Cannot access 'argValue' before
// initialization` and killed the whole main process before the panel or the
// hotkey ever existed. MEASURED 2026-10-06: the owner pressed Alt+C and nothing
// happened, because there was no process left to register it — the only thing on
// screen was Electron's own "A JavaScript error occurred in the main process".
HOTKEY = argValue('--hotkey') || HOTKEY;
const SELFTEST = ARGS.has('--selftest');
/** Transcribing a file is a visible, bounded run: the owner asked to see text. */
const START_VISIBLE = ARGS.has('--show') || SELFTEST || argValue('--transcribe') !== null;
const DEMO_CAPTION = argValue('--caption');
const DEMO_STATUS = argValue('--status');
/** Quit on a wall clock so an acceptance run ends by ITSELF and leaves a log,
 *  instead of needing a hand on the kill switch. 0 = never. */
const EXIT_AFTER = Number(argValue('--exit-after')) || 0;
/** `--no-hot-reload` is the opt-out: a run that must not be disturbed by a save
 *  anywhere on this machine asks for it explicitly, and nothing is armed. */
const NO_HOT_RELOAD = ARGS.has('--no-hot-reload');
/** Kept next to the flag so the doc, the log and the code cannot drift: the
 *  number main.js prints at startup IS the constant hot-reload.js uses. */
const HOT_RELOAD_DEBOUNCE_MS = DEBOUNCE_MS;

/** --- the worker bridge -------------------------------------------------
 *  Flags, all additive and all optional. `--selftest` on its own still behaves
 *  exactly as M0 did: no worker, no Python, no caption — its receipt is a
 *  frozen artefact for the shell lane. */
const BRIDGE_SELFTEST = ARGS.has('--bridge-selftest');
/** Start the worker at launch instead of waiting for the first Alt+C. */
const WITH_WORKER = ARGS.has('--with-worker');
/** Test-only. Measures the real panel and exits; see the block after loadFile. */
const DUMP_DOM = ARGS.has('--dump-dom');
/** Test-only: force an opaque window, to A/B whether transparency is the defect. */
const USE_OPAQUE = ARGS.has('--opaque');
const WORKER_PATH = argValue('--worker') || DEFAULT_WORKER_PATH;
const PYTHON_PATH = argValue('--python') || DEFAULT_COMMAND;
const WORKER_DEVICE = argValue('--device');
const WORKER_CAPTURE = argValue('--capture');
/** `--transcribe=<file>` makes the worker transcribe a FILE instead of the
 *  loopback. It is the one invocation that is proven to produce model text on
 *  this host (`worker/assets/sample1.flac` -> 37 tokens), so it is how the
 *  end-to-end caption path gets proven end to end without an audio device. It
 *  travels by ENVIRONMENT, never by argv: the bridge builds argv as
 *  `python [args] <workerPath> [extraArgs]`, so a flag from here would land
 *  before the script path and be eaten by the interpreter's own parser. That is
 *  the same reason worker-bridge.js passes the device by env. */
const TRANSCRIBE_FILE = argValue('--transcribe');

/** @type {BrowserWindow|null} */
let panel = null;
/** Capped mirror of what the renderer is showing, for the startup receipt and
 *  the self-test. The renderer is the source of truth for the DOM; this is the
 *  main process's answer to "did a caption actually arrive". */
const captionLog = [];

/** @type {import('./worker-bridge').WorkerBridge|null} */
let workerBridge = null;

// ---------------------------------------------------------------------------
// Geometry — the port of ../src-tauri/src/geometry.rs::dock_right.
//
// Kept a pure function so it can be reasoned about (and unit-tested) without a
// window: the output is always contained in the work area, whatever the work
// area is, including degenerate rectangles.
// ---------------------------------------------------------------------------

/**
 * Dock a panel to the right edge of `work`, vertically centred.
 * @param {{x:number,y:number,width:number,height:number}} work work area in DIP
 * @param {{width?:number,height?:number,margin?:number,dock?:'right'}} [opts]
 */
function dockRight(work, opts = {}) {
  const wantWidth = Number.isFinite(opts.width) ? opts.width : PANEL_WIDTH;
  const wantHeight = Number.isFinite(opts.height) ? opts.height : PANEL_HEIGHT;
  const wantMargin = Number.isFinite(opts.margin) ? opts.margin : PANEL_MARGIN;
  const w = Math.max(0, work.width);
  const h = Math.max(0, work.height);

  // A margin that leaves the panel no room to live in is a margin that shrinks
  // before anything else does.
  const margin = Math.max(0, Math.min(wantMargin, w / 8, h / 8));

  // A panel wider than its share of the work area is a mistake, not a layout.
  const panelWidth = Math.min(wantWidth, Math.max(0, w * PANEL_MAX_WORK_FRACTION));
  const panelHeight = Math.min(wantHeight, Math.max(0, h - 2 * margin));

  // Flush to the right edge of the work area, never past it; vertically centred
  // in whatever height is left over.
  const x = work.x + w - panelWidth - margin;
  const y = work.y + Math.round((h - panelHeight) / 2);

  const geometry = {
    workX: work.x,
    workY: work.y,
    workWidth: w,
    workHeight: h,
    x: Math.max(work.x, Math.round(x)),
    y: Math.max(work.y, Math.round(y)),
    width: Math.max(1, Math.round(panelWidth)),
    height: Math.max(1, Math.round(panelHeight)),
    margin,
    docked: opts.dock || 'right',
  };

  // Containment is an invariant, not a hope: clamp back into the work area.
  geometry.x = Math.min(geometry.x, work.x + w - geometry.width);
  geometry.y = Math.min(geometry.y, work.y + h - geometry.height);

  return geometry;
}

/** One line for the startup receipt — the same shape as the Rust `summary()`. */
function summary(g) {
  return [
    `docked=${g.docked}`,
    `work=${g.workWidth}x${g.workHeight}@(${g.workX},${g.workY})`,
    `window=${g.width}x${g.height}@(${g.x},${g.y})`,
    `margin=${g.margin}`,
  ].join(' ');
}

/** Geometry for the PRIMARY display's work area (screen minus the taskbar). */
function primaryGeometry() {
  const display = screen.getPrimaryDisplay();
  return {
    display,
    geometry: dockRight(display.workArea),
  };
}

// ---------------------------------------------------------------------------
// Panel window
// ---------------------------------------------------------------------------

function createPanel() {
  const { display, geometry } = primaryGeometry();

  panel = new BrowserWindow({
    x: geometry.x,
    y: geometry.y,
    width: geometry.width,
    height: geometry.height,
    minWidth: geometry.width,
    maxWidth: geometry.width,
    minHeight: geometry.height,
    maxHeight: geometry.height,
    frame: false,
    transparent: !USE_OPAQUE,
    backgroundColor: USE_OPAQUE ? '#0b0f14' : '#00000000',
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    focusable: false,
    hasShadow: false,
    show: false,
    title: 'Sotto',
    webPreferences: {
      preload: path.join(APP_DIR, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
      backgroundThrottling: false,
    },
  });

  log(
    'panel window created frame=false transparent=true alwaysOnTop=true ' +
      'skipTaskbar=true resizable=false show=false focusable=false',
  );
  log(`panel geometry: ${summary(geometry)}`);

  // Each of these is a platform call that can fail on its own; a call that
  // throws is reported rather than silently leaving a panel that steals focus.
  const attempt = (what, fn) => {
    try {
      fn();
      log(`panel ${what} ok`);
    } catch (err) {
      warn(`panel ${what} failed: ${err && err.message ? err.message : err}`);
    }
  };

  attempt('setAlwaysOnTop(floating)', () => panel.setAlwaysOnTop(true, 'floating'));
  attempt('setVisibleOnAllWorkspaces', () =>
    panel.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true }),
  );
  attempt('setFocusable(false)', () => panel.setFocusable(false));
  // Click-through by default so the overlay never eats a click meant for the
  // app underneath. `forward: true` still delivers move events to the page, which
  // is how the renderer asks for interactivity over its own controls.
  attempt('setIgnoreMouseEvents(true, forward)', () =>
    panel.setIgnoreMouseEvents(true, { forward: true }),
  );

  panel.loadFile(path.join(APP_DIR, 'panel.html'));

  // `--dump-dom`: measure the panel THE REAL WINDOW PAINTS — rects from the live
  // renderer plus a pixel capture of this very window — then exit. This exists
  // because a hand-made probe window with different options is a confound: the
  // owner reported the panel as wrong while an isolated probe measured correct
  // rects, so the measurement has to come from the window under complaint.
  if (DUMP_DOM) {
    panel.webContents.once('did-finish-load', async () => {
      const fs = require('fs');
      const probe = `(() => {
        const sels = ['#panel', '.panel__header', '.wordmark', '.captions', '#placeholder',
                      '#caption-list', '.status', '.wordmark__name', '#clear-button', '#status'];
        const out = { viewport: [innerWidth, innerHeight],
                      zoom: (window.devicePixelRatio || 1),
                      body: [document.body.scrollWidth, document.body.scrollHeight],
                      sheets: document.styleSheets.length, els: {} };
        for (const s of sels) {
          const el = document.querySelector(s);
          if (!el) { out.els[s] = null; continue; }
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          out.els[s] = { rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
                         color: cs.color, display: cs.display, position: cs.position,
                         visibility: cs.visibility, opacity: cs.opacity };
        }
        return out;
      })()`;
      try {
        const dump = await panel.webContents.executeJavaScript(probe, true);
        log(`DOMDUMP ${JSON.stringify(dump)}`);
        // Test-only: drive the SAME path Alt+C takes (`window.sotto.toggle()` -> ipc ->
        // togglePanel) so the single-instance guard is exercised by the caller that
        // matters, not by a simulation of it.
        const toggleTimes = Number(argValue('--toggle-times')) || 0;
        for (let i = 0; i < toggleTimes; i += 1) {
          await panel.webContents.executeJavaScript('window.sotto.toggle(); true', true).catch(() => {});
          await new Promise((r) => setTimeout(r, 1500));
        }
        if (toggleTimes) log(`TOGGLES_DRIVEN n=${toggleTimes}`);
        // SHOW before capturing: a never-shown window has no drawable surface and
        // capturePage() returns 0x0, which is a measurement of nothing.
        panel.showInactive();
        await new Promise((r) => setTimeout(r, 1200));
        const img = await panel.webContents.capturePage();
        const arm = USE_OPAQUE ? 'opaque' : 'transparent';
        const png = path.join(APP_DIR, '..', '..', '_main', `panel-${arm}.png`);
        fs.writeFileSync(png, img.toPNG());
        log(`DOMDUMP_CAPTURE arm=${arm} ${png} ${img.getSize().width}x${img.getSize().height}`);
      } catch (err) {
        warn(`DOMDUMP failed: ${err && err.message ? err.message : err}`);
      }
      app.exit(0);
    });
  }

  panel.on('closed', () => {
    panel = null;
  });

  return { geometry, display };
}

// ---------------------------------------------------------------------------
// Captions — the receiver side. A later milestone owns the producer (loopback
// capture + ASR) and calls these; nothing here captures or decodes audio.
// ---------------------------------------------------------------------------

/** Push a caption line into the panel. No-op if the panel is not up yet. */
function sendCaption(text, meta = {}) {
  if (!panel || panel.isDestroyed()) return false;
  if (typeof text !== 'string' || text.trim() === '') return false;
  panel.webContents.send('sotto:caption', { text: text.trim(), meta });
  return true;
}

/** Replace the status line. */
function sendStatus(text) {
  if (!panel || panel.isDestroyed()) return false;
  panel.webContents.send('sotto:status', String(text == null ? '' : text));
  return true;
}

/** Hand the renderer its geometry so CSS can size itself to the real slab. */
function sendGeometry() {
  if (!panel || panel.isDestroyed()) return false;
  const { geometry } = primaryGeometry();
  panel.webContents.send('sotto:geometry', geometry);
  return true;
}

// ---------------------------------------------------------------------------
// Show / hide
// ---------------------------------------------------------------------------

function showPanel(reason) {
  if (!panel || panel.isDestroyed()) {
    warn(`${reason}: panel is gone`);
    return false;
  }
  // showInactive, not show: showing an overlay must not steal focus from
  // whatever the user is actually doing.
  panel.showInactive();
  // Re-assert non-focusable after showing: on Windows a show can restore
  // activation for the window.
  try {
    panel.setFocusable(false);
  } catch { /* already applied */ }
  try {
    panel.blur();
  } catch { /* not focusable, nothing to blur */ }
  try {
    panel.setAlwaysOnTop(true, 'floating');
  } catch { /* best effort */ }
  log(`PANEL_SHOWN reason=${reason} bounds=${JSON.stringify(panel.getBounds())}`);
  sendGeometry();
  return true;
}

function hidePanel(reason) {
  if (!panel || panel.isDestroyed()) {
    warn(`${reason}: panel is gone`);
    return false;
  }
  panel.hide();
  log(`PANEL_HIDDEN reason=${reason}`);
  return true;
}

function togglePanel(reason) {
  if (!panel || panel.isDestroyed()) {
    warn(`${reason}: panel is gone`);
    return false;
  }
  const visible = panel.isVisible();
  if (visible) return hidePanel(reason);
  // Alt+C is the "I want captions" gesture, so showing the panel brings the
  // worker with it — otherwise the panel opens onto the stale status again,
  // which is the bug this wiring exists to remove.
  startWorker(reason);
  return showPanel(reason);
}

// ---------------------------------------------------------------------------
// The worker bridge — the wire between this shell and the Python ASR worker.
//
// The panel used to say "Waiting for audio" forever, which was a claim about
// audio. Audio is NOT the missing thing on this host: the system tap measures
// CAPTURED (peak=0.883270). The missing thing was the worker — nothing was
// connected to this panel — and the panel had no way to say so. Every state
// below therefore names the WORKER (starting / loading / listening / not
// running / not found) and never asserts that audio is absent.
//
// The caption path is the one M0 already proved: main -> IPC -> preload -> DOM
// -> `CAPTION_APPLIED`. This section only changes who calls `sendCaption`.
// ---------------------------------------------------------------------------

/**
 * Put a bridge state on screen in BOTH places the panel shows state.
 *
 * The footer status line is the primary channel (it acks as `STATUS_APPLIED`),
 * and the caption area's placeholder — which ships hardcoded as "Waiting for
 * audio" in panel.html — is rewritten so the headline matches the real state.
 * It is done with one `executeJavaScript` using the class names panel.js
 * already queries, so panel.html / panel.js / preload.js stay untouched.
 *
 * @param {string} text  the status line
 * @param {'busy'|'live'|'error'} kind
 * @param {{title?:string|null, body?:string|null}} [info] placeholder copy
 */
function applyPanelState(text, kind = 'busy', info = {}) {
  const line = String(text == null ? '' : text).trim();
  if (line === '') {
    // Never send an empty status: panel.js returns early on `!text`, which
    // would leave the previous text on screen — the stale-status bug itself.
    log('bridge status rejected: empty text would leave the stale line in place');
    return false;
  }
  const delivered = sendStatus(line);

  if (!panel || panel.isDestroyed()) return delivered;

  const script = `(() => {
    const title = ${JSON.stringify(info.title || '')};
    const body = ${JSON.stringify(info.body || '')};
    const kind = ${JSON.stringify(kind)};
    const t = document.querySelector('.captions__placeholder-title');
    const b = document.querySelector('.captions__placeholder-body');
    if (t && title) t.textContent = title;
    if (b && body) b.textContent = body;
    const s = document.getElementById('status');
    if (s) {
      s.classList.toggle('status--live', kind === 'live');
      s.classList.toggle('status--error', kind === 'error');
    }
    // Return what the panel now HEADLINES, so the placeholder rewrite is a
    // receipt and not an assumption: STATUS_APPLIED only proves the footer.
    return t ? t.textContent : '';
  })()`;
  Promise.resolve(panel.webContents.executeJavaScript(script))
    .then((shown) => {
      if (shown) log(`PLACEHOLDER_APPLIED title=${JSON.stringify(String(shown))}`);
    })
    .catch(() => {});
  return delivered;
}

/** Bring the worker up once. Idempotent: the bridge refuses a second start. */
function startWorker(reason) {
  if (SELFTEST || BRIDGE_SELFTEST) {
    // `--selftest` on its own must stay byte-for-byte the M0 receipt: no
    // worker, no Python, no caption. `--bridge-selftest` drives its own
    // throwaway workers from bridge-selftest.js instead.
    log(`WORKER_AUTOSTART=skipped reason=${BRIDGE_SELFTEST ? 'bridge-selftest' : 'selftest'}`);
    return false;
  }
  // ONE BRIDGE PER PROCESS. The bridge owns BOTH the child and its restart timer, so a
  // guard on `child` alone was wrong: after a worker death `child` becomes null while the
  // restart timer is still armed inside the SAME bridge, so the next Alt+C built a SECOND
  // bridge and spawned a SECOND python — and the first bridge's timer later spawned a
  // third, with the old bridge unreferenced but still running. Each worker is a ~2.1 GB
  // process, so repeated Alt+C multiplied memory. MEASURED 2026-10-06; the guard is now on
  // the BRIDGE, which is what actually owns the lifecycle.
  if (workerBridge) {
    log(`WORKER_AUTOSTART=reused reason=${reason}`);
    return true;
  }

  // File mode travels by env; see the TRANSCRIBE_FILE note. Set here, next to the
  // bridge that will spawn it, so the pairing is visible in one place.
  if (TRANSCRIBE_FILE) process.env.SOTTO_AUDIO_FILE = TRANSCRIBE_FILE;

  workerBridge = createBridge({
    command: PYTHON_PATH,
    workerPath: WORKER_PATH,
    device: WORKER_DEVICE || undefined,
    captureMode: WORKER_CAPTURE || undefined,
    // Only when the owner explicitly asked for a device: the live worker
    // already prefers the measured-best tap on its own.
    extraArgs: WORKER_DEVICE ? ['--device', WORKER_DEVICE] : [],
    log,
    onCaption: (text, meta) => {
      const ok = sendCaption(text, meta);
      log(`BRIDGE_CAPTION_SENT delivered=${ok} text=${JSON.stringify(text)}`);
      return ok;
    },
    onStatus: (text, kind, info) => applyPanelState(text, kind, info),
  });

  log(`WORKER_PATH ${WORKER_PATH}`);
  log(`WORKER_COMMAND ${PYTHON_PATH}`);
  if (TRANSCRIBE_FILE) log(`WORKER_MODE=file audio=${TRANSCRIBE_FILE}`);
  const started = workerBridge.start(reason);
  log(`WORKER_AUTOSTART=${started ? 'started' : 'declined'} reason=${reason}`);
  return started;
}

function stopWorker(reason) {
  if (!workerBridge) return false;
  const stopped = workerBridge.stop(reason);
  workerBridge = null;
  return stopped;
}

// ---------------------------------------------------------------------------
// Hot reload — edit a file, see it in the app that is already running.
//
// The watcher lives in hot-reload.js and knows nothing about windows or
// workers; this half owns the consequences. Two invariants make it safe: a
// reload never creates a second BrowserWindow, and it never creates a second
// worker. The app stays a single instance from first paint to last edit.
// ---------------------------------------------------------------------------

/** @type {ReturnType<typeof createHotReload>|null} */
let hotReload = null;

/** How long a restart waits for the old child to really be gone. */
const CHILD_EXIT_TIMEOUT_MS = 5000;

/**
 * Wait until a child is really gone, bounded.
 *
 * `stop()` kills the child, but kill() is a REQUEST: on Windows the process
 * dies asynchronously, and spawning the replacement in the same tick would
 * briefly put two workers on the machine — the multi-worker shape the bridge
 * guard exists to prevent. So the replacement waits for the old pid to
 * actually exit. The wait is BOUNDED, because an unbounded one would hang the
 * app on a child that never reports its exit; the timeout is named in the log
 * instead of being silent.
 *
 * @param {import('node:child_process').ChildProcess|null} child
 * @returns {Promise<'no-child'|'already-exited'|'exit'|'timeout'>}
 */
function waitForChildExit(child) {
  if (!child) return Promise.resolve('no-child');
  if (child.exitCode !== null || child.signalCode !== null) {
    return Promise.resolve('already-exited');
  }
  return new Promise((resolve) => {
    let settled = false;
    const done = (how) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(how);
    };
    const timer = setTimeout(() => done('timeout'), CHILD_EXIT_TIMEOUT_MS);
    if (timer.unref) timer.unref();
    child.once('exit', () => done('exit'));
  });
}

/**
 * Put changed panel assets into the window that is already on screen.
 *
 * `reloadIgnoringCache`, not `loadFile` and not a new BrowserWindow: the
 * window's geometry, always-on-top and click-through state are MAIN-process
 * state that a fresh window would have to rebuild, and one that rebuilds a
 * pixel differently is the exact panel the owner already reported as broken.
 * The renderer is the only thing that restarts; the process, the window and
 * the worker child are untouched — which is what keeps a capture session
 * alive across a CSS edit.
 *
 * @param {string[]} files
 */
function reloadPanelAssets(files) {
  if (!panel || panel.isDestroyed()) {
    log(`HOT_RELOAD_PANEL_SKIPPED files=${JSON.stringify(files)} reason=panel-gone`);
    return false;
  }
  panel.webContents.reloadIgnoringCache();
  // The hotkey is registered by THIS process and a renderer reload cannot
  // unregister it — but "cannot" is a claim, so it is read back here. A hotkey
  // that died in a reload is the failure the owner would feel first.
  const hotkeyRegistered = globalShortcut.isRegistered(HOTKEY);
  log(
    `HOT_RELOAD_PANEL_DONE files=${JSON.stringify(files)} alive=${!panel.isDestroyed()} ` +
      `visible=${panel.isVisible()} hotkey=${HOTKEY} hotkeyRegistered=${hotkeyRegistered}`,
  );
  if (!hotkeyRegistered) warn(`HOT_RELOAD_HOTKEY_LOST accelerator=${HOTKEY} after=${JSON.stringify(files)}`);
  return true;
}

/**
 * Restart the one worker, through the path that already exists.
 *
 * There is no second code path here: `stopWorker()` is main.js's own call into
 * `bridge.stop()` (kills the child, cancels the restart and silence timers)
 * and `startWorker()` builds exactly ONE new bridge and calls its `start()`,
 * which refuses a second start. Neither guard is bypassed or re-implemented.
 *
 * @param {string[]} files
 */
async function restartWorkerForHotReload(files) {
  if (!workerBridge) {
    // No worker means the owner never asked for one; starting one because a
 // file changed would be a 2 GB process nobody wanted.
    log(`HOT_RELOAD_WORKER_SKIPPED files=${JSON.stringify(files)} reason=no-worker-running`);
    return false;
  }
  const child = workerBridge.child;
  const oldPid = child && child.pid ? child.pid : null;
  // Armed BEFORE the stop, so it cannot miss the exit event it is waiting for.
  const exited = waitForChildExit(child);
  stopWorker('hot-reload');
  const how = await exited;
  const started = startWorker('hot-reload');
  const newPid = workerBridge && workerBridge.child ? workerBridge.child.pid : null;
  log(
    `HOT_RELOAD_WORKER_RESTART files=${JSON.stringify(files)} oldPid=${oldPid} ` +
      `oldChildExit=${how} started=${started} newPid=${newPid} ` +
      `liveChildren=${workerBridge ? workerBridge.liveChildCount : 0}`,
  );
  return started;
}

/**
 * Arm the watcher — unless this run opted out.
 *
 * `--no-hot-reload` is checked BEFORE anything is armed, so a release or
 * acceptance run cannot be disturbed by a save in an unrelated lane. A
 * PACKAGED app is exempt for the same reason: there is no source tree to
 * watch there, and a watcher in a shipped build is a liability.
 */
function startHotReload() {
  if (NO_HOT_RELOAD || app.isPackaged) {
    log(`HOT_RELOAD_DISABLED reason=${NO_HOT_RELOAD ? '--no-hot-reload' : 'packaged'}`);
    return false;
  }
  try {
    hotReload = createHotReload({
      log,
      onPanelAssetsChanged: reloadPanelAssets,
      onWorkerChanged: restartWorkerForHotReload,
      debounceMs: HOT_RELOAD_DEBOUNCE_MS,
    });
    hotReload.start();
    log(`HOT_RELOAD_ENABLED debounce_ms=${hotReload.debounceMs}`);
    return true;
  } catch (err) {
    // A watcher that cannot be armed must cost the reload feature, not the app.
    warn(`HOT_RELOAD_START_FAILED error=${JSON.stringify(err && err.message ? err.message : String(err))}`);
    hotReload = null;
    return false;
  }
}

function stopHotReload(reason = 'quit') {
  if (!hotReload) return false;
  const stopped = hotReload.stop(reason);
  hotReload = null;
  return stopped;
}

// ---------------------------------------------------------------------------
// The hotkey — the acceptance criterion that matters most
// ---------------------------------------------------------------------------

/** A hotkey failure waiting for a panel that can receive it. */
let pendingHotkeyFailure = null;

/**
 * Put a hotkey registration failure where the owner can actually see it.
 *
 * Two things make this more than a log line. First, the panel must be SHOWN:
 * with the hotkey dead nothing else would ever bring it up, so a failure that
 * was only delivered to a hidden window is a failure the owner still cannot
 * see. Second, it must survive the page not being painted yet — registration
 * happens at `whenReady`, well before `sotto:renderer-ready` — so the text is
 * held and replayed.
 *
 * @param {string} text
 * @returns {boolean} whether the panel took it right now
 */
function hotkeyFailure(text) {
  pendingHotkeyFailure = text;
  if (!panel || panel.isDestroyed()) {
    log('HOTKEY_FAILURE_DEFERRED reason=panel-not-ready');
    return false;
  }
  // A dead hotkey is the only reason this panel will ever open on its own.
  if (!panel.isVisible()) showPanel('hotkey-failed');
  const delivered = applyPanelState(text, 'error', {
    title: `Cannot use ${HOTKEY}`,
    body:
      `${text}. The panel is open now, but ${HOTKEY} will not toggle it. ` +
      'Close the other instance (or whatever owns the shortcut) and start Sotto again.',
  });
  log(`HOTKEY_FAILURE_PENDING text=${JSON.stringify(String(text).slice(0, 80))}`);
  return delivered;
}

function registerHotkey() {
  let ok = false;
  let registered = false;
  let thrown = null;
  try {
    ok = globalShortcut.register(HOTKEY, () => togglePanel(`hotkey ${HOTKEY}`));
    registered = globalShortcut.isRegistered(HOTKEY);
  } catch (err) {
    thrown = err && err.message ? err.message : String(err);
  }

  // A hotkey that silently did not register is a hotkey that does not work, so
  // this is printed as a bare token at the start of the line: `run.log` is the
  // receipt, and grep for HOTKEY_REGISTER.
  if (ok && registered) {
    console.log(
      `HOTKEY_REGISTERED accelerator=${HOTKEY} register=${ok} isRegistered=${registered} ` +
        `toggle=show|hide`,
    );
    return true;
  }

  console.error(
    `HOTKEY_REGISTER_FAILED accelerator=${HOTKEY} register=${ok} isRegistered=${registered} ` +
      `reason=another application already owns ${HOTKEY}` +
      (thrown ? ` error="${thrown}"` : ''),
  );

  // A failure the user cannot see is the same class of bug as "Waiting for
  // audio": the panel keeps advertising a gesture that does nothing, and the
  // only evidence is a line in a log nobody opens. So the failure is pushed
  // through BOTH channels the panel renders — the footer status and the
  // caption area's placeholder — with the fix stated, because "another
  // application owns Alt+C" is not actionable until you know what to close.
  const why = thrown
    ? `${HOTKEY} could not be registered: ${thrown}`
    : `${HOTKEY} is already owned by another application, so this panel cannot be toggled with it - close the other Sotto instance and start again`;
  const shown = hotkeyFailure && hotkeyFailure(why);
  log(`HOTKEY_FAILURE_ON_PANEL delivered=${shown} text=${JSON.stringify(why)}`);
  return false;
}

// ---------------------------------------------------------------------------
// IPC — renderer to main
// ---------------------------------------------------------------------------

function registerIpc() {
  ipcMain.on('sotto:renderer-ready', (_event, payload = {}) => {
    log(
      `RECEIVER_READY captions=${Number(payload.captions) || 0} ` +
        `placeholder=${JSON.stringify(String(payload.placeholder || '').slice(0, 60))}`,
    );
    sendGeometry();
    // A worker started with `--with-worker` speaks before the page has painted,
    // and an IPC message with no listener is gone. Re-send the current state so
    // the panel opens onto the truth instead of the hardcoded placeholder.
    if (workerBridge && workerBridge.lastStatus) {
      applyPanelState(workerBridge.lastStatus, workerBridge.lastKind, workerBridge.lastInfo || {});
      log(`WORKER_STATUS_REPLAYED text=${JSON.stringify(workerBridge.lastStatus)}`);
    }
    // A dead hotkey outranks the worker's state: the owner has to know the
    // gesture they are about to press is owned by something else, and it can
    // only be fixed outside this process.
    if (pendingHotkeyFailure) {
      hotkeyFailure(pendingHotkeyFailure);
      log('HOTKEY_FAILURE_REPLAYED');
    }
    if (DEMO_STATUS !== null) sendStatus(DEMO_STATUS);
    if (SELFTEST && !BRIDGE_SELFTEST) runSelfTest();
    if (BRIDGE_SELFTEST) runBridgeSelfTestMode();
  });

  // The preload layer saw a pushCaption / setStatus call.
  ipcMain.on('sotto:caption-observed', (_event, payload = {}) => {
    log(`CAPTION_OBSERVED via=preload text=${JSON.stringify(String(payload.text || ''))}`);
  });
  ipcMain.on('sotto:status-observed', (_event, payload = {}) => {
    log(`STATUS_OBSERVED via=preload text=${JSON.stringify(String(payload.text || ''))}`);
  });

  // The DOM actually changed — this is the receiver-side proof.
  ipcMain.on('sotto:caption-applied', (_event, payload = {}) => {
    captionLog.push(String(payload.text || ''));
    if (captionLog.length > MAX_CAPTIONS) captionLog.shift();
    log(
      `CAPTION_APPLIED lines=${captionLog.length} ` +
        `text=${JSON.stringify(String(payload.text || ''))}`,
    );
  });
  ipcMain.on('sotto:status-applied', (_event, payload = {}) => {
    log(`STATUS_APPLIED text=${JSON.stringify(String(payload.text || ''))}`);
  });
  ipcMain.on('sotto:caption-cleared', (_event, payload = {}) => {
    captionLog.length = 0;
    log(`CAPTIONS_CLEARED remaining=${Number(payload.remaining) || 0}`);
  });

  // --- the transcript history ("redux") -----------------------------------
  // The disk layout lives in history-store.js, the Node twin of the store in
  // app/webview/sotto_webview.py; both write the same `<date>/<HH>.md` shape.
  ipcMain.handle('sotto:history-append', (_event, payload = {}) => {
    // `payload.meta` carries the route/start/reason the panel stamped on the
    // line (M7/M8). It crossed the IPC and was dropped here before.
    const entry = historyStore.append(payload.text, payload.meta);
    if (entry) {
      log(
        `HISTORY_APPEND path=${JSON.stringify(entry.path)} time=${entry.time} ` +
          `bytes=${Buffer.byteLength(entry.text, 'utf8')}`,
      );
    }
    return { entry };
  });
  ipcMain.handle('sotto:history-tail', (_event, payload = {}) => historyStore.tail(payload.limit));
  ipcMain.handle('sotto:history-search', (_event, payload = {}) =>
    historyStore.search(payload.query, payload.limit),
  );
  ipcMain.handle('sotto:history-root', () => historyStore.root());
  ipcMain.on('sotto:history-reveal', (_event, payload = {}) => {
    const target = String(payload.path == null ? '' : payload.path);
    const ok = historyStore.reveal(target);
    log(`REVEAL_IN_FOLDER path=${JSON.stringify(target)} ok=${ok}`);
  });

  // What the panel asked for at first paint: the hotkey it must advertise, the
  // versions it is running on, and the geometry it was actually placed at.
  ipcMain.handle('sotto:info', () => {
    const { geometry } = primaryGeometry();
    return {
      hotkey: HOTKEY,
      hotkeyRegistered: globalShortcut.isRegistered(HOTKEY),
      electron: process.versions.electron,
      chrome: process.versions.chrome,
      node: process.versions.node,
      platform: process.platform,
      geometry,
      captions: captionLog.length,
      startedAt: new Date().toISOString(),
    };
  });

  // Interactivity over the panel's own controls, without giving up click-through
  // over the transparent margin around them.
  ipcMain.on('sotto:pointer', (_event, payload = {}) => {
    const active = Boolean(payload.active);
    try {
      panel.setIgnoreMouseEvents(!active, { forward: true });
      log(`POINTER_INTERACTIVE=${active}`);
    } catch (err) {
      warn(`setIgnoreMouseEvents failed: ${err && err.message ? err.message : err}`);
    }
  });

  ipcMain.on('sotto:hide', () => hidePanel('renderer'));
  ipcMain.on('sotto:toggle', () => togglePanel('renderer'));
  ipcMain.on('sotto:quit', () => app.quit());
}

// ---------------------------------------------------------------------------
// Self-test — proves the toggle and the caption receiver without a human at the
// keyboard. Exit code 0 = every step observed, 3 = a step did not observe.
// ---------------------------------------------------------------------------

function runSelfTest() {
  const steps = [];
  const finish = () => {
    const failed = steps.filter((s) => !s.ok);
    log(`SELFTEST_STEPS ${steps.map((s) => `${s.name}=${s.ok ? 'ok' : 'FAIL'}`).join(' ')}`);
    log(`SELFTEST_RESULT ${failed.length === 0 ? 'PASS' : 'FAIL'} steps=${steps.length}`);
    app.exit(failed.length === 0 ? 0 : 3);
  };

  // Start from a KNOWN state. --selftest shows the panel at startup so the
  // owner can see it, so "toggle means show" is only true after an explicit
  // hide. Asserting a transition without pinning its starting state tests the
  // test's assumption, not the code.
  if (panel && panel.isVisible()) hidePanel('selftest-reset');

  // 1. The handler Alt+C calls, invoked the way the hotkey invokes it: hidden
  //    -> visible.
  setTimeout(() => {
    const shown = togglePanel('selftest') && panel.isVisible();
    steps.push({ name: 'hotkey-show', ok: shown });
    log(`SELFTEST hotkey-show visible=${panel.isVisible()}`);

    // 2. And again, to prove it toggles both ways.
    setTimeout(() => {
      const hidden = togglePanel('selftest') && !panel.isVisible();
      steps.push({ name: 'hotkey-hide', ok: hidden });
      log(`SELFTEST hotkey-hide visible=${panel.isVisible()}`);

      setTimeout(() => {
        // 3. Leave the panel visible so the owner sees it, then push one caption
        //    down the exact path a later milestone will use: main -> IPC ->
        //    preload -> DOM -> ack.
        showPanel('selftest');
        const probe = DEMO_CAPTION || 'selftest caption - receiver is live';
        const delivered = sendCaption(probe, { source: 'selftest' });
        log(`SELFTEST caption-sent delivered=${delivered} text=${JSON.stringify(probe)}`);
        const statusProbe = DEMO_STATUS || 'selftest: caption receiver verified';
        log(`SELFTEST status-sent delivered=${sendStatus(statusProbe)} text=${JSON.stringify(statusProbe)}`);

        // Give the renderer time to apply, then let the ack decide.
        setTimeout(() => {
          const applied = captionLog.some((t) => t === probe.trim());
          steps.push({ name: 'caption-applied', ok: applied });
          log(`SELFTEST caption-applied acknowledged=${applied} lines=${captionLog.length}`);

          // 4. The other direction: the preload API itself, called from the page.
          //    The caption above arrived over IPC; this one goes through
          //    contextBridge (`window.sotto.pushCaption`), which is the API a
          //    later milestone is told to call.
          const bridgeProbe = 'page-bridge caption via window.sotto.pushCaption';
          log(`SELFTEST bridge-sending text=${JSON.stringify(bridgeProbe)}`);
          Promise.resolve(
            panel.webContents.executeJavaScript(
              `window.sotto.pushCaption(${JSON.stringify(bridgeProbe)})`,
            ),
          )
            .then(() => new Promise((resolve) => setTimeout(resolve, 800)))
            .then(() => {
              const bridgeOk = captionLog.includes(bridgeProbe);
              steps.push({ name: 'bridge-pushCaption', ok: bridgeOk });
              log(`SELFTEST bridge-pushCaption acknowledged=${bridgeOk} lines=${captionLog.length}`);
            })
            .catch((err) => {
              steps.push({ name: 'bridge-pushCaption', ok: false });
              log(`SELFTEST bridge-pushCaption threw: ${err && err.message ? err.message : err}`);
            })
            .then(finish);
        }, 1500);
      }, 800);
    }, 800);
  }, 800);
}

// ---------------------------------------------------------------------------
// Bridge self-test — the same steps bridge-selftest.js runs under plain node,
// but with the panel as the sink, so the proof covers IPC -> preload -> DOM ->
// `CAPTION_APPLIED` rather than just the parser. Exit 0 / 3, never a lie.
// ---------------------------------------------------------------------------

async function runBridgeSelfTestMode() {
  if (!panel || panel.isDestroyed()) {
    warn('bridge-selftest: panel is gone');
    app.exit(3);
    return;
  }
  if (!panel.isVisible()) showPanel('bridge-selftest');
  log('BRIDGE_SELFTEST mode=panel sink=ipc');

  let result;
  try {
    result = await runBridgeSelfTest({
      isPanel: true,
      log,
      onCaption: (text, meta) => sendCaption(text, meta),
      onStatus: (text, kind, info) => applyPanelState(text, kind, info),
      acked: () => captionLog.slice(),
    });
  } catch (err) {
    warn(`bridge-selftest threw: ${err && err.stack ? err.stack : err}`);
    log('BRIDGE_SELFTEST FAIL threw=1 rc=3');
    app.exit(3);
    return;
  }

  // The DOM ack is asynchronous; give the last `caption-applied` a moment to
  // land before the verdict, or the step would measure IPC timing, not the code.
  await new Promise((resolve) => setTimeout(resolve, 800));
  const rc = printResult(result);
  log(`BRIDGE_SELFTEST rc=${rc}`);
  app.exit(rc);
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

// One instance, or two processes fighting over Alt+C: the second one hands the
// panel to the first and exits, rather than silently failing to register.
if (!app.requestSingleInstanceLock()) {
  log('second instance detected; handing the panel to the running one');
  // A self-test that never ran must not exit 0 — 0 is the PASS signal, and a
  // lock collision would otherwise be a silent, unearned pass.
  if (BRIDGE_SELFTEST) {
    console.error('BRIDGE_SELFTEST FAIL reason=single-instance-lock-held rc=3');
    app.exit(3);
  } else {
    app.exit(0);
  }
} else {
  app.on('second-instance', () => showPanel('second-instance'));

  app.whenReady().then(() => {
    log(`electron version=${process.versions.electron} chrome=${process.versions.chrome} node=${process.versions.node}`);

    const { display } = createPanel();
    log(
      `primary display bounds=${JSON.stringify(display.bounds)} ` +
        `workArea=${JSON.stringify(display.workArea)} scaleFactor=${display.scaleFactor}`,
    );

    registerIpc();
    registerHotkey();

    // Armed after the hotkey so the FIRST thing a reload has to preserve is
    // already registered and can be read back in the same log.
    startHotReload();

    if (START_VISIBLE) showPanel(SELFTEST ? 'startup-selftest' : 'startup --show');
    if (WITH_WORKER || TRANSCRIBE_FILE) {
      startWorker(TRANSCRIBE_FILE ? 'startup --transcribe' : 'startup --with-worker');
    }

    // A bounded acceptance run ends on its own terms, so its log is complete
    // rather than truncated by whoever killed it.
    if (EXIT_AFTER > 0) {
      log(`EXIT_AFTER=${EXIT_AFTER}s`);
      setTimeout(() => {
        log(`EXIT_TIMER elapsed=${EXIT_AFTER}s captions=${captionLog.length}`);
        app.exit(captionLog.length > 0 ? 0 : 4);
      }, EXIT_AFTER * 1000);
    }

    if (workerBridge) {
      log(`idle: worker bridge live (${WORKER_PATH}), panel hidden until ${HOTKEY}`);
    } else {
      log(`idle: no audio capture, no model loaded, panel hidden until ${HOTKEY}`);
    }
  });

  // A hotkey that survives quitting is a hotkey that fires into nothing.
  app.on('will-quit', () => {
    if (globalShortcut.isRegistered(HOTKEY)) globalShortcut.unregister(HOTKEY);
    globalShortcut.unregisterAll();
    // Never orphan the Python worker: a panel that quits and leaves a
    // transcriber running is a leak nobody asked for. The watcher goes first:
    // armed, it could restart the worker this very teardown is killing.
    stopHotReload('will-quit');
    stopWorker('will-quit');
    log('HOTKEY_UNREGISTERED on quit');
  });
}