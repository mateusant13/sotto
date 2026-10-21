#!/usr/bin/env python3
"""audit-shots.py -- FRESH prints for the 2026-10-21 design audit.

WHY A NEW SET. The 2026-10-20 intake set (docs/design-intake/) answered "why does
it truncate"; this set answers "what does each design look like on EVERY surface
the owner actually sees". It is written to a new root so the old set stays as the
record it is, and NOTHING is reused: every job below renders again.

WHAT IT PRINTS, per product theme (45):
    product/panel/<theme>.png     380x900  the right panel
    product/strip/<theme>.png    1040x150  the bottom strip
    product/caption/<theme>.png   900x170  the live caption overlay, over grey
    product/meta/<theme>.json              the measurements of all three
and per demo of the five .zip originals (50):
    demos/<zip>/<nn-name>/app.png          the demo as the owner sees it
    demos/<zip>/<nn-name>/panel.png        the demo's OWN panel, clipped
    demos/<zip>/<nn-name>/meta.json        its measurements

THE INSTRUMENT is `cdp.mjs`, not Edge's --screenshot: the layout viewport of a
headless Edge screenshot is clamped to 492 px on this box (measured 2026-10-20),
so a 380 px panel would be a 492 px layout cropped to 380. `cdp.mjs` sets the
LAYOUT viewport over the DevTools protocol.

THE PRODUCT SIDE loads the deferred sheets the way the shell does: `lazy-assets.js`
+ a `window.sotto.dispatch` stub, both injected as FILES (the panel's CSP has no
'unsafe-inline'). See panel-measure.py for the measurement of what a copy without
it paints (the base skin, not the theme).

USAGE
    python _main/_design-lane/audit-shots.py --root docs/design-audit-20261021
    python _main/_design-lane/audit-shots.py --only product --themes theme-1
"""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import shot  # noqa: E402

CDP = os.path.join(HERE, 'cdp.mjs')
PROBE_PANEL = os.path.join(HERE, 'probe-panel.js')
PROBE_CAPTION = os.path.join(HERE, 'probe-caption.js')
PANEL = os.path.join(REPO, 'app', 'panel')

# intake-shots.py has a dash in its name: load it by path for its demo tables.
_spec = importlib.util.spec_from_file_location(
    'intake_shots', os.path.join(HERE, 'intake-shots.py'))
intake = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(intake)

PANEL_W, PANEL_H = 380, 900
#: THE TWO BOTTOM SURFACES. 40 px is the bar itself (`--strip-height: 40px`,
#: panel.css:3069, which the shell reads); 220 px is the bar plus the floated
#: caption (`--float-height: 220px`), the window the owner gets while LINHAR is on.
STRIP_W, STRIP_BAR_H, STRIP_FLOAT_H = 1040, 40, 220

PRODUCT_THEMES = intake.PRODUCT_THEMES

# ---------------------------------------------------------------- fixtures ---

