// OWNER LANE camera v2 — size-parameterized, walks the vendor's OWN design affordance.
// Env: SOTTO_SKIN_PAGE, SOTTO_W, SOTTO_H, SOTTO_TAG, SOTTO_STEPS
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const PAGE = process.env.SOTTO_SKIN_PAGE
  || 'file:///H:/sotto/_main/_design-lane/zips/cinematic-2/dist/index.html';
const W = parseInt(process.env.SOTTO_W || '380', 10);
const H = parseInt(process.env.SOTTO_H || '900', 10);
const TAG = process.env.SOTTO_TAG || 'cine2';
const STEPS = parseInt(process.env.SOTTO_STEPS || '0', 10);
const OUT = 'H:\\sotto\\_main\\_skin-owner';

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

const FACTS = '(() => {'
  + ' const root = document.getElementById("root") || document.body;'
  + ' const host = root.firstElementChild;'
  + ' const vars = host ? (host.getAttribute("style") || "") : "";'
  + ' const leaves = [];'
  + ' for (const el of root.querySelectorAll("*")) {'
  + '   if (el.children.length) continue;'
  + '   const t = (el.textContent || "").trim();'
  + '   if (t.length < 3) continue;'
  + '   const cs = getComputedStyle(el); const sz = parseFloat(cs.fontSize) || 0;'
  + '   if (sz < 15) continue;'
  + '   const r = el.getBoundingClientRect();'
  + '   leaves.push({ t: t.slice(0, 60), sz: Math.round(sz * 10) / 10,'
  + '     r: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] });'
  + ' }'
  + ' leaves.sort((a, b) => b.sz - a.sz);'
  + ' const panels = [];'
  + ' for (const el of root.querySelectorAll("*")) {'
  + '   const cs = getComputedStyle(el);'
  + '   if (cs.position !== "absolute" && cs.position !== "fixed") continue;'
  + '   const r = el.getBoundingClientRect();'
  + '   if (r.width < 80 || r.height < 80) continue;'
  + '   panels.push({ cls: String(el.className || "").slice(0, 90), pos: cs.position,'
  + '     r: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] });'
  + ' }'
  + ' return { vars: vars, big: leaves.slice(0, 12), panels: panels.slice(0, 10),'
  + '   viewport: [innerWidth, innerHeight], body: [document.body.scrollWidth, document.body.scrollHeight] };'
  + ' })()';

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    show: false, width: W, height: H, useContentSize: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  const wc = win.webContents;
  await win.loadURL(PAGE);
  await sleep(2600);

  const walk = [];
  const shot = async (n) => {
    const img = await wc.capturePage();
    fs.writeFileSync(path.join(OUT, TAG + '-' + n + '.png'), img.toPNG());
    const facts = await wc.executeJavaScript(FACTS, true);
    walk.push({ step: n, facts: facts });
  };
  await shot('00');
  for (let i = 1; i <= STEPS; i += 1) {
    wc.sendInputEvent({ type: 'keyDown', keyCode: 'Right' });
    wc.sendInputEvent({ type: 'keyUp', keyCode: 'Right' });
    await sleep(900);
    await shot(String(i).padStart(2, '0'));
  }
  fs.writeFileSync(path.join(OUT, TAG + '-walk.json'), JSON.stringify(walk, null, 1));
  app.exit(0);
}).catch((err) => {
  fs.writeFileSync(path.join(OUT, 'error.txt'), String((err && err.stack) || err));
  app.exit(1);
});
