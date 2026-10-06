// Scratch probe: WHY does the panel lay out in a narrow left column?
// Loads panel.html at the real window size and dumps measured rects + computed
// styles. No vision: numbers only. Never shows a window.
const { app, BrowserWindow } = require('electron');
const path = require('path');

const APP_DIR = path.join(__dirname, '..', 'app', 'electron');
const SIZE = { width: 380, height: 900 };

const JS = `(() => {
  const pick = ['#panel', '.panel__header', '.wordmark', '.captions', '#placeholder',
                '#caption-list', '.status', '.wordmark__name', '#clear-button'];
  const g = (sel, prop) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
      display: cs.display,
      position: cs.position,
      width: cs.width,
      height: cs.height,
      color: cs.color,
      bg: cs.backgroundColor,
      opacity: cs.opacity,
      visibility: cs.visibility,
      overflow: cs.overflow,
      fontSize: cs.fontSize,
    };
  };
  const out = { viewport: [window.innerWidth, window.innerHeight],
                body: [document.body.scrollWidth, document.body.scrollHeight],
                html: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
                sheets: document.styleSheets.length,
                rules: Array.from(document.styleSheets).map(s => { try { return s.cssRules.length } catch (e) { return 'ERR' } }),
                els: {} };
  for (const sel of pick) out.els[sel] = g(sel);
  return out;
})()`;

app.disableHardwareAcceleration();
app.whenReady().then(async () => {
  const win = new BrowserWindow({
    width: SIZE.width,
    height: SIZE.height,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(APP_DIR, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  await win.loadFile(path.join(APP_DIR, 'panel.html'));
  await new Promise((r) => setTimeout(r, 700));
  try {
    const dump = await win.webContents.executeJavaScript(JS, true);
    console.log('PROBE ' + JSON.stringify(dump, null, 2));
  } catch (err) {
    console.log('PROBE_FAILED ' + (err && err.message));
  }
  app.exit(0);
});
