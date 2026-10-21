'use strict';

/**
 * _panel-design-fit-probe.js — WHY THE DESIGNS TRUNCATE IN THE RIGHT PANEL.
 *
 * WHAT IT MEASURES. The shipped panel is 380 px wide (`sotto_webview.py`
 * PANEL_WIDTH) and the slab's content box is 380 - 2*14 = 352 px. For EVERY
 * theme the panel ships, this walks the live document and reports the elements
 * that do not FIT that box: a box whose right edge is past the slab's content
 * edge (an overflow), and a box whose `scrollWidth` is past its `clientWidth`
 * (text that is CLIPPED -- the "trunca na merda" the owner wrote about).
 *
 * WHY A COPY. The headless Edge on this box CLAMPS the layout viewport to
 * 492 px (see `AGENTS.md`, the 2026-10-18 retraction), so the panel would be
 * laid out 492 px wide and every number would be about a window nobody has.
 * The copy forces the root to 380 px so the numbers are the owner's window.
 * The ONE thing that cannot be reproduced here is `position: fixed`
 * (`.panel__controls` is fixed, so it is pinned to the viewport, not to the
 * slab): the shell's own `--dump-dom` is the instrument for THAT, and it says
 * the cluster is 264 px inside a 380 px window.
 *
 * node _main/_panel-design-fit-probe.js            # the table
 * node _main/_panel-design-fit-probe.js --json     # machine-readable
 *
 * Exit codes: 0 the probe ran | 1 setup error.
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const PANEL_DIR = path.join(REPO, 'app', 'panel');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const TMP = process.env.TMPDIR && fs.existsSync(process.env.TMPDIR) ? process.env.TMPDIR : os.tmpdir();

const PANEL_W = 380;
const PAD = 14;

function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, e.name);
    const d = path.join(dst, e.name);
    if (e.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

/** The theme ids the panel ships, read from the panel's OWN registry. */
function themeIds() {
  const src = fs.readFileSync(path.join(PANEL_DIR, 'themes', 'themes.js'), 'utf8');
  const ids = [...src.matchAll(/^\s*name:\s*'([^']+)'/gm)].map((m) => m[1]);
  const zipc = path.join(PANEL_DIR, 'themes', 'zipc-panels.js');
  if (fs.existsSync(zipc)) {
    const z = fs.readFileSync(zipc, 'utf8');
    for (const m of z.matchAll(/^\s*name:\s*'([^']+)'/gm)) ids.push(m[1]);
    for (const m of z.matchAll(/^\s*id:\s*'([^']+)'/gm)) ids.push(m[1]);
  }
  return [...new Set(ids)];
}

const MEASURE = `
(function () {
  function run() {
    var out = [];
    var themes = window.__THEMES__;
    var root = document.documentElement;
    // The surface must be ON before anything is measured: the panel's own CSS
    // keys body[data-surface="panel"], and surface.js owns that attribute.
    document.body.setAttribute('data-surface', 'panel');
    for (var i = 0; i < themes.length; i++) {
      var t = themes[i];
      root.setAttribute('data-theme', t);
      void document.body.offsetHeight;
      var panel = document.getElementById('panel');
      if (!panel) { out.push({ theme: t, error: 'no #panel' }); continue; }
      var pr = panel.getBoundingClientRect();
      var cs = getComputedStyle(panel);
      var padL = parseFloat(cs.paddingLeft) || 0;
      var padR = parseFloat(cs.paddingRight) || 0;
      var left = pr.left + padL;
      var right = pr.right - padR;
      var over = [];
      var clipped = [];
      var all = panel.querySelectorAll('*');
      for (var j = 0; j < all.length; j++) {
        var el = all[j];
        var st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') continue;
        // A FIXED box is anchored to the VIEWPORT, not to the slab, so it cannot
        // truncate the slab: .panel__controls is fixed, and in this instrument
        // the viewport is the headless 492 px one, so counting it would report
        // a 112 px overflow that the owner's 380 px window does not have. The
        // shell's own --dump-dom probe is the instrument for the fixed cluster.
        if (st.position === 'fixed') continue;
        // ...and so is every child of one: the cluster is fixed, so its buttons
        // are laid out against the headless 492 px viewport, not against the
        // owner's 380 px window. The shell's --dump-dom is the instrument for
        // them (it says the cluster is 102..366 inside 380, `past_by: 0`).
        if (el.closest && el.closest('.panel__controls')) continue;
        var r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        var overRight = Math.round(r.right - right);
        var overLeft = Math.round(left - r.left);
        if (overRight > 1 || overLeft > 1) {
          over.push({ sel: el.id ? '#' + el.id : (el.className && typeof el.className === 'string'
            ? '.' + el.className.trim().split(/\\s+/).join('.') : el.tagName.toLowerCase()),
            right: Math.round(r.right), over: overRight, overLeft: overLeft });
        }
        if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
          clipped.push({ sel: el.id ? '#' + el.id : (el.className && typeof el.className === 'string'
            ? '.' + el.className.trim().split(/\\s+/).join('.') : el.tagName.toLowerCase()),
            scroll: el.scrollWidth, client: el.clientWidth, cut: el.scrollWidth - el.clientWidth });
        }
      }
      out.push({
        theme: t,
        content: Math.round(right - left),
        over: over.slice(0, 6),
        overCount: over.length,
        clipped: clipped.slice(0, 6),
        clippedCount: clipped.length,
      });
    }
    var pre = document.createElement('pre');
    pre.id = 'FITDUMP';
    pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }
  if (document.readyState === 'complete') setTimeout(run, 1200);
  else window.addEventListener('load', function () { setTimeout(run, 1200); });
})();
`;

