#!/usr/bin/env python3
"""panel-measure.py -- THE PRODUCT'S PANEL, MEASURED AT ITS OWN 380 px.

WHAT IT IS FOR
--------------
The owner (2026-10-19): *"me explica por que DIVERSOS designs nao encaixam direito
ou truncam na merda do painel da direita"*. An answer needs numbers from the
panel AT 380 px, and the only instrument that can produce them is `cdp.mjs`:
headless Edge's own --screenshot clamps the layout viewport to 492 px on this
box (measured 2026-10-20: 380 -> 492, 520 -> 496, 1000 -> 976), so every
coordinate read from a plain screenshot describes a panel the owner does not
have.

THE FIXTURE
-----------
`shot.py` writes its own `_shot.js` into the copied document. This driver
OVERWRITES it with a fixture whose lines are the ZIP'S OWN script
(`_main/ziprefs/dirs/src/data/designs.ts:85` SCRIPT), because the question is
whether a REAL caption fits, and a three-word fixture never fails to fit.
The forming line is the longest line of that script -- 57 characters -- which
is the worst case the panel has to survive.

WHAT IT PRINTS, PER THEME
--------------------------
  * the resolved font-size of the live line and of the closed lines
  * the column the text actually gets (after the time column, the grid gap
    and the two paddings)
  * OVERFLOW (scrollWidth > clientWidth) vs WRAP (number of line boxes) --
    the two are different failures
  * the PNG of the panel at a TRUE 380x900

    python _main/_design-lane/panel-measure.py --themes theme-1,theme-2
"""
import argparse
import json
import os
import subprocess
import sys
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import shot  # noqa: E402  (the copy loop and the theme/surface rewrite)

CDP = os.path.join(HERE, 'cdp.mjs')
PANEL_DIR = os.path.join(REPO, 'app', 'panel')
PROBE = os.path.join(HERE, 'probe-panel.js')
PANEL_W, PANEL_H = 380, 900

# THE ZIP'S OWN SCRIPT (ziprefs/dirs/src/data/designs.ts:85). The forming line is
# the longest of them: 57 characters.
FIXTURE = r'''(function () {
  'use strict';
  var THEME = '__SHOT_THEME__';
  var LINES = [
    ['10:23:58', 'O som chega antes da imagem.', 0],
    ['10:24:01', 'Antes da primeira cena, ja existe um rumor de sala.', 0],
    ['10:24:04', 'Quando a frase fecha, ela ganha peso - e fica.', 0],
    ['10:24:09', 'A legenda nasce enquanto a frase ainda esta em formacao.', 1]
  ];
  function go() {
    try { if (window.SottoTheme) { window.SottoTheme.set(THEME, { persist: false }); } } catch (e) {}
    var list = document.getElementById('caption-list');
    if (!list) return;
    for (var i = 0; i < LINES.length; i++) {
      var li = document.createElement('li');
      li.className = 'caption' + (i === LINES.length - 1 ? ' caption--provisional' : '') +
                     (i === LINES.length - 2 ? ' caption--latest' : '');
      var t = document.createElement('span'); t.className = 'caption__time'; t.textContent = LINES[i][0];
      var b = document.createElement('span'); b.className = 'caption__text'; b.textContent = LINES[i][1];
      li.appendChild(t); li.appendChild(b);
      list.appendChild(li);
    }
    list.hidden = false;
    var ph = document.getElementById('placeholder'); if (ph) ph.hidden = true;
    var rail = document.getElementById('captions-body');
    if (rail) { rail.scrollTop = rail.scrollHeight; }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(go, 300); });
  } else { setTimeout(go, 300); }
})();
'''


