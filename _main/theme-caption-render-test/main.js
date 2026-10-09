/* Sotto — the Electron host for the CAPTION STRUCTURE render instrument.
 *
 *   H:/sotto/app/node_modules/electron/dist/electron.exe \
 *       _main/theme-caption-render-test/main.js --no-sandbox
 *
 * A hidden window (`show: false`), the REAL stylesheets, the REAL manifest, and the
 * driver as a separate file so `node --check driver.js` checks exactly what runs.
 * Exit code is the verdict. Nothing here is hard-coded per theme: every check is
 * relational, because a hard-coded expectation is a second copy of a design that
 * drifts the day the generator moves.
 */
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const PAGE = path.join(__dirname, 'page.html');
const DRIVER = fs.readFileSync(path.join(__dirname, 'driver.js'), 'utf8');

app.disableHardwareAcceleration();

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    show: false,
    width: 380,
    height: 900,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });
  try {
    await win.loadFile(PAGE);
    const result = await win.webContents.executeJavaScript(DRIVER, true);
    const checks = result.checks || {};
    const failed = Object.keys(checks).filter((k) => checks[k] !== true);
    const errors = result.errors || [];
    const ok = failed.length === 0 && errors.length === 0;
    console.log('RESULT ' + JSON.stringify({
      ok, failed, errors, checks, observations: result.observations,
    }, null, 2));
    console.log(ok ? 'VERDICT: PASS' : 'VERDICT: FAIL');
    app.exit(ok ? 0 : 1);
  } catch (err) {
    console.log('RESULT ' + JSON.stringify({ ok: false, error: String((err && err.stack) || err) }));
    console.log('VERDICT: FAIL');
    app.exit(1);
  }
});

app.on('window-all-closed', () => app.exit(1));