FIXTURE = r'''(function () {
  'use strict';
  var THEME = '__SHOT_THEME__';
  var SURFACE = '__SHOT_SURFACE__';
  var FLOAT = __SHOT_FLOAT__;
  /* THE THEME RIDES IN THE HASH. One copied document serves all 45 themes, so
     the theme cannot be baked into `_shot.js`; `#panel&theme=cine-linen` is
     parsed here and surface.js refuses the compound token, leaving the markup's
     surface alone (the fixture writes the real one below). */
  try {
    var hm = decodeURIComponent(String(location.hash || '')).match(/(?:^|[&#])theme=([^&]+)/);
    if (hm) THEME = hm[1];
  } catch (e) {}
  var LIVE = 'A legenda nasce enquanto a frase ainda esta em formacao.';
  var PREV = 'Quando a frase fecha, ela ganha peso - e fica.';
  /* A REAL SESSION, NOT FOUR LINES ON A 900 px SHEET. Four rows left every
     bottom-anchored design (theme-1, the cinematic sheets) with 500+ px of void in
     the photograph, which reads as a broken panel. The product fills this list as
     the worker closes lines; the fixture should show the same density. The last
     line is still the forming one, and the one before it is still `--latest`. */
  var LINES = [
    ['10:23:58', 'O som chega antes da imagem.', 0],
    ['10:24:01', 'Antes da primeira cena, ja existe um rumor de sala.', 0],
    ['10:24:04', 'A sala respira entre uma frase e a seguinte.', 0],
    ['10:24:08', 'Cada palavra chega com o seu proprio tempo.', 0],
    ['10:24:12', 'O microfone apanha a chuva la fora.', 0],
    ['10:24:17', 'Ninguem pediu uma segunda leitura.', 0],
    ['10:24:21', 'O texto fecha a linha quando o silencio chega.', 0],
    ['10:24:25', 'A legenda espera o proximo gesto.', 0],
    ['10:24:29', PREV, 0],
    ['10:24:34', LIVE, 1]
  ];
  function go() {
    try { if (window.SottoTheme) { window.SottoTheme.set(THEME, { persist: false }); } } catch (e) {}
    try { document.documentElement.dataset.theme = THEME; } catch (e) {}
    try { document.body.dataset.surface = SURFACE; } catch (e) {}

    /* THE LIVE LINE IS THE BOTTOM OF THE COLUMN, AND FONTS ARRIVE AFTER THE
       FIRST SCROLL. The fixture used to scroll once at 500 ms; the webfont then
       loaded, the rows grew by ~80 px, and every panel PNG showed the forming
       line floating above the footer while its own JSON (measured later, after a
       second scroll) said the rail was at the bottom. Re-stick after the font
       has settled, so the image and the measurement are the same state. */
    function stickBottom() {
      var r = document.getElementById('captions-body');
      if (r) { r.scrollTop = r.scrollHeight; }
    }

    var list = document.getElementById('caption-list');
    if (list) {
      for (var i = 0; i < LINES.length; i++) {
        var li = document.createElement('li');
        li.className = 'caption' + (i === LINES.length - 1 ? ' caption--provisional' : '') +
                       (i === LINES.length - 2 ? ' caption--latest' : '');
        /* THE LED IS A REAL NODE IN THE PRODUCT ROW (panel.js:1032). The first
           fixture omitted it, so every design whose identity is a left dot/rail
           was photographed without it -- and `brand-bridge` would have measured
           `ledVisible:false` for all 45 themes. */
        var led = document.createElement('span'); led.className = 'caption__led';
        var t = document.createElement('span'); t.className = 'caption__time'; t.textContent = LINES[i][0];
        var b = document.createElement('span'); b.className = 'caption__text'; b.textContent = LINES[i][1];
        li.appendChild(led); li.appendChild(t); li.appendChild(b);
        list.appendChild(li);
      }
      list.hidden = false;
      stickBottom();
      setTimeout(stickBottom, 900);
      setTimeout(stickBottom, 2200);
      setTimeout(stickBottom, 4000);
    }
    var ph = document.getElementById('placeholder'); if (ph) ph.hidden = true;

    /* THE CINEMATIC SKINS OWN THEIR OWN HISTORY LIST. `skin-host.js` hides the
       stock panel (`body[data-skin]`), mounts the zip's caption fragment in a
       shadow root, and fills it from `window.SottoSkin`; the fixture's rows in
       `#caption-list` are therefore invisible on every `cine-*` theme. The fresh
       2026-10-21 contact sheet showed 25 cinematic panels with a header and an
       EMPTY stage for exactly this reason. Feed the same fixture lines through
       the skin's public API, on the same late schedule as the assets that mount
       it (the skin pair is lazy-loaded after the theme flips). */
    function feedSkin() {
      if (!window.SottoSkin || !window.SottoSkin.active) return false;
      /* THE SKIN'S TRANSCRIPT DRAWER IS THE PANEL. `skin-host.js` hides the
         stock list and paints the zip's own history panel there; with no closed
         lines fed, that drawer is a header, a search field and a 700 px void -
         exactly the "empty stage" the owner photographed on 2026-10-21. The
         mock's own simulated rows are already cleared by `mount()` (`refs.
         historyList` is emptied before the first render), so feeding ours is
         not a duplicate: it is the only transcript on screen. `lines()` is
         idempotent, so every late retry replaces the set instead of appending
         it again. The forming line stays OUT of the drawer; it belongs to the
         design's own live caption plate. */
      try {
        window.SottoSkin.lines(LINES.slice(0, -1).map(function (row) {
          return { text: row[1], time: row[0] };
        }));
      } catch (e) {}
      try {
        window.SottoSkin.live({ committed: [], provisional: LIVE.split(' ') });
      } catch (e) {}
      try { window.SottoSkin.status({ word: 'Live', state: 'live' }); } catch (e) {}
      try { window.SottoSkin.level(0.62); } catch (e) {}
      /* A PRINT IS NOT A MOVIE. The vendor fades the newest word in over 420 ms
         (`word-in`). The last feed runs 500 ms before the shot, but a job that
         lands on the animation's first frames photographs the newest word at 40%
         opacity - measured on cine-rainline, where the closing word was almost
         black. Freeze every animation and transition INSIDE the shadow root so
         every printed live line is at its settled opacity. The product still
         animates; only the audit fixture is frozen. */
      try {
        var host = document.getElementById('skin');
        var sr = host && host.shadowRoot;
        if (sr && !sr.querySelector('style[data-shot-freeze]')) {
          var st = document.createElement('style');
          st.setAttribute('data-shot-freeze', '1');
          st.textContent = '*,*::before,*::after{animation:none!important;transition:none!important}';
          sr.appendChild(st);
        }
      } catch (e) {}
      /* The bridge may already have run its last scheduled read while the word
         host was empty. Ask it to measure the skin NOW. */
      try { if (window.SottoBrand && window.SottoBrand.push) window.SottoBrand.push(); } catch (e) {}
      return true;
    }
    setTimeout(feedSkin, 1200);
    setTimeout(feedSkin, 2500);
    setTimeout(feedSkin, 4000);
    setTimeout(feedSkin, 5600);
    setTimeout(feedSkin, 6000);

    if (FLOAT) {
      try { document.body.setAttribute('data-float', 'on'); } catch (e) {}
      try {
        if (window.SottoCaptionFloat) {
          window.SottoCaptionFloat.setListening(true);
          window.SottoCaptionFloat.push(LIVE, { producer: 'nemotron' });
          window.SottoCaptionFloat.setMeter(0.62);
          window.SottoCaptionFloat.setFloat(true);
        }
      } catch (e) {}
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(go, 500); });
  } else { setTimeout(go, 500); }
})();
'''

