const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');
const PAGE = 'file:///H:/sotto/_main/_design-lane/zips/cinematic-2/dist/index.html';
const OUT = 'H:\\sotto\\_main\\_skin-owner';
const W = parseInt(process.env.SOTTO_W || '380', 10);
const H = parseInt(process.env.SOTTO_H || '900', 10);
const TAG = process.env.SOTTO_TAG || 'click';
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
const probe = '(() => { const bs=[...document.querySelectorAll("button")]; const want=bs.filter(b=>((b.title||"")+(b.getAttribute("aria-label")||"")).toLowerCase().indexOf("hide panel")>=0); if(!want.length) return "NOTFOUND"; want[0].click(); return "CLICKED"; })()';
const facts = '(() => { const r=(el)=>{const b=el.getBoundingClientRect();return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)];}; const cap=[...document.querySelectorAll("div")].filter(d=>{const t=(d.textContent||""); const cs=getComputedStyle(d); return cs.position==="absolute" && d.className && String(d.className).indexOf("absolute")>=0 && t.indexOf("ON-DEVICE")>=0;}); const out={viewport:[innerWidth,innerHeight],caption:cap.length?r(cap[cap.length-1]):null,big:[]}; for(const el of document.querySelectorAll("span,p,div")){ if(el.children.length) continue; const t=(el.textContent||"").trim(); if(t.length<3) continue; const cs=getComputedStyle(el); const sz=parseFloat(cs.fontSize)||0; if(sz<18) continue; out.big.push({t:t.slice(0,40),sz:Math.round(sz*10)/10,r:r(el)}); } out.big=out.big.slice(0,8); return out; })()';
app.whenReady().then(async () => {
  const win = new BrowserWindow({ show:false, width:W, height:H, useContentSize:true, webPreferences:{ contextIsolation:true, nodeIntegration:false } });
  const wc = win.webContents;
  await win.loadURL(PAGE);
  await sleep(2600);
  let img = await wc.capturePage(); fs.writeFileSync(path.join(OUT, TAG+'-before.png'), img.toPNG());
  const res = await wc.executeJavaScript(probe, true);
  await sleep(1300);
  img = await wc.capturePage(); fs.writeFileSync(path.join(OUT, TAG+'-after.png'), img.toPNG());
  const f = await wc.executeJavaScript(facts, true);
  fs.writeFileSync(path.join(OUT, TAG+'-facts.json'), JSON.stringify({click:res, facts:f}, null, 1));
  app.exit(0);
}).catch((e)=>{ fs.writeFileSync(path.join(OUT,'error2.txt'), String(e&&e.stack||e)); app.exit(1); });
