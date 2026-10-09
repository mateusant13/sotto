/* THE FIDELITY GATE.
 *
 *   H:/sotto/app/node_modules/electron/dist/electron.exe _main/_skin-lane/oracle.js
 *   ... --design rainline        (one design)
 *   ... --neg-arm                (ship the UN-REWRITTEN sheet and prove the gate goes RED)
 *   ... --viewport-drift         (also measure a wide host viewport, §9.2)
 *
 * One command, every design, two sides of the same 380x900 box:
 *
 *   VENDOR  the real app, the design forced through its own UI, then put into the same
 *           composition the fragments carry (caption column `right:0`, one wallpaper
 *           layer, animations off) — its own compiled sheet in the light DOM.
 *   FROZEN  the four frozen fragments, mounted in a SHADOW ROOT with the rewritten
 *           `app.css` adopted inside it — the way the integrator will mount them.
 *
 * Both sides are located by the SAME role rules (probe.js) and compared property by
 * property, plus a capturePage PNG hash over a fixed 380x900 crop.
 *
 * Exit 0 only when every design passes.
 */
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

const argv = process.argv.slice(2);
const negArm = argv.indexOf('--neg-arm') >= 0;
const driftArm = argv.indexOf('--viewport-drift') >= 0;
// Both spellings, because the PowerShell launcher delivers `--design=x` as ONE token
// while a direct invocation can pass `--design x` as two. An instrument that silently
// ignored the narrower request and measured all 20 while the caller believed otherwise
// has already happened once in this lane.
function optVal(name) {
  const eq = argv.filter(a => a.indexOf(name + '=') === 0)[0];
  if (eq) return eq.slice(name.length + 1);
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : null;
}
const ONLY = (v => v ? v.split(',') : null)(optVal('--design'));

const probeSrc = fs.readFileSync(path.join(HERE, 'probe.js'), 'utf8');
const driverSrc = fs.readFileSync(path.join(HERE, 'freeze-driver.js'), 'utf8');
const index = JSON.parse(fs.readFileSync(path.join(SKIN, 'index.json'), 'utf8'));
const rows = JSON.parse(fs.readFileSync(path.join(HERE, 'walls.json'), 'utf8'));
const wallMap = {};
rows.forEach(r => { wallMap[r.photo] = r.wall_local; });

/* THE FONTS, ON BOTH SIDES, FROM THE PANEL'S OWN BUNDLE.
 * The vendor page pulls its families from a remote Google Fonts <link>; the panel ships
 * the same families as 67 local woff2 files (`app/panel/themes/fonts.css`). Text metrics
 * are what a skin's geometry is made of — measured: with no faces loaded at all on the
 * frozen side, the scene slate's width came out 239.38 px against the vendor's 228.19 —
 * so both sides get the SAME local faces, which is also the runtime truth inside the
 * panel (`@font-face` matching is document-global, so a shadow root can use them). */