def build_surface(theme, surface, workdir, float_on=False):
    """panel-measure's builder (loader + skins), plus a fixture of this surface."""
    html = intake.panel_measure.build(theme, surface, workdir)
    with open(os.path.join(workdir, '_shot.js'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(FIXTURE.replace('__SHOT_THEME__', theme)
                        .replace('__SHOT_SURFACE__', surface)
                        .replace('__SHOT_FLOAT__', 'true' if float_on else 'false'))
    return html


# -------------------------------------------------------------------- jobs ---

#: THE THREE SURFACES the owner actually sees, with the size each one is docked
#: at by the shell. `surface` is what the DOCUMENT wears; `view` is the folder.
VIEWS = (
    ('panel', 'panel', PANEL_W, PANEL_H, PROBE_PANEL, False),
    ('strip', 'strip', STRIP_W, STRIP_BAR_H, PROBE_PANEL, False),
    ('strip-float', 'strip', STRIP_W, STRIP_FLOAT_H, PROBE_CAPTION, True),
)


def product_jobs(root, themes, views=None):
    """One document copy PER VIEW, reused by every theme.

    THE THEME IS RUNTIME, NOT BYTES. `shot.build()` writes the theme into the
    markup, but `_shot.js` forces it again after boot (`SottoTheme.set`), and the
    deferred sheets arrive through the loader. So the same copied document can
    wear all 45 themes; copying `app/panel` 135 times would only copy the same
    bytes 135 times. MEASURED: the copy is what costs seconds per job, not the
    render.
    """
    views = list(views or VIEWS)
    workroot = tempfile.mkdtemp(prefix='audit-shots-',
                                dir=os.environ.get('TMPDIR', 'I:/cc-tmp'))
    jobs = []
    built = {}
    # THE WIRE THEME MUST BE ABLE TO LOAD THE SKIN PAIR AT BOOT. A cinematic
    # theme's assets are lazy: `skins/skins.js` is 812 KB and `skin-host.js`
    # mounts the shadow caption. When the copy boots `theme-1` and a `cine-*`
    # theme is forced 500 ms later, the skin pair races the shot and some panels
    # photographed the STOCK panel (`sotto LIVE/CAPTIONS`, rows at the bottom)
    # while their own JSON already measured the skin (Inter 22.5, 300). Booting
    # with the first cinematic theme in the batch loads the pair before the
    # fixture runs; the requested theme still comes from the hash and the loader
    # follows it. With no cinematic theme, the first requested theme is the wire,
    # exactly as before.
    wire = next((t for t in themes if t.startswith('cine-')), themes[0])
    for view, surface, w, h, probe, float_on in views:
        wd = os.path.join(workroot, view)
        os.makedirs(wd, exist_ok=True)
        built[view] = (build_surface(wire, surface, wd, float_on=float_on), surface)
    for theme in themes:
        for view, surface, w, h, probe, float_on in views:
            html, surface = built[view]
            base = os.path.join(root, 'product', view, theme)
            os.makedirs(os.path.dirname(base), exist_ok=True)
            # A QUERY, NOT ONLY A FRAGMENT. CDP `Page.navigate` treats a same-path,
            # same-query fragment change as SAME-DOCUMENT: no load event fires, the
            # fixture never re-runs, and the job keeps the previous job's theme.
            # MEASURED 2026-10-21: a batch of cine-rainline, cine-adobe and
            # cine-terrace produced three identical Rainline panels, and every JSON
            # reported theme `cine-rainline`. The unique query forces a real load.
            bust = '?job=%s-%s' % (theme, view)
            jobs.append({
                'name': '%s-%s' % (theme, view),
                'url': 'file:///' + html.replace(os.sep, '/') + bust + '#' + surface + '&theme=' + theme,
                'w': w, 'h': h, 'wait': 6500,
                'eval': probe, 'out': base + '.png', 'outJson': base + '.json',
            })
    return jobs, workroot


DEMOS = [
    ('zip1-directions', 'zipA', intake.BUNDLE_A, 1600, 1000, intake.A_DEMOS, '1', 0, '.sotto-panel'),
    ('zip2-panels', 'zipB', intake.BUNDLE_B, 1600, 1800, intake.B_DEMOS, '1', 0, '.panel-in'),
    ('zip3-cinematic', 'zipC', intake.BUNDLE_C, 1600, 1000, intake.C_DEMOS, 'ArrowRight', 0, 'aside'),
    ('zip4-cinematic-1', 'zipC1', intake.BUNDLE_C1, 1600, 1000, intake.C1_DEMOS, 'ArrowRight', 0, 'aside'),
    ('zip5-cinematic-2', 'zipC2', intake.BUNDLE_C2, 1600, 1000, intake.C2_DEMOS, 'ArrowRight', 2, 'aside'),
]


def demo_jobs(root):
    jobs = []
    for zipname, key, url, w, h, demos, press, start, clip in DEMOS:
        for i, (num, name) in enumerate(demos):
            presses = (i - start) % len(demos) if press == 'ArrowRight' else 0
            keys = [press] * presses if presses else []
            if press == '1':
                keys = [str(i + 1)]
            base = os.path.join(root, 'demos', zipname, '%s-%s' % (num, name))
            os.makedirs(base, exist_ok=True)
            jobs.append({
                'name': '%s-%s' % (zipname, name),
                'url': url, 'w': w, 'h': h, 'wait': 2800 + presses * 350,
                'keys': keys, 'after': 900,
                'eval': os.path.join(HERE, 'probe-demo.js'),
                'out': os.path.join(base, 'app.png'),
                'outJson': os.path.join(base, 'meta.json'),
            })
            jobs.append({
                'name': '%s-%s-panel' % (zipname, name),
                'url': url, 'w': w, 'h': h, 'wait': 2800 + presses * 350,
                'keys': keys, 'after': 900, 'clip': clip,
                'out': os.path.join(base, 'panel.png'),
            })
    return jobs


# -------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.join(REPO, 'docs', 'design-audit-20261021'))
    ap.add_argument('--only', default='all', choices=('all', 'product', 'demos'))
    ap.add_argument('--themes', default='')
    ap.add_argument('--views', default='',
                    help='comma list of panel,strip,strip-float')
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    os.makedirs(os.path.join(root, 'data'), exist_ok=True)
    jobs = []
    workroot = None
    if args.only in ('all', 'product'):
        themes = [t.strip() for t in args.themes.split(',') if t.strip()] or PRODUCT_THEMES
        want = [v.strip() for v in args.views.split(',') if v.strip()]
        views = [v for v in VIEWS if not want or v[0] in want]
        if not views:
            raise SystemExit('no known --views in %r' % args.views)
        pj, workroot = product_jobs(root, themes, views)
        jobs.extend(pj)
    if args.only in ('all', 'demos'):
        jobs.extend(demo_jobs(root))

    jf = os.path.join(root, 'data', 'jobs.json')
    with open(jf, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(jobs, fh, indent=1)
    outf = os.path.join(root, 'data', 'jobs-result.json')
    print('jobs: %d' % len(jobs))
    try:
        proc = subprocess.run(['node', CDP, '--jobs', jf, '--json', outf],
                              capture_output=True, timeout=7200)
        sys.stdout.write(proc.stdout.decode('utf-8', 'replace')[-6000:])
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr.decode('utf-8', 'replace')[-3000:])
        return proc.returncode
    finally:
        if workroot:
            shutil.rmtree(workroot, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
