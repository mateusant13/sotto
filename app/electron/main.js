'use strict';

/**
 * Sotto M0 — the shell. Electron main process.
 *
 * M0's only job is to exist measurably: the panel opens, Alt+C toggles it, and
 * the window behaviour is provable from stdout without a screenshot. There is no
 * audio capture and no model here — the caption area is a receiver waiting for
 * a later milestone to feed it (see `pushCaption` in preload.js).
 *
 * Why Electron and not the Tauri build next door: the Tauri/Rust tree at
 * ../src-tauri cannot be built on this host — cargo hangs at "Updating
 * crates.io index" on both the gnu and msvc toolchains while curl on the same
 * host returns in 0.15 s. Rust is out of scope for this milestone; this file is
 * the shell, and nothing under ../src-tauri is read at runtime or written to.
 */

const { app, BrowserWindow, globalShortcut, ipcMain, screen } = require('electron');
const path = require('node:path');

/** The global toggle. Global rather than window-local is the whole point: the
 *  panel is hidden most of the time, so a hotkey that only worked while the
 *  panel had focus would never fire. Matches HOTKEY in ../src-tauri/src/main.rs. */
const HOTKEY = 'Alt+C';

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
const SELFTEST = ARGS.has('--selftest');
const START_VISIBLE = ARGS.has('--show') || SELFTEST;
const DEMO_CAPTION = argValue('--caption');
const DEMO_STATUS = argValue('--status');

/** @type {BrowserWindow|null} */
let panel = null;
/** Capped mirror of what the renderer is showing, for the startup receipt and
 *  the self-test. The renderer is the source of truth for the DOM; this is the
 *  main process's answer to "did a caption actually arrive". */
const captionLog = [];

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
    transparent: true,
    backgroundColor: '#00000000',
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
  return visible ? hidePanel(reason) : showPanel(reason);
}

// ---------------------------------------------------------------------------
// The hotkey — the acceptance criterion that matters most
// ---------------------------------------------------------------------------

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
  } else {
    console.error(
      `HOTKEY_REGISTER_FAILED accelerator=${HOTKEY} register=${ok} isRegistered=${registered} ` +
        `reason=another application already owns ${HOTKEY}` +
        (thrown ? ` error="${thrown}"` : ''),
    );
  }
  return ok && registered;
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
    if (DEMO_STATUS !== null) sendStatus(DEMO_STATUS);
    if (SELFTEST) runSelfTest();
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

  // 1. The handler that Alt+C calls, invoked the same way the hotkey invokes it.
  steps.push({ name: 'toggle-show', ok: togglePanel('selftest') && panel.isVisible() });
  log(`SELFTEST toggle-show visible=${panel.isVisible()}`);

  setTimeout(() => {
    // 2. And again, to prove it toggles both ways.
    steps.push({ name: 'toggle-hide', ok: togglePanel('selftest') && !panel.isVisible() });
    log(`SELFTEST toggle-hide visible=${panel.isVisible()}`);

    setTimeout(() => {
      // 3. Leave the panel visible so the owner sees it, then push one caption
      //    down the exact path a later milestone will use: main -> IPC ->
      //    preload -> DOM -> ack.
      showPanel('selftest');
      const probe = DEMO_CAPTION || 'selftest caption — receiver is live';
      const delivered = sendCaption(probe, { source: 'selftest' });
      log(`SELFTEST caption-sent delivered=${delivered} text=${JSON.stringify(probe)}`);
      const statusProbe = DEMO_STATUS || 'selftest: caption receiver verified';
      log(`SELFTEST status-sent delivered=${sendStatus(statusProbe)} text=${JSON.stringify(statusProbe)}`);

      // Give the renderer time to apply, then let the ack decide.
      setTimeout(() => {
        const applied = captionLog.some((t) => t === probe.trim());
        steps.push({ name: 'caption-applied', ok: applied });
        finish();
      }, 1500);
    }, 800);
  }, 800);
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

// One instance, or two processes fighting over Alt+C: the second one hands the
// panel to the first and exits, rather than silently failing to register.
if (!app.requestSingleInstanceLock()) {
  log('second instance detected; handing the panel to the running one');
  app.exit(0);
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

    if (START_VISIBLE) showPanel(SELFTEST ? 'startup-selftest' : 'startup --show');

    log(`idle: no audio capture, no model loaded, panel hidden until ${HOTKEY}`);
  });

  // A hotkey that survives quitting is a hotkey that fires into nothing.
  app.on('will-quit', () => {
    if (globalShortcut.isRegistered(HOTKEY)) globalShortcut.unregister(HOTKEY);
    globalShortcut.unregisterAll();
    log('HOTKEY_UNREGISTERED on quit');
  });
}