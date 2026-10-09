/* Sotto — the RENDER runner for the REVIVE instrument.
 *
 *   H:/sotto/app/node_modules/electron/dist/electron.exe \
 *       _main/revive-panel-render-test/main.js
 *
 * A real Chromium, a HIDDEN window (`show: false`, never shown), the REAL
 * `app/panel/panel.html` — built into `_page.html` in this directory by
 * `_main/revive-pipeline-oracle.py`, which is also what decides WHICH
 * `panel.js` the page loads (the shipped one, or a one-line mutant for the
 * negative arm) — and a fake bridge injected by `preload.js` before any page
 * script runs.
 *
 * WHY THE REAL PAGE. The feature is a listener on `#status`/`#strip-state`
 * that `panel.js` installs at init. A stand-in page would have to re-implement
 * the very wiring under test, and would pass while the shipped document did
 * nothing.
 *
 * `SOTTO_REVIVE_ABSENT=1` makes `preload.js` leave `bridge.revive` out
 * entirely: that is the honesty arm, and it is the same switch for both
 * colours — one runner, one driver, one page.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { app, BrowserWindow } = require('electron');

const PAGE = path.join(__dirname, '_page.html');
const DRIVER = fs.readFileSync(path.join(__dirname, 'driver.js'), 'utf8');
const PRELOAD = path.join(__dirname, 'preload.js');

app.disableHardwareAcceleration();

function finish(payload, code) {
  console.log('RESULT ' + JSON.stringify(payload, null, 2));
  console.log(code === 0 ? 'VERDICT: PASS' : 'VERDICT: FAIL');
  app.exit(code);
}

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    show: false,
    width: 380,
    height: 900,
    webPreferences: {
      preload: PRELOAD,
      contextIsolation: false,
      nodeIntegration: false,
    },
  });
  try {
    await win.loadFile(PAGE);
    const first = await win.webContents.executeJavaScript(DRIVER, true);

    // PHASE 2 is a fresh document on purpose: the panel's in-flight guard lasts
    // 10 s by design, so the keyboard path can only be measured on a page that
    // has not already asked for a revive.
    let second = { checks: {}, observations: {}, errors: [] };
    if (first.observations && first.observations.elements
        && first.observations.elements.hasRevive) {
      const loaded = new Promise((resolve) => win.webContents.once('did-finish-load', resolve));
      win.webContents.reload();
      await loaded;
      await win.webContents.executeJavaScript('window.__reviveProbePhase = 2', true);
      second = await win.webContents.executeJavaScript(DRIVER, true);
    }

    const checks = Object.assign({}, first.checks, second.checks);
    const errors = [].concat(first.errors || [], second.errors || []);
    const failed = Object.keys(checks).filter((k) => checks[k] !== true);
    const ok = failed.length === 0 && errors.length === 0 && first.ok !== false;
    finish({
      ok: ok, failed: failed, errors: errors, checks: checks,
      observations: Object.assign({}, first.observations, second.observations),
    }, ok ? 0 : 1);
  } catch (err) {
    finish({ ok: false, error: String((err && err.stack) || err) }, 1);
  }
});

app.on('window-all-closed', () => app.exit(1));