def build(theme, surface, workdir):
    """shot.build() copies app/panel and rewrites the theme/surface; the fixture
    it writes is replaced by the zip's own script lines.

    THE DEFERRED ASSETS. `themes/cinematic.css` and `themes/panel-designs.css`
    are NOT `<link>`ed in panel.html: the SHELL injects `app/panel/lazy-assets.js`
    as BOOTSTRAP_JS and the loader pulls the sheet in when a `cine-*` or `pd-*`
    theme is selected (lazy-assets.js:73-85). A copy of the document that runs
    without the shell therefore paints the BASE skin and the measurement is of
    the wrong thing -- MEASURED 2026-10-20: without the loader, `pd-tele`'s
    live line measures 15px (the base `--caption-size`) instead of the theme's
    own 32px, and `cine-rainline` prints the stock panel, not the Rainline skin.

    So the copy gets the loader, and a `window.sotto.dispatch` stub that
    answers the loader's ask the way the shell's gate does (allow). The bytes
    then come off the disk, from the very same file the shell would serve.
    """
    html = shot.build(theme, surface, workdir)

    # the skins: skins.js (812 KB) + skins/cinematic-2/*.html + the wallpapers
    src_skins = os.path.join(PANEL_DIR, 'skins')
    if os.path.isdir(src_skins):
        dst_skins = os.path.join(workdir, 'skins')
        for base, dirs, files in os.walk(src_skins):
            rel = os.path.relpath(base, src_skins)
            target = os.path.normpath(os.path.join(dst_skins, rel))
            os.makedirs(target, exist_ok=True)
            for f in files:
                shutil.copyfile(os.path.join(base, f), os.path.join(target, f))

    # the loader + the answer it waits for.
    #
    # A FILE, NOT AN INLINE SCRIPT: panel.html carries a Content-Security-Policy
    # with no 'unsafe-inline', so an inline <script> is REFUSED by the page and
    # `window.sotto` stays undefined -- MEASURED 2026-10-20: the loader then
    # spins on `if (!canAwait && !hasSotto) { setTimeout(ask, 100) }`
    # (lazy-assets.js:185-188) and NEVER injects the sheet, so the page paints
    # the base skin. Same-origin 'self' scripts are allowed.
    with open(os.path.join(workdir, 'panel.html'), encoding='utf-8') as fh:
        doc = fh.read()
    with open(os.path.join(workdir, 'sotto-stub.js'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('/* the shell\'s answer, for the copy: the loader asks, the gate opens */\n'
                 'window.sotto = window.sotto || { dispatch: function () { return Promise.resolve(); } };\n')
    boot = ('<script src="sotto-stub.js"></script>\n'
            '<script src="lazy-assets.js"></script>\n')
    if '</head>' in doc:
        doc = doc.replace('</head>', boot + '</head>', 1)
    else:
        doc = boot + doc
    with open(os.path.join(workdir, 'panel.html'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(doc)

    with open(os.path.join(workdir, '_shot.js'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(FIXTURE.replace('__SHOT_THEME__', theme))
    return os.path.join(workdir, 'panel.html')


def measure(theme, surface, outdir, budget):
    workdir = tempfile.mkdtemp(prefix='panel-measure-', dir=outdir)
    try:
        html = build(theme, surface, workdir)
        png = os.path.join(outdir, 'current-%s.png' % theme)
        jf = os.path.join(workdir, 'result.json')
        url = 'file:///' + html.replace(os.sep, '/')
        cmd = ['node', CDP, '--url', url, '--w', str(PANEL_W), '--h', str(PANEL_H),
               '--eval', PROBE, '--shot', png, '--json', jf, '--wait', str(budget)]
        proc = subprocess.run(cmd, capture_output=True, timeout=300)
        data = {}
        if os.path.isfile(jf):
            with open(jf, encoding='utf-8') as fh:
                data = json.load(fh)
        # cdp.mjs writes {"jobs": [ {...,"result": ...} ]}
        if isinstance(data, dict) and 'jobs' in data:
            jobs = data.get('jobs') or []
            data = jobs[0] if jobs else {}
        return data, png, proc.returncode
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--themes', required=True)
    ap.add_argument('--surface', default='panel', choices=('panel', 'strip'))
    ap.add_argument('--outdir', default='I:/cc-tmp/panel-measure')
    ap.add_argument('--budget', type=int, default=1200)
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    themes = [t.strip() for t in args.themes.split(',') if t.strip()]
    results = {}
    for theme in themes:
        data, png, rc = measure(theme, args.surface, args.outdir, args.budget)
        r = data.get('result') or {}
        rows = r.get('captions') or []
        live = rows[-1] if rows else {}
        closed = rows[0] if rows else {}
        results[theme] = {
            'viewport': r.get('viewport'),
            'panel': r.get('panel'),
            'live_font': live.get('fontSize'),
            'live_text_w': live.get('clientW'),
            'live_overflow_x': live.get('overflowX'),
            'live_line_boxes': live.get('lineBoxes'),
            'live_text_h': live.get('textH'),
            'closed_font': closed.get('fontSize'),
            'time_w': live.get('timeW'),
            'rail': r.get('rail'),
            'header_overflow_x': (r.get('header') or {}).get('overflowX'),
            'controls_past_by': max([b['past_by'] for b in
                                     ((r.get('controls') or {}).get('buttons') or [])] or [0]),
            'overflowing': r.get('overflowing'),
            'png': png,
            'rc': rc,
        }
        print('%-24s live=%-7s col=%-5s over_x=%-5s boxes=%-3s closed=%-7s ctrl_past=%-4s %s' % (
            theme, results[theme]['live_font'], results[theme]['live_text_w'],
            results[theme]['live_overflow_x'], results[theme]['live_line_boxes'],
            results[theme]['closed_font'], results[theme]['controls_past_by'], png))

    out = os.path.join(args.outdir, 'measure-%s.json' % args.surface)
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print('WROTE ' + out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
