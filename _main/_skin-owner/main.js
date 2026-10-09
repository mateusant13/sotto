// OWNER LANE — look at the vendor app with my own eyes before designing the host.
// Not a gate, not a receipt: a camera. One page, one 380x900 window, PNGs + a DOM dump.
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const PAGE = process.env.SOTTO_SKIN_PAGE
  || 'file:///H:/sotto/_main/_design-lane/zips/cinematic-2/dist/index.html';
const OUT = 'H:\\sotto\\_main\\_skin-owner';
const DRIVER = path.join(__dirname, 'driver.js');
const SHOTS = process.env.SOTTO_SKIN_SHOTS || '';

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    show: false,
    width: 380,
    height: 900,
    useContentSize: true,
    webPreferences: { offscreen: false, contextIsolation: true, nodeIntegration: false },
  });
  const wc = win.webContents;
  const errors = [];
  wc.on('console-message', (_e, level, message) => {
    if (level >= 2) errors.push(String(message).slice(0, 300));
  });
  await win.loadURL(PAGE);
  await sleep(2500);

  const driver = fs.readFileSync(DRIVER, 'utf8');
  const probe = await wc.executeJavaScript(driver, true);
  fs.writeFileSync(path.join(OUT, 'probe.json'), JSON.stringify(probe, null, 1));

  const shot = await wc.capturePage();
  fs.writeFileSync(path.join(OUT, 'shot-default.png'), shot.toPNG());

  // Walk whatever design controls the driver found and shoot each one.
  const targets = (probe && probe.designControls) || [];
  const report = { page: PAGE, errors, shots: ['shot-default.png'], controls: targets.length };
  for (let i = 0; i < targets.length && i < 14; i += 1) {
    const sel = targets[i].selector;
    const ok = await wc.executeJavaScript(
      '(() => { const el = document.querySelector(' + JSON.stringify(sel) + ');'
      + ' if (!el) return false; el.click(); return true; })()', true);
    if (!ok) continue;
    await sleep(1200);
    const name = 'shot-' + String(i).padStart(2, '0') + '.png';
    const img = await wc.capturePage();
    fs.writeFileSync(path.join(OUT, name), img.toPNG());
    report.shots.push(name);
  }
  if (SHOTS) fs.writeFileSync(SHOTS, JSON.stringify(report, null, 1));
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 1));
  app.exit(0);
}).catch((err) => {
  fs.writeFileSync(path.join(OUT, 'error.txt'), String(err && err.stack || err));
  app.exit(1);
});
