const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');
const PAGE = 'file:///H:/sotto/_main/_design-lane/zips/cinematic-2/dist/index.html';
const OUT = 'H:\\sotto\\_main\\_skin-owner';
const W = parseInt(process.env.SOTTO_W || '1280', 10);
const H = parseInt(process.env.SOTTO_H || '900', 10);
const TAG = process.env.SOTTO_TAG || 'g';
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
app.whenReady().then(async () => {
  const win = new BrowserWindow({ show:false, width:W, height:H, useContentSize:true,
    webPreferences:{ contextIsolation:true, nodeIntegration:false } });
  const wc = win.webContents;
  await win.loadURL(PAGE);
  await sleep(2600);
  let img = await wc.capturePage();
  fs.writeFileSync(path.join(OUT, TAG + '-00.png'), img.toPNG());
  wc.sendInputEvent({ type:'keyDown', keyCode:'G' });
  wc.sendInputEvent({ type:'keyUp', keyCode:'G' });
  await sleep(1400);
  img = await wc.capturePage();
  fs.writeFileSync(path.join(OUT, TAG + '-gallery.png'), img.toPNG());
  const n = await wc.executeJavaScript('document.querySelectorAll("button").length', true);
  fs.writeFileSync(path.join(OUT, TAG + '-meta.json'), JSON.stringify({ w:W, h:H, buttons:n }, null, 1));
  app.exit(0);
}).catch((e)=>{ fs.writeFileSync(path.join(OUT,'error.txt'), String(e&&e.stack||e)); app.exit(1); });
