/* THE FREEZE, Electron side.
 *
 *   H:/sotto/app/node_modules/electron/dist/electron.exe _main/_skin-lane/freeze.js --all
 *   ... --only rainline
 *
 * One PAGE LOAD per design, on purpose: __freeze_compose_live() stops the vendor's
 * simulation clock so the reference screenshot is a still frame, and a stopped page cannot
 * produce a live caption for the next design. A fresh load also guarantees every design is
 * captured from the same starting state instead of from whatever the previous one left.
 */
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const SKIN = 'H:\\sotto\\app\\panel\\skins\\cinematic-2';
const SHOTS = path.join(HERE, 'shots');
const VENDOR = 'file:///H:/sotto/_main/_design-lane/zips/cinematic-2/dist/index.html';
const W = 380, H = 900;

const argv = process.argv.slice(2);
// `--only=x,y` (one token, how the PowerShell launcher delivers it) or `--only x,y`.
function optVal(name) {
  const eq = argv.filter(a => a.indexOf(name + '=') === 0)[0];
  if (eq) return eq.slice(name.length + 1);
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : null;
}
const ONLY = (v => v ? v.split(',') : null)(optVal('--only'));

const rows = JSON.parse(fs.readFileSync(path.join(HERE, 'walls.json'), 'utf8'));
const wallMap = {};
rows.forEach(r => { wallMap[r.photo] = r.wall_local; });

const probeSrc = fs.readFileSync(path.join(HERE, 'probe.js'), 'utf8');
const driverSrc = fs.readFileSync(path.join(HERE, 'freeze-driver.js'), 'utf8');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function waitForMount(wc, timeoutMs) {
  const t0 = Date.now();
  for (;;) {
    const ok = await wc.executeJavaScript(
      'Boolean(document.getElementById("root") && document.getElementById("root").firstElementChild)');
    if (ok) return Date.now() - t0;
    if (Date.now() - t0 > timeoutMs) throw new Error('the app never mounted');
    await sleep(120);
  }
}

function writeFile(p, text) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, text, 'utf8');
}

(async () => {
  await app.whenReady();
  fs.mkdirSync(SHOTS, { recursive: true });

  const win = new BrowserWindow({
    width: W, height: H, useContentSize: true, show: false, frame: false,
    backgroundColor: '#000000',
    webPreferences: { offscreen: false, backgroundThrottling: false, contextIsolation: false }
  });
  win.webContents.setZoomFactor(1);
  win.webContents.setAudioMuted(true);

  const wanted = ONLY ? rows.filter(r => ONLY.indexOf(r.id) >= 0) : rows;
  if (!wanted.length) throw new Error('--only matched no design');

  const out = { designs: {}, failures: [], notes: [] };

  for (const row of wanted) {
    const t0 = Date.now();
    await win.webContents.loadURL(VENDOR);
    await waitForMount(win.webContents, 20000);
    // Both scripts are injected after every load: a reload throws them away.
    await win.webContents.executeJavaScript(probeSrc + '\n' + driverSrc, true);
    await sleep(250);

    let res;
    try {
      res = await win.webContents.executeJavaScript(
        '__freeze_run(' + JSON.stringify({ index: rows.indexOf(row), id: row.id, n: row.n, wallMap }) + ')', true);
    } catch (e) {
      out.failures.push({ id: row.id, stage: 'capture', error: String(e && e.message || e) });
      console.log('FAIL ' + row.id + '  ' + String(e && e.message || e));
      continue;
    }

    // raw vendor frame first — this is the collapsed 380 px reference the owner measured
    const rawPng = await win.webContents.capturePage();
    fs.writeFileSync(path.join(SHOTS, row.id + '.vendor.png'), rawPng.toPNG());

    // then the fragments land on disk
    const files = {};
    ['stage', 'chrome', 'caption', 'panel'].forEach(part => {
      const name = row.id + '.' + part + '.html';
      writeFile(path.join(SKIN, name), res.fragments[part].html);
      files[part] = name;
    });

    // then the live page is put into the SAME composition and frozen for the reference
    const composed = await win.webContents.executeJavaScript('__freeze_compose_live()', true);
    await sleep(120);
    const compPng = await win.webContents.capturePage();
    fs.writeFileSync(path.join(SHOTS, row.id + '.composed.png'), compPng.toPNG());

    res.files = files;
    res.composed = composed;
    res.ms = Date.now() - t0;
    out.designs[row.id] = res;

    const must = ['live', 'historyRow'];
    const bad = must.filter(k => res.bindings[k] === null);
    const resolved = Object.keys(res.bindings).filter(k => res.bindings[k] !== null).length;
    // Plain concatenation: Node's console.log does NOT honour a printf width (`%-14s`
    // was printed literally and shifted every following argument by one, so the run
    // reported `live=18ms` where it meant `arrows=1`).
    console.log((bad.length ? 'FAIL ' : 'OK   ') + row.id.padEnd(14) +
      ' n=' + row.n + ' arrows=' + res.arrows + ' live=' + res.liveAfterMs + 'ms' +
      ' bindings=' + resolved + '/9' +
      (bad.length ? '  MUST-RESOLVE MISSING: ' + bad.join(',') : ''));
    if (bad.length) out.failures.push({ id: row.id, stage: 'bindings', missing: bad });
  }

  // ---------- index.json ----------
  const designs = Object.keys(out.designs);
  const bindings = {}, bindingProof = {}, vars = {}, fragments = {}, branches = {}, stats = {};
  designs.forEach(id => {
    const d = out.designs[id];
    const row = rows.find(r => r.id === id) || {};
    bindings[id] = d.bindings;
    bindingProof[id] = d.bindingProof;
    vars[id] = d.vars;
    fragments[id] = d.files;
    // The four branches that decide this design's element tree (analysis §4: the TREE
    // changes, not just the colours), so the integrator can tell which skeleton it got.
    branches[id] = row.branch || null;
    stats[id] = {
      arrows: d.arrows, liveAfterMs: d.liveAfterMs, chromeShownAs: d.chromeShownAs,
      chromeNodes: d.fragments.chrome.nodes, chromeWrapped: d.fragments.chrome.wrapped,
      droppedTransitionLayers: d.stageStats.droppedTransitionLayers,
      captionHadRight: d.captionStats.hadRight,
      rewrites: d.rewrites,
      liveCensus: d.liveCensus
    };
  });

  const index = {
    zip: 'cinematic-2',
    css: 'app.css',
    viewport: [W, H],
    frozen: designs,
    complete: !ONLY,
    designs,
    fragments,
    vars,
    bindings,
    branches,
    bindingFragments: {
      live: 'caption', wordTemplate: 'caption', caret: 'caption', speaker: 'caption',
      statusWord: 'caption', meter: 'caption',
      historyList: 'panel', historyRow: 'panel', historyTime: 'panel'
    },
    bindingProof,
    stats,
    mustResolve: ['live', 'historyRow'],
    failures: out.failures
  };
  writeFile(path.join(SKIN, 'index.json'), JSON.stringify(index, null, 1));

  console.log('');
  console.log('designs frozen: %d   failures: %d', designs.length, out.failures.length);
  out.failures.forEach(f => console.log('   FAILED %s at %s: %s', f.id, f.stage,
    f.error || ('missing ' + (f.missing || []).join(','))));
  console.log('index.json -> %s (%d bytes)', path.join(SKIN, 'index.json'),
    fs.statSync(path.join(SKIN, 'index.json')).size);
  app.exit(out.failures.length ? 1 : 0);
})().catch(e => {
  console.error('FREEZE CRASHED: ' + (e && e.stack || e));
  app.exit(2);
});
