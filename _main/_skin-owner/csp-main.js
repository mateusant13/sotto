const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');
const OUT = 'H:\\sotto\\_main\\_skin-owner';
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
app.whenReady().then(async () => {
  const report = {};
  const save = () => fs.writeFileSync(path.join(OUT, 'csp-report.json'), JSON.stringify(report, null, 1));
  for (const page of ['page.html', 'page-strict.html']) {
    const win = new BrowserWindow({ show:false, width:420, height:320, useContentSize:true, webPreferences:{ contextIsolation:true, nodeIntegration:false } });
    const wc = win.webContents;
    const notes = [];
    wc.on('console-message', (_e, level, message) => { notes.push(level + ': ' + String(message).slice(0,200)); });
    try {
      await win.loadURL('file:///H:/sotto/_main/_skin-owner/csp/' + page);
      await sleep(1800);
      const res = await wc.executeJavaScript('window.__CSP_RESULT || null', true);
      report[page] = { result: res, console: notes };
    } catch (e) {
      report[page] = { loadError: String(e && e.message || e), console: notes };
    }
    save();
    win.destroy();
  }
  app.exit(0);
}).catch((e)=>{ fs.writeFileSync(path.join(OUT,'csp-error.txt'), String(e&&e.stack||e)); app.exit(1); });