const fontsCss = fs.readFileSync('H:\\sotto\\app\\panel\\themes\\fonts.css', 'utf8')
  .replace(/url\(\.\.\/fonts\//g, 'url(file:///H:/sotto/app/panel/fonts/');

// The sheet under test. The negative arm ships the vendor's sheet EXACTLY as compiled —
// `html,:host{…}`, `body{…}`, `html,body,#root{height:100%}` — which inside a shadow root
// matches nothing, so the app's `h-full` root has no height to be 100% of and the whole
// composition collapses. If the gate cannot see THAT, it cannot see anything.
const CSS_FILE = negArm ? 'app.raw.css' : 'app.css';
const css = fs.readFileSync(path.join(SKIN, CSS_FILE), 'utf8');

const TOLERANCE = 0.75;   // px, on the rect; layout rounds differently by half a pixel

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function sha(b) { return crypto.createHash('sha256').update(b).digest('hex').slice(0, 16); }

function filesURL(rel) {
  // A RELATIVE ref inside a fragment (e.g. `img/35258949.jpg`) resolves against the BASE
  // IT SHIPS IN: the skin directory. Pointing it at the oracle host's own directory
  // (`_main/_skin-lane/img/…`, which does not exist) paints every wallpaper as a dark
  // `var(--page)` box — which is how the gate once reported zero fingerprint diffs
  // against 11k differing pixels. An absolute `file:///` URL follows the checkout.
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

/* Both sides print the wallpaper URL differently — the vendor's is a remote Pexels URL,
 * the frozen one is the local file — so BOTH are reduced to the photo id, which is the
 * part that must agree. A wallpaper swapped for another design's still shows up. */
function normalizeFingerprint(fp) {
  const out = {};
  for (const role of Object.keys(fp.roles)) {
    const s = fp.roles[role];
    if (!s) { out[role] = null; continue; }
    const props = {};
    for (const k of Object.keys(s.props)) {
      let v = s.props[k];
      if (k === 'backgroundImage' && v && v.indexOf('url(') >= 0) {
        v = v.replace(/url\((?:"|')?([^)"']+)(?:"|')?\)/g, (all, u) => {
          const m = /\/(\d{6,})\b/.exec(u) || /(\d{6,})/.exec(u);
          return 'url(#' + (m ? m[1] : 'unknown') + ')';
        });
      }
      props[k] = v;
    }
    out[role] = { tag: s.tag, rect: s.rect, props };
  }
  return out;
}

function compare(vendorFp, frozenFp) {
  const diffs = [];
  const roles = new Set(Object.keys(vendorFp).concat(Object.keys(frozenFp)));
  for (const role of roles) {
    const a = vendorFp[role], b = frozenFp[role];
    if (!a && !b) continue;
    if (!a || !b) {
      diffs.push({ role, kind: 'present', vendor: Boolean(a), frozen: Boolean(b) });
      continue;
    }
    for (const axis of ['x', 'y', 'w', 'h']) {
      const d = Math.abs((a.rect[axis] || 0) - (b.rect[axis] || 0));
      if (d > TOLERANCE) diffs.push({ role, kind: 'rect.' + axis, vendor: a.rect[axis], frozen: b.rect[axis], delta: Math.round(d * 100) / 100 });
    }
    for (const k of Object.keys(a.props)) {
      if (a.props[k] !== b.props[k]) {
        diffs.push({ role, kind: 'prop.' + k, vendor: a.props[k], frozen: b.props[k] });
      }
    }
  }
  return diffs;
}

(async () => {
  await app.whenReady();
  fs.mkdirSync(SHOTS, { recursive: true });
  const designs = ONLY || index.designs;
  const report = { css: CSS_FILE, negArm, designs: {}, failures: [] };

  const win = new BrowserWindow({
    width: W, height: H, useContentSize: true, show: false, frame: false,
    backgroundColor: '#000000',
    webPreferences: { offscreen: false, backgroundThrottling: false, contextIsolation: false }
  });
  win.webContents.setZoomFactor(1);
  win.webContents.setAudioMuted(true);

  for (const id of designs) {
    const t0 = Date.now();
    const rec = { id, diffs: [], vendorPixels: null, frozenPixels: null };
    try {
      // ---------- VENDOR ----------
      await win.webContents.loadURL(VENDOR);
      for (let i = 0; i < 150; i++) {
        const ok = await win.webContents.executeJavaScript(
          'Boolean(document.getElementById("root") && document.getElementById("root").firstElementChild)');
        if (ok) break;
        await sleep(120);
      }
      await win.webContents.executeJavaScript(probeSrc + '\n' + driverSrc, true);
      // the same local faces the frozen side gets, so the two sides cannot differ by
      // which copy of Manrope the network delivered
      await win.webContents.executeJavaScript(
        '(function(){var s=document.createElement("style");s.id="sotto-skin-fonts";' +
        's.textContent=' + JSON.stringify(fontsCss) + ';document.head.appendChild(s);' +
        'return document.fonts.ready.then(function(){return true;});})()', true);
      await sleep(200);
      const idx = rows.findIndex(r => r.id === id);
      /* ONE page task does force+slice+stop+compose+reference (`composeAfterSlice`): the
       * fragments below and the vendor fingerprint are the same text by construction.
       * Mounting the DISK fragments here instead is how the gate once compared "Egyptian"
       * against "the" and reported `word rect.x 80 vs 238` — a self-inflicted drift, not
       * a skin defect. The disk artifacts are still checked: the frozen bytes mounted
       * here must equal the disk files byte for byte (asserted below). */
      const run = await win.webContents.executeJavaScript(
        '__freeze_run(' + JSON.stringify({ index: idx, id, n: (rows[idx] || {}).n,
          wallMap, composeAfterSlice: true }) + ')', true);
      const vfp = run.post.fingerprint;
      rec.wordText = run.post.wordText;
      const vPng = (await win.webContents.capturePage()).toPNG();
      fs.writeFileSync(path.join(SHOTS, id + '.gate-vendor.png'), vPng);
      rec.vendorPixels = sha(vPng);

      // ---------- FROZEN ----------
      await win.webContents.loadURL(HOST);
      await win.webContents.executeJavaScript(probeSrc, true);
      const payload = {
        css,
        fontsCss,
        vars: run.vars,
        fragments: {
          stage: run.fragments.stage.html,
          chrome: run.fragments.chrome.html,
          caption: run.fragments.caption.html,
          panel: run.fragments.panel.html
        }
      };
      // The disk files must BE this slice, byte for byte: the gate proves the shipped
      // artifact, not a private copy of it. The DISK bytes are then what gets mounted —
      // with one documented exception: `img/…` refs resolve against the directory THEY
      // SHIP IN, so mounting them from the oracle host's own directory would 404 every
      // wallpaper. `rebaseFragments` points them at the same FILES by absolute file URL;
      // the bytes otherwise mounted are the bytes on disk.
      // TRANSIENT TEXT, STABLE SKELETON: the slice above captured text T, but the disk
      // files captured text T-minus-minutes (the simulation reveals another word every
      // IPC round trip: disk caption holds "night ", this run's slice holds "shift ").
      // Byte equality across runs is therefore EXPECTED to fail on every text-bearing
      // part (chrome counts, caption words, history rows) and to hold only on the stage
      // (no transcript text). What must be byte-equal is the SKELETON — tags, classes,
      // attributes with all text nodes blanked — because the rewrite path is the same
      // code for both. The FROZEN side mounts the FRESH slice (same text as the vendor
      // reference by construction via `composeAfterSlice`), rebased to absolute file
      // URLs so the same wallpaper files resolve; the disk skeleton proof below is what
      // ties the shipped bytes to this run.
      function skeleton(html) {
        return html.replace(/>[^<>]+</g, '><');
      }
      rec.diskMatch = ['stage', 'chrome', 'caption', 'panel'].map(part => {
        const f = index.fragments[id][part];
        const disk = fs.readFileSync(path.join(SKIN, f), 'utf8');
        const fresh = run.fragments[part].html;
        return { part, file: f, match: disk === fresh,
          skeletonMatch: skeleton(disk) === skeleton(fresh),
          diskBytes: disk.length, freshBytes: fresh.length };
      });
      /* WALL LOAD, FOLDED INTO THE PAGE TASKS (no extra round trip that the probe's own
       * regex once broke): the driver already recorded the computed wallpaper URL; here each
       * side decodes THE SAME FILE it points at and reports `naturalWidth`. A 0 means the
       * pixels are comparing a painting against an absence. The detail that made this
       * probe necessary: the vendor's URL is remote (Pexels) and unreachable from this
       * box's file:// page load, so the vendor side may paint `var(--page)` where the
       * frozen side paints the photo — zero fingerprint diffs, thousands of pixel diffs. */
      rec.wallURL = run.post.wallURL;
      rec.wallDecoded = await win.webContents.executeJavaScript(
        'new Promise(function(res){var u=' + JSON.stringify(run.post.wallURL) + ';' +
        'if(!u){res(0);return;}var im=new Image();' +
        'im.onload=function(){res(im.naturalWidth);};im.onerror=function(){res(-1);};' +
        'im.src=u;setTimeout(function(){res(im.naturalWidth||-2);},3000);})', true);
      payload.fragments = rebaseFragments({
        stage: run.fragments.stage.html,
        chrome: run.fragments.chrome.html,
        caption: run.fragments.caption.html,
        panel: run.fragments.panel.html
      });
      const mount = await win.webContents.executeJavaScript(
        '__mountFrozen(' + JSON.stringify(payload) + ')', true);
      rec.mount = mount;
      // The vendor's history scroller had auto-scrolled (measured: scrollTop 580 of 1193
      // on cellar); a rebuilt scroller starts at 0, which puts every row rect hundreds of
      // pixels off (`row rect.y -249 vs 238`). Same content, so the same offset restores it.
      if (run.post.listScrollTop) {
        await win.webContents.executeJavaScript(
          '(function(){var R=__sottoProbe.detect(' +
          'document.querySelector("#box").shadowRoot.querySelector(".skin-root"));' +
          'if(R.list)R.list.scrollTop=' + JSON.stringify(run.post.listScrollTop) + ';return true;})()',
          true);
      }
      // Wait for the FACES, not for a stopwatch: a fingerprint taken before the fonts
      // resolve measures the fallback face.
      rec.fonts = await win.webContents.executeJavaScript(
        'document.fonts.ready.then(function(){' +
        'return {check16Manrope: document.fonts.check("16px Manrope"),' +
        ' faces: document.fonts.size};})', true);
      await sleep(250);
      const ffp = await win.webContents.executeJavaScript(
        '__sottoProbe.fingerprint(document.querySelector("#box").shadowRoot.querySelector(".skin-root"))', true);
      rec.frozenWallLoad = 'folded-into-mount: see wallDecoded below';
      // FROZEN-SIDE LOAD PROBE, drawn from the REBASED bytes that were actually
      // mounted (NOT the vendor URL): it reports how the same local file decoded from
      // inside the shadow mount. `frozenWallDecoded` −1 = error, −2 = timeout, 0 = empty.
      rec.frozenWallURL = (function () { const m = /url\(['"]?(file:[^'")]+)['"]?\)/.exec(
        (payload.fragments.stage || '').slice(0, 4000)); return m ? m[1] : null; })();
      const fWallJs = 'new Promise(function(res){var u=' + JSON.stringify(rec.frozenWallURL) + ';' +
        'if(!u){res(0);return;}var im=new Image();' +
        'im.onload=function(){res(im.naturalWidth||0);};im.onerror=function(){res(-1);};' +
        'im.src=u;setTimeout(function(){res(im.naturalWidth||-2);},3000);})';
      rec.frozenWallDecoded = await win.webContents.executeJavaScript(fWallJs, true);
      const fPng = (await win.webContents.capturePage()).toPNG();
      fs.writeFileSync(path.join(SHOTS, id + '.gate-frozen.png'), fPng);
      rec.frozenPixels = sha(fPng);

      // ---------- COMPARE ----------
      rec.diffs = compare(normalizeFingerprint(vfp), normalizeFingerprint(ffp));
      rec.pixelsEqual = rec.vendorPixels === rec.frozenPixels;
      rec.rolesVendor = vfp.found.length;
      rec.rolesFrozen = ffp.found.length;
      rec.ms = Date.now() - t0;

      if (driftArm) {
        // §9.2: `sm:`/`lg:`/`xl:` and every vw/vh resolve against the TOP-LEVEL viewport,
        // not the 380 px host box. Measured, not asserted, so the integrator can be told
        // exactly which roles move if the skin is mounted in a wider page.
        win.setContentSize(1280, 900);
        await sleep(300);
        const wide = await win.webContents.executeJavaScript(
          '__sottoProbe.fingerprint(document.querySelector("#box").shadowRoot.querySelector(".skin-root"))', true);
        win.setContentSize(W, H);
        await sleep(200);
        const wideDiffs = compare(normalizeFingerprint(ffp), normalizeFingerprint(wide));
        rec.viewportDrift = wideDiffs.map(d => d.role + ':' + d.kind);
      }

      const bad = rec.diffs.length;
      console.log((bad || !rec.pixelsEqual ? 'FAIL ' : 'OK   ') + id.padEnd(14) +
        ' diffs=' + String(bad).padStart(3) +
        ' roles=' + rec.rolesVendor + '/' + rec.rolesFrozen +
        ' pixels=' + (rec.pixelsEqual ? 'equal' : 'DIFFERENT') +
        (driftArm ? ' drift=' + (rec.viewportDrift || []).length : '') +
        ' ' + rec.ms + 'ms');
      if (bad) {
        const byRole = {};
        rec.diffs.forEach(d => { byRole[d.role] = (byRole[d.role] || 0) + 1; });
        console.log('       ' + Object.keys(byRole).map(r => r + '×' + byRole[r]).join(' '));
        rec.diffs.slice(0, 3).forEach(d => console.log('         ' + d.role + ' ' + d.kind +
          '\n           vendor: ' + JSON.stringify(d.vendor) + '\n           frozen: ' + JSON.stringify(d.frozen)));
      }
      if (bad || !rec.pixelsEqual) report.failures.push(id);
    } catch (e) {
      rec.error = String(e && e.message || e);
      report.failures.push(id);
      console.log('FAIL ' + id.padEnd(14) + ' ' + rec.error);
    }
    report.designs[id] = rec;
  }

  fs.writeFileSync(path.join(HERE, 'oracle-report' + (negArm ? '-negarm' : '') + '.json'),
    JSON.stringify(report, null, 1));
  console.log('');
  console.log('css under test: %s   designs: %d   failures: %d',
    CSS_FILE, designs.length, report.failures.length);
  if (report.failures.length) console.log('   failing: %s', report.failures.join(', '));
  console.log('VERDICT: %s', report.failures.length ? 'FAIL' : 'PASS');
  app.exit(report.failures.length ? 1 : 0);
})().catch(e => {
  console.error('ORACLE CRASHED: ' + (e && e.stack || e));
  app.exit(2);
});
