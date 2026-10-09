const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');
const PAGE = 'file:///H:/sotto/_main/_design-lane/zips/cinematic-2/dist/index.html';
const OUT = 'H:\\sotto\\_main\\_skin-owner';
const W = parseInt(process.env.SOTTO_W || '380', 10);
const H = parseInt(process.env.SOTTO_H || '900', 10);
const TAG = process.env.SOTTO_TAG || 'keys';
const KEYS = (process.env.SOTTO_KEYS || 'h').split(',').filter(Boolean);
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
app.whenReady().then(async () => {
  const win = new BrowserWindow({ show:false, width:W, height:H, useContentSize:true,
    webPreferences:{ contextIsolation:true, nodeIntegration:false } });
  const wc = win.webContents;
  await win.loadURL(PAGE);
  await sleep(2600);
  const log = [];
  let i = 0;
  for (const k of KEYS) {
    wc.sendInputEvent({ type:'keyDown', keyCode:k });
    wc.sendInputEvent({ type:'keyUp', keyCode:k });
    await sleep(1300);
    i += 1;
    const img = await wc.capturePage();
    const name = TAG + '-k' + i + '-' + k + '.png';
    fs.writeFileSync(path.join(OUT, name), img.toPNG());
    const facts = await wc.executeJavaScript('(() => { const cands=[...document.querySelectorAll("div")].filter(d=>{const cs=getComputedStyle(d); const r=d.getBoundingClientRect(); return cs.position==="absolute" && r.width>200 && r.height>60 && !d.children.length===false && r.height<420;}); const out=cands.slice(0,8).map(d=>{const r=d.getBoundingClientRect(); return {cls:String(d.className||"").slice(0,70), r:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)]};}); return {viewport:[innerWidth,innerHeight], boxes:out}; })()', true);
    log.push({ key: k, name: name, facts: facts });
  }
  fs.writeFileSync(path.join(OUT, TAG + '-log.json'), JSON.stringify(log, null, 1));
  app.exit(0);
}).catch((e)=>{ fs.writeFileSync(path.join(OUT,'error.txt'), String(e&&e.stack||e)); app.exit(1); });
