/* Sotto — hidden Electron host for the strip-minimal verification.
 *
 *   H:\sotto\app\node_modules\electron\dist\electron.exe \
 *       _main\_strip-minimal-verify\main.js --no-sandbox
 *
 * The REAL `app/panel/panel.html` with the REAL stylesheets and scripts; the
 * only fiction is the bridge (`_main/_skin-owner/render/preload.js`, the
 * panel's own contract stubbed — the same pair of calls the shell makes).
 * Hidden window: this measures the DOM, never the owner's screen.
 * Writes `report.json` next to itself. Exit code is the verdict.
 */
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const PAGE = 'H:\\sotto\\app\\panel\\panel.html';
const OUT = 'H:\\sotto\\_main\\_strip-minimal-verify';
const DRIVER = fs.readFileSync(path.join(OUT, 'driver.js'), 'utf8');
const PRELOAD = 'H:\\sotto\\_main\\_skin-owner\\render\\preload.js';

app.disableHardwareAcceleration();

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    show: false,
    width: 380,
    height: 900,
    useContentSize: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: false,
      preload: PRELOAD,
    },
  });
  const wc = win.webContents;
  const pageErrors = [];
  wc.on('console-message', (event) => {
    const level = event && typeof event.level === 'number' ? event.level : 0;
    const message = String((event && (event.message || event)) || '').slice(0, 300);
    if (level >= 2 || message.indexOf('Refused to') >= 0) pageErrors.push(message);
  });
  try {
    await win.loadFile(PAGE);
    await new Promise((r) => setTimeout(r, 500));
    const result = await wc.executeJavaScript(DRIVER, true);
    const checks = result.checks || {};
    const failed = Object.keys(checks).filter((k) => checks[k] !== true);
    const errors = (result.errors || []).concat(pageErrors);
    const ok = failed.length === 0 && errors.length === 0;
    delete result.checks;
    delete result.errors;
    fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify({
      ok, failed, errors, checks, detail: result,
    }, null, 2));
    console.log('FAILED ' + JSON.stringify(failed));
    console.log('ERRORS ' + JSON.stringify(errors.slice(0, 8)));
    console.log('VERDICT: ' + (ok ? 'PASS' : 'FAIL'));
    app.exit(ok ? 0 : 1);
  } catch (err) {
    fs.writeFileSync(path.join(OUT, 'error.txt'), String((err && err.stack) || err));
    console.log('VERDICT: FAIL ' + String((err && err.message) || err));
    app.exit(1);
  }
});

app.on('window-all-closed', () => app.exit(1));
