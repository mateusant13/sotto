/* Sotto — the Electron host for the SKIN render instrument.
 *
 *   H:/sotto/app/node_modules/electron/dist/electron.exe \
 *       _main/_skin-owner/render/main.js --no-sandbox
 *
 * The REAL `app/panel/panel.html`, the REAL stylesheets, the REAL `skins/skins.js`
 * and the REAL `skin-host.js`. The only fiction is the bridge (`preload.js`), which
 * is the panel's own contract stubbed — the same pair of calls the shell makes.
 *
 * It writes a screenshot per design into `_main/_skin-owner/render/shots/` so the
 * result can be LOOKED at, and a JSON report. Exit code is the verdict.
 */
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const PAGE = 'H:\\sotto\\app\\panel\\panel.html';
const OUT = path.join('H:\\sotto\\_main\\_skin-owner', 'render');
const SHOTS = path.join(OUT, 'shots');
const DRIVER = fs.readFileSync(path.join(OUT, 'driver.js'), 'utf8');
const PRELOAD = path.join(OUT, 'preload.js');

app.disableHardwareAcceleration();

app.whenReady().then(async () => {
  if (!fs.existsSync(SHOTS)) fs.mkdirSync(SHOTS, { recursive: true });
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
    await new Promise((r) => setTimeout(r, 400));
    const result = await wc.executeJavaScript(DRIVER, true);
    // ONE SHOT PER DESIGN, DRIVEN HERE: `capturePage` is a main-process call, so the
    // driver hands back a plan and this loop sets the theme, feeds a line and shoots
    // — a screenshot taken after the whole walk would show only the last design.
    for (const item of (result.shootPlan || [])) {
      const script = '(() => {'
        + ' document.documentElement.dataset.theme = ' + JSON.stringify(item.theme) + ';'
        + ' var b = window.sotto;'
        + ' b.pushCaption(' + JSON.stringify(item.first) + ','
        + '   { start: 3, end: 6, final: false, route: "provisional-draft" });'
        + ' return true; })()';
      await wc.executeJavaScript(script, true);
      await new Promise((r) => setTimeout(r, 260));
      const script2 = '(() => { window.sotto.pushCaption(' + JSON.stringify(item.second) + ','
        + ' { start: 3, end: 9, final: true, route: "final" }); return true; })()';
      await wc.executeJavaScript(script2, true);
      await new Promise((r) => setTimeout(r, 320));
      const image = await wc.capturePage();
      fs.writeFileSync(path.join(SHOTS, item.name + '.png'), image.toPNG());
      result.shoot.push(item.name);
    }
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