function main() {
  if (!fs.existsSync(EDGE)) {
    console.error('SETUP ERROR: Edge not found at ' + EDGE);
    process.exit(2);
  }
  const work = fs.mkdtempSync(path.join(TMP, 'fit-'));
  copyDir(PANEL_DIR, work);
  const themes = themeIds();
  let html = fs.readFileSync(path.join(work, 'panel.html'), 'utf8');
  // THE OWNER'S WINDOW, not the headless clamp.
  html = html.replace('</head>', '<style>html,body{width:' + PANEL_W + 'px !important;}'
    + 'main.panel{width:' + PANEL_W + 'px !important;}</style></head>');
  // THE PANEL'S CSP IS `script-src 'self'` — an INLINE script is refused, so
  // the measurement is written as a FILE next to the copy and loaded by src.
  fs.writeFileSync(path.join(work, '_fitthemes.js'),
    'window.__THEMES__=' + JSON.stringify(themes) + ';\n', 'utf8');
  fs.writeFileSync(path.join(work, '_fitmeasure.js'), MEASURE, 'utf8');
  html = html.replace('</body>', '<script src="_fitthemes.js"></script>'
    + '<script src="_fitmeasure.js"></script></body>');
  fs.writeFileSync(path.join(work, 'panel.html'), html, 'utf8');

  const url = 'file:///' + path.join(work, 'panel.html').replace(/\\/g, '/') + '#panel';
  const args = ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--hide-scrollbars', '--force-device-scale-factor=1', '--virtual-time-budget=30000',
    '--user-data-dir=' + path.join(work, 'udd'), '--window-size=' + (PANEL_W + 8) + ',900',
    '--dump-dom', url];
  let stdout = '';
  try {
    stdout = execFileSync(EDGE, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, timeout: 300000 });
  } catch (err) {
    stdout = (err.stdout || '') + '\nERR:' + (err.stderr || '');
  }
  const m = stdout.match(/<pre id="FITDUMP">([\s\S]*?)<\/pre>/);
  if (!m) {
    console.error('NO DUMP. stdout head:\n' + stdout.slice(0, 1200));
    process.exit(2);
  }
  const rows = JSON.parse(m[1]
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&'));

  if (process.argv.includes('--json')) {
    console.log(JSON.stringify(rows, null, 1));
    return;
  }
  console.log('PANEL ' + PANEL_W + 'px wide, content box ' + (PANEL_W - 2 * PAD) + 'px. '
    + rows.length + ' theme(s).');
  console.log('theme'.padEnd(22) + 'content  over  clipped  worst');
  let worst = 0;
  for (const r of rows) {
    const w = r.over && r.over.length ? r.over[0] : null;
    const c = r.clipped && r.clipped.length ? r.clipped[0] : null;
    const worstBy = w ? (w.over > w.overLeft ? 'over ' + w.over + 'px @ ' + w.sel : 'left ' + w.overLeft + 'px @ ' + w.sel)
      : (c ? 'cut ' + c.cut + 'px @ ' + c.sel : '-');
    if (w) worst = Math.max(worst, w.over, w.overLeft);
    console.log(String(r.theme).padEnd(22) + String(r.content).padEnd(8)
      + String(r.overCount).padEnd(6) + String(r.clippedCount).padEnd(9) + worstBy);
  }
  console.log('\nworst horizontal overflow measured: ' + worst + 'px');
  console.log('workdir=' + work);
}

main();
