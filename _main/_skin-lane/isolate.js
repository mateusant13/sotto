/* LAYER ISOLATION: which paint layer diverges on cellar.
 * Vendor vs frozen, same 380x900 box: full, stage-only, wall-only, caption-only.
 * Plus a computed-paint dump of every stage child on both sides. */
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const HERE = __dirname;
const SKIN = 'H:\\sotto\\app\\panel\\skins\\cinematic-2';
const SHOTS = path.join(HERE, 'shots');
const VENDOR = 'file:///H:/sotto/_main/_design-lane/zips/cinematic-2/dist/index.html';
const HOST = 'file:///' + path.join(HERE, 'oracle-host.html').replace(/\\/g, '/');
const W = 380, H = 900;
const ID = 'cellar';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function sha(b) { return crypto.createHash('sha256').update(b).digest('hex').slice(0, 16); }
function filesURL(rel) {
  return /^[a-z]+:|^\/\//i.test(rel) ? rel
    : 'file:///H:/sotto/app/panel/skins/cinematic-2/' + rel.replace(/^\.\//, '');
}
function rebaseFragments(frags) {
  const out = {};
  ['stage', 'chrome', 'caption', 'panel'].forEach(part => {
    let html = frags[part] || '';
    html = html.replace(/url\(\s*(['"]?)(img\/[^'")]+)\1\s*\)/g,
      (m, q, rel) => 'url(' + (q || '') + filesURL(rel) + (q || '') + ')');
    out[part] = html;
  });
  return out;
}

const probeSrc = fs.readFileSync(path.join(HERE, 'probe.js'), 'utf8');
const driverSrc = fs.readFileSync(path.join(HERE, 'freeze-driver.js'), 'utf8');
const index = JSON.parse(fs.readFileSync(path.join(SKIN, 'index.json'), 'utf8'));
const rows = JSON.parse(fs.readFileSync(path.join(HERE, 'walls.json'), 'utf8'));
const wallMap = {};
rows.forEach(r => { wallMap[r.photo] = r.wall_local; });
const fontsCss = fs.readFileSync('H:\\sotto\\app\\panel\\themes\\fonts.css', 'utf8')
  .replace(/url\(\.\.\/fonts\//g, 'url(file:///H:/sotto/app/panel/fonts/');
const css = fs.readFileSync(path.join(SKIN, 'app.css'), 'utf8');

// Hide everything except the stage; returns what was hidden.
const STAGE_ONLY_JS = `(function(){
  var P=window.__sottoProbe, out=[];
  var root=P.detect(document.getElementById("root").firstElementChild).__root||document.getElementById("root").firstElementChild;
  var R=P.detect(root);
  function hide(el,label){ if(el&&el.style){ el.style.display='none'; out.push(label); } }
  hide(R.caption,'caption'); hide(R.panel,'panel');
  (R.chromeNodes||[]).forEach(function(c,i){ hide(c,'chrome'+i); });
  Array.prototype.forEach.call(root.children,function(c){ if(c.tagName==='BUTTON') hide(c,'button'); });
  return out; })()`;

// Inside the stage, hide every paint layer except the wallpaper div itself.
const WALL_ONLY_JS = `(function(){
  var P=window.__sottoProbe;
  var root=document.getElementById("root").firstElementChild;
  var R=P.detect(root); var out=[];
  function hide(el,label){ if(el&&el.style){ el.style.display='none'; out.push(label); } }
  hide(R.overlay,'overlay'); hide(R.vignette,'vignette'); hide(R.grain,'grain');
  hide(R.slate,'slate');
  if(R.particles&&R.particles.parentElement!==R.stage) hide(R.particles.parentElement,'particles-wrap');
  else hide(R.particles,'particles');
  // frame corners: any stage child that is not an ancestor of the wall
  var wall=R.wall;
  Array.prototype.forEach.call(R.stage.children,function(c){
    if(c!==wall && !c.contains(wall) && c!==R.overlay && c!==R.vignette && c!==R.grain && c!==R.slate){ hide(c,'stage-child:'+(c.getAttribute('class')||c.tagName).slice(0,60)); }
  });
  return {hidden:out, wallRect: wall?wall.getBoundingClientRect().toJSON():null}; })()`;

// Hide stage+panel+chrome -> caption plate over black page background.
const CAPTION_ONLY_JS = `(function(){
  var P=window.__sottoProbe; var out=[];
  var root=document.getElementById("root").firstElementChild;
  var R=P.detect(root);
  function hide(el,label){ if(el&&el.style){ el.style.display='none'; out.push(label); } }
  hide(R.stage,'stage'); hide(R.panel,'panel');
  (R.chromeNodes||[]).forEach(function(c,i){ hide(c,'chrome'+i); });
  Array.prototype.forEach.call(root.children,function(c){ if(c.tagName==='BUTTON') hide(c,'button'); });
  return out; })()`;

// Computed paint dump of the stage subtree.
const PAINT_DUMP_JS = `(function(){
  var P=window.__sottoProbe;
  var root=document.getElementById("root").firstElementChild;
  var R=P.detect(root); var rows=[];
  function paint(el,label){
    if(!el) return;
    var cs=getComputedStyle(el); var r=el.getBoundingClientRect();
    var bg=cs.backgroundImage||'';
    rows.push({label:label, tag:el.tagName.toLowerCase(),
      cls:(el.getAttribute('class')||'').slice(0,80),
      inline:(el.getAttribute('style')||'').slice(0,200),
      rect:[r.x,r.y,r.width,r.height].map(function(v){return Math.round(v*10)/10;}).join(','),
      bgColor:cs.backgroundColor, bgImage:(bg.length>220?bg.slice(0,220)+'...len'+bg.length:bg),
      bgSize:cs.backgroundSize, bgPos:cs.backgroundPosition,
      opacity:cs.opacity, filter:cs.filter, mix:cs.mixBlendMode,
      backdrop:cs.backdropFilter, transform:cs.transform});
  }
  paint(R.stage,'stage'); paint(R.wall,'wall'); paint(R.overlay,'overlay');
  paint(R.vignette,'vignette'); paint(R.grain,'grain'); paint(R.slate,'slate');
  paint(R.particles,'particles');
  if(R.particles&&R.particles.parentElement!==R.stage) paint(R.particles.parentElement,'particles-wrap');
  if(R.caption) paint(R.caption,'caption-col');
  var live=R.live; if(live) paint(live,'live');
  var box=R.captionBox; if(box&&box!==live) paint(box,'captionBox');
  return rows; })()`;

// Same three, but inside the shadow host (#box -> .skin-root).
const SHADOW = {
  stageOnly: `(function(){
    var P=window.__sottoProbe, out=[];
    var root=document.querySelector("#box").shadowRoot.querySelector(".skin-root");
    var R=P.detect(root);
    function hide(el,label){ if(el&&el.style){ el.style.display='none'; out.push(label); } }
    hide(R.caption,'caption'); hide(R.panel,'panel');
    (R.chromeNodes||[]).forEach(function(c,i){ hide(c,'chrome'+i); });
    Array.prototype.forEach.call(root.children,function(c){ if(c.tagName==='BUTTON') hide(c,'button'); });
    return out; })()`,
  paintDump: `(function(){
    var P=window.__sottoProbe; var rows=[];
    var root=document.querySelector("#box").shadowRoot.querySelector(".skin-root");
    var R=P.detect(root);
    function paint(el,label){
      if(!el) return;
      var cs=getComputedStyle(el); var r=el.getBoundingClientRect();
      var bg=cs.backgroundImage||'';
      rows.push({label:label, tag:el.tagName.toLowerCase(),
        cls:(el.getAttribute('class')||'').slice(0,80),
        inline:(el.getAttribute('style')||'').slice(0,200),
        rect:[r.x,r.y,r.width,r.height].map(function(v){return Math.round(v*10)/10;}).join(','),
        bgColor:cs.backgroundColor, bgImage:(bg.length>220?bg.slice(0,220)+'...len'+bg.length:bg),
        bgSize:cs.backgroundSize, bgPos:cs.backgroundPosition,
        opacity:cs.opacity, filter:cs.filter, mix:cs.mixBlendMode,
        backdrop:cs.backdropFilter, transform:cs.transform});
    }
    paint(R.stage,'stage'); paint(R.wall,'wall'); paint(R.overlay,'overlay');
    paint(R.vignette,'vignette'); paint(R.grain,'grain'); paint(R.slate,'slate');
    paint(R.particles,'particles');
    if(R.particles&&R.particles.parentElement!==R.stage) paint(R.particles.parentElement,'particles-wrap');
    if(R.caption) paint(R.caption,'caption-col');
    var live=R.live; if(live) paint(live,'live');
    var box=R.captionBox; if(box&&box!==live) paint(box,'captionBox');
    return rows; })()`
};

(async () => {
  await app.whenReady();
  const rec = { id: ID };
  const win = new BrowserWindow({
    width: W, height: H, useContentSize: true, show: false, frame: false,
    backgroundColor: '#000000',
    webPreferences: { offscreen: false, backgroundThrottling: false, contextIsolation: false }
  });
  win.webContents.setZoomFactor(1);
  win.webContents.setAudioMuted(true);

  // ---- VENDOR ----
  await win.webContents.loadURL(VENDOR);
  for (let i = 0; i < 150; i++) {
    const ok = await win.webContents.executeJavaScript(
      'Boolean(document.getElementById("root") && document.getElementById("root").firstElementChild)');
    if (ok) break;
    await sleep(120);
  }
  await win.webContents.executeJavaScript(probeSrc + '\n' + driverSrc, true);
  await win.webContents.executeJavaScript(
    '(function(){var s=document.createElement("style");s.id="sotto-skin-fonts";' +
    's.textContent=' + JSON.stringify(fontsCss) + ';document.head.appendChild(s);' +
    'return document.fonts.ready.then(function(){return true;});})()', true);
  await sleep(200);
  const idx = rows.findIndex(r => r.id === ID);
  const run = await win.webContents.executeJavaScript(
    '__freeze_run(' + JSON.stringify({ index: idx, id: ID, n: rows[idx].n, wallMap, composeAfterSlice: true }) + ')', true);
  rec.vendorPaint = await win.webContents.executeJavaScript(PAINT_DUMP_JS, true);
  rec.vendorHiddenForStage = await win.webContents.executeJavaScript(STAGE_ONLY_JS, true);
  await sleep(300);
  let png = (await win.webContents.capturePage()).toPNG();
  fs.writeFileSync(path.join(SHOTS, ID + '.iso-vendor-stage.png'), png);
  rec.vendorStagePixels = sha(png);
  rec.vendorWallInfo = await win.webContents.executeJavaScript(WALL_ONLY_JS, true);
  await sleep(300);
  png = (await win.webContents.capturePage()).toPNG();
  fs.writeFileSync(path.join(SHOTS, ID + '.iso-vendor-wall.png'), png);
  rec.vendorWallPixels = sha(png);

  // ---- FROZEN ----
  await win.webContents.loadURL(HOST);
  await win.webContents.executeJavaScript(probeSrc, true);
  const payload = {
    css, fontsCss, vars: run.vars,
    fragments: rebaseFragments({
      stage: run.fragments.stage.html, chrome: run.fragments.chrome.html,
      caption: run.fragments.caption.html, panel: run.fragments.panel.html })
  };
  await win.webContents.executeJavaScript('__mountFrozen(' + JSON.stringify(payload) + ')', true);
  if (run.post.listScrollTop) {
    await win.webContents.executeJavaScript(
      '(function(){var R=__sottoProbe.detect(' +
      'document.querySelector("#box").shadowRoot.querySelector(".skin-root"));' +
      'if(R.list)R.list.scrollTop=' + JSON.stringify(run.post.listScrollTop) + ';return true;})()', true);
  }
  await win.webContents.executeJavaScript('document.fonts.ready.then(function(){return true;})', true);
  await sleep(250);
  rec.frozenPaint = await win.webContents.executeJavaScript(SHADOW.paintDump, true);
  rec.frozenHiddenForStage = await win.webContents.executeJavaScript(SHADOW.stageOnly, true);
  await sleep(300);
  png = (await win.webContents.capturePage()).toPNG();
  fs.writeFileSync(path.join(SHOTS, ID + '.iso-frozen-stage.png'), png);
  rec.frozenStagePixels = sha(png);
  // Frozen wall-only + bare wall, mirroring the vendor WALL_ONLY_JS layer strip.
  const SHADOW_WALL_ONLY = `(function(){
    var P=window.__sottoProbe; var out=[];
    var root=document.querySelector("#box").shadowRoot.querySelector(".skin-root");
    var R=P.detect(root);
    function hide(el,label){ if(el&&el.style){ el.style.display='none'; out.push(label); } }
    hide(R.overlay,'overlay'); hide(R.vignette,'vignette'); hide(R.grain,'grain');
    hide(R.slate,'slate');
    if(R.particles&&R.particles.parentElement!==R.stage) hide(R.particles.parentElement,'particles-wrap');
    else hide(R.particles,'particles');
    var wall=R.wall;
    Array.prototype.forEach.call(R.stage.children,function(c){
      if(c!==wall && !c.contains(wall) && c!==R.overlay && c!==R.vignette && c!==R.grain && c!==R.slate){ hide(c,'stage-child:'+(c.getAttribute('class')||c.tagName).slice(0,60)); }
    });
    return {hidden:out}; })()`;
  rec.frozenWallInfo = await win.webContents.executeJavaScript(SHADOW_WALL_ONLY, true);
  await sleep(300);
  png = (await win.webContents.capturePage()).toPNG();
  fs.writeFileSync(path.join(SHOTS, ID + '.iso-frozen-wall.png'), png);
  rec.frozenWallPixels = sha(png);

  rec.stagePixelsEqual = rec.vendorStagePixels === rec.frozenStagePixels;
  fs.writeFileSync(path.join(HERE, 'isolate-report.json'), JSON.stringify(rec, null, 1));
  console.log('ISOLATE vendorStage=' + rec.vendorStagePixels + ' frozenStage=' + rec.frozenStagePixels +
    ' equal=' + rec.stagePixelsEqual);
  console.log('ISOLATE vendorWall=' + rec.vendorWallPixels + ' frozenWall=' + rec.frozenWallPixels +
    ' wallEqual=' + (rec.vendorWallPixels === rec.frozenWallPixels));
  console.log('VENDOR-PAINT ' + JSON.stringify(rec.vendorPaint));
  console.log('FROZEN-PAINT ' + JSON.stringify(rec.frozenPaint));
  process.exit(0);
})().catch(e => { console.error('ISOLATE CRASHED: ' + (e && e.message)); process.exit(2); });
