/* ONE-OFF: dump element identity for the cellar design, vendor side post-compose,
 * to compare against the STORED frozen fragments on disk. */
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');
const HERE = __dirname;
const VENDOR = 'file:///H:/sotto/_main/_design-lane/zips/cinematic-2/dist/index.html';
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
(async () => {
  await app.whenReady();
  const win = new BrowserWindow({
    width: 380, height: 900, useContentSize: true, show: false, frame: false,
    backgroundColor: '#000000',
    webPreferences: { offscreen: false, backgroundThrottling: false, contextIsolation: false }
  });
  win.webContents.setZoomFactor(1);
  win.webContents.setAudioMuted(true);
  await win.webContents.loadURL(VENDOR);
  for (let i = 0; i < 150; i++) {
    const ok = await win.webContents.executeJavaScript(
      'Boolean(document.getElementById("root") && document.getElementById("root").firstElementChild)');
    if (ok) break;
    await sleep(120);
  }
  const probeSrc = fs.readFileSync(path.join(HERE, 'probe.js'), 'utf8');
  const driverSrc = fs.readFileSync(path.join(HERE, 'freeze-driver.js'), 'utf8');
  const rows = JSON.parse(fs.readFileSync(path.join(HERE, 'walls.json'), 'utf8'));
  const wallMap = {};
  rows.forEach(r => { wallMap[r.photo] = r.wall_local; });
  await win.webContents.executeJavaScript(probeSrc + '\n' + driverSrc, true);
  await sleep(200);
  const idx = rows.findIndex(r => r.id === 'cellar');
  await win.webContents.executeJavaScript(
    '__freeze_run(' + JSON.stringify({ index: idx, id: 'cellar', n: rows[idx].n, wallMap }) + ')', true);
  await win.webContents.executeJavaScript('__freeze_compose_live()', true);
  await sleep(150);
  const dump = await win.webContents.executeJavaScript(`(function(){
    const P = window.__sottoProbe;
    const root = document.getElementById('root').firstElementChild;
    const R = P.detect(root);
    const o = {};
    o.chromeCount = (R.chromeNodes||[]).length;
    o.chromeHTML = (R.chromeNodes||[]).map(e => e.outerHTML.slice(0, 400));
    o.wordText = R.word ? R.word.textContent : null;
    o.liveText = R.live ? R.live.textContent.slice(0, 120) : null;
    o.rowText = R.row ? R.row.textContent.slice(0, 120) : null;
    o.timeText = R.time ? R.time.textContent : null;
    o.listScroll = R.list ? {top: R.list.scrollTop, h: R.list.scrollHeight, ch: R.list.clientHeight} : null;
    o.rowRect = R.row ? R.row.getBoundingClientRect().toJSON() : null;
    o.listRect = R.list ? R.list.getBoundingClientRect().toJSON() : null;
    o.chrome1Rect = R.chromeNodes && R.chromeNodes[1] ? R.chromeNodes[1].getBoundingClientRect().toJSON() : null;
    return o;
  })()`, true);
  console.log(JSON.stringify(dump, null, 1));
  const wantNames = fs.readFileSync(path.join(HERE, 'wanted-initials.txt'), 'utf8')
    .split('\n').filter(Boolean).map(l => l.split('|')[0].trim());
  const meas = await win.webContents.executeJavaScript(`(function(){
    var names = ${JSON.stringify(wantNames)};
    var cs = getComputedStyle(document.getElementById('root'));
    var o = {};
    names.forEach(function(n){ o[n] = JSON.stringify(cs.getPropertyValue(n)); });
    var kids = document.querySelector('#root').firstElementChild.children;
    // chrome1 is the node carrying .-translate-x-1/2 (left:50%)
    for (var i = 0; i < kids.length; i++) {
      if ((kids[i].getAttribute('class') || '').indexOf('-translate-x-1/2') >= 0) {
        o['.chrome1-computed-translate'] = getComputedStyle(kids[i]).translate;
        o['.chrome1-computed-left'] = getComputedStyle(kids[i]).left;
      }
    }
    return o;
  })()`, true);
  console.log(JSON.stringify(meas, null, 1));
  app.exit(0);
})().catch(e => { console.error('DUMP CRASHED: ' + (e && e.stack || e)); app.exit(2); });
