#!/usr/bin/env python3
"""Screenshot the REAL panel document, per theme, per surface, in headless Chromium.

WHAT IT IS FOR. The owner asked for the templates to be "very close to the ones in
the .zip files", INCLUDING how the live subtitles sit at the bottom and in the
middle of the screen. A grep cannot see a layout, so this instrument renders the
SHIPPED app/panel/ into a PNG and leaves it on disk to be looked at.

THE FRAME IS THE APP'S OWN WINDOW, MEASURED, AND THAT IS THE WHOLE INSTRUMENT.
shot.py used to shoot a 1040x900 stage with the rail docked right. That framing is
not what the app draws, for TWO measured reasons:

  1. --screenshot takes --window-size as the VIEWPORT. The belief that it needs a
     frame added came from measuring the DOM with --dump-dom, which emulates a
     window WITH browser chrome (there, viewport = requested - 24 px wide, - 92 px
     tall). It does NOT hold for --screenshot. MEASURED 2026-10-09 with a marker
     document (pure #ff0000 page, the panel forced to a pure #00ff00 380 px block
     docked right):
        --window-size=1040,900 -> PNG 1040x900, the block 380x900 at x=660
        --window-size=1064,992 -> PNG 1064x992, the block 380x992 at x=684
     i.e. the PNG IS the viewport. Adding the frame back produced a PNG 24 px too
     wide and 92 px too tall, stretching the rail 92 px past the viewport it was
     calibrated in and computing every vh in it (the mid-rail padding included)
     against a viewport the owner does not have. THE OFFSETS ARE GONE.
  2. the vw ramp. The generated themes size the live line with
     clamp(A, Nvw, B) (gen_themes.py), so the TYPE SCALE DEPENDS ON THE VIEWPORT
     WIDTH. The app's panel window is 380 x 900 (PANEL_WIDTH/PANEL_HEIGHT,
     app/webview/sotto_webview.py:84-85), where vw == 380; the same document inside
     a 1040 px stage gets a viewport of 1040 and theme-1's live line renders at
     4.6vw = 47.8 px instead of its 30 px floor - 60% larger than the app. So the
     faithful shot is 380 x 900 and the docked stage is NOT (see --dock below).

So the presets reproduce the shell's own windows:
  panel5  PANEL_SIZE  = 380 x 900  (sotto_webview.py PANEL_WIDTH x PANEL_HEIGHT)
  strip5  STRIP_SIZE  = 1040 x 150 (sotto_webview.py STRIP_WIDTH x STRIP_HEIGHT)
  panelctx5  the same rail docked right in a 1040x900 stage, ONLY to answer "where
             does it sit on the desktop" - its type scale is NOT the app's (reason
             2 above), so it is named *-context-* and is never the proof of a size.

THE 492 px WIDTH CLAMP IS ALSO MEASURED, AND IT DOES NOT APPLY HERE. The old
docstring said a 380 px-wide PNG was unobtainable because headless Edge clamps the
layout viewport to 492 px. That clamp was measured with --dump-dom; re-measured
2026-10-09 with --screenshot, --window-size=380,900 -> PNG 380x900, 380x150 ->
380x150, even 150x400 -> 150x400. There is no clamp to escape, so the old
"screenshot it is not obtainable" is FALSE and the dock-only framing it justified
is retired as the default.

WHY HEADLESS EDGE, NOT THE APP:
  1. the engine. The app is WebView2, which IS Chromium; --headless=new on Edge is
     the same engine class without the HWND.
  2. geometry. --window-size is the viewport, so the two surfaces are shot in
     exactly the windows the shell creates for them.
  3. no window on the owner's screen. Headless Chromium draws nothing.

WHAT IS COPIED, AND WHAT IS REWRITTEN. A COPY of app/panel/ in a scratch dir (the
shipped directory is never touched). Three edits, and only three:
  * <body ... data-surface="..."> -> the surface being shot, by REGEX ON THE BODY
    TAG. A plain str.replace hit the COMMENT above the markup first
    (panel.html's own doc comment quotes data-surface="panel" two lines above the
    real tag) and left every body on the panel surface -- that is how the strip
    shots used to come out as panel shots.
  * <html ... data-theme="theme-N"> -> the theme being shot, by regex on the HTML
    tag, for the same reason.
  * <script src="_shot.js"></script> and <link rel=stylesheet href="_shot.css">
    appended before </body>. _shot.js builds the three real caption rows (older
    settled / just closed / LIVE forming) exactly the way _geom.js does, so the
    shot shows live subtitle styling, and re-applies the theme THROUGH THE
    SWITCHER after boot (see below).

TWO TRAPS THIS DOCUMENT IS MADE OF, both of which produced a picture that looked
plausible and lied:
  1. panel.html MUST BE WRITTEN AFTER THE COPY LOOP. Writing it first and then
     copying every file in app/panel/ OVERWROTE the rewritten copy with the
     shipped one, byte for byte: the shot was of an unmodified panel.html with
     data-theme="theme-1" and data-surface="panel", no matter the arguments.
  2. THE MARKUP'S THEME IS NOT THE THEME. theme-switcher.js apply() runs from
     <head> at parse and writes the STORED theme (empty store -> the theme-1
     fallback) over whatever attribute the markup carries, and its mount() runs
     again on DOMContentLoaded. So _shot.js also calls
     window.SottoTheme.set(theme, {persist:false}) AFTER boot -- the same arm
     _geom.js uses, and the reason the theme in these PNGs is the one asked for.
     (This one bit hard: while SHOT_JS interpolated the names UNQUOTED, _shot.js
     died on a ReferenceError before it could force anything and all five panel
     PNGs came out byte-identical theme-1 renders.)

THE HASH IS PART OF THE SHOT: the URL carries #panel / #strip, which surface.js
reads at boot (headless Edge has no shell bridge to tell it otherwise).

USAGE
    py -3 _main\_design-lane\shot.py --preset panel5
    py -3 _main\_design-lane\shot.py --preset strip5
    py -3 _main\_design-lane\shot.py --preset panelctx5
    py -3 _main\_design-lane\shot.py --themes theme-1,cine-rainline --surface panel
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PANEL = os.path.join(REPO, 'app', 'panel')
EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'

# --screenshot takes --window-size as the VIEWPORT (measured above). There is
# deliberately no offset to add back into the request.
#
# The three frames, and where each number comes from:
#   PANEL_SIZE = PANEL_WIDTH x PANEL_HEIGHT   (sotto_webview.py:84-85)
#   STRIP_SIZE = STRIP_WIDTH x STRIP_HEIGHT   (sotto_webview.py:605-606)
PANEL_WIDTH = 380           # app/webview/sotto_webview.py PANEL_WIDTH
PANEL_SIZE = (380, 900)
STRIP_SIZE = (1040, 150)


SHOT_JS = r'''(function () {
  'use strict';
  var THEME = '%(theme)s';
  var SURFACE = '%(surface)s';

  function settledLi(text, cls, time) {
    var li = document.createElement('li');
    li.className = cls;
    var t = document.createElement('span'); t.className = 'caption__time'; t.textContent = time;
    var b = document.createElement('span'); b.className = 'caption__text'; b.textContent = text;
    li.appendChild(t); li.appendChild(b);
    return li;
  }

  function go() {
    /* THE SWITCHER OWNS THE ATTRIBUTE. apply() ran from <head> and wrote the
       stored theme (empty store -> theme-1) over the markup; mount() ran on
       DOMContentLoaded and painted it again. Setting the attribute by hand now
       would be fought by the switcher's own MutationObserver, so the theme is set
       the only way the app itself sets it. */
    try { if (window.SottoTheme) { window.SottoTheme.set(THEME, { persist: false }); } } catch (e) {}
    try { document.documentElement.dataset.theme = THEME; } catch (e) {}
    try { document.body.dataset.surface = SURFACE; } catch (e) {}

    var list = document.getElementById('caption-list');
    if (!list) { return; }
    list.appendChild(settledLi('O som chega antes da imagem.', 'caption', '10:23:58'));
    list.appendChild(settledLi('Quando a frase fecha, ela ganha peso - e fica.', 'caption caption--latest', '10:24:04'));
    var forming = document.createElement('li');
    forming.className = 'caption caption--provisional';
    var t1 = document.createElement('span'); t1.className = 'caption__time'; t1.textContent = '10:24:01';
    var body1 = document.createElement('span'); body1.className = 'caption__text';
    var conf = document.createElement('span'); conf.className = 'caption__confirmed';
    conf.textContent = 'A legenda nasce enquanto a frase';
    var prov = document.createElement('span'); prov.className = 'caption__provisional';
    prov.textContent = ' ainda esta em formacao -';
    body1.appendChild(conf); body1.appendChild(prov);
    forming.appendChild(t1); forming.appendChild(body1);
    list.appendChild(forming);
    list.hidden = false;
    var ph = document.getElementById('placeholder'); if (ph) ph.hidden = true;

    /* what followNewestLine() does in effect: the rail follows the newest line by
       scrolling to the bottom, unconditionally, when there is something to
       scroll. Without this the shot shows the TOP of the rail, which is where the
       mask fades everything out. */
    var rail = document.getElementById('captions-body');
    if (rail) { rail.scrollTop = rail.scrollHeight; }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(go, 300); });
  } else { setTimeout(go, 300); }
})();
'''
# Shot-only dressing. The real overlay is transparent -- this paints the desktop it
# sits on in the app's own ink, so a PNG opened in a white-background viewer reads
# the fades and the blur instead of dissolving into white. --dock additionally
# parks the rail at the right edge of a wider stage; it is NOT the default because
# the vw ramp in the generated themes then sizes the type against the STAGE's
# width, not the panel's (see the docstring).
CSS_COMMON = 'html, body { background: #0b0d10; }\n'
CSS_DOCK_PANEL = (
    'body[data-surface="panel"] > main.panel {\n'
    '  left: auto;\n'
    '  right: 0;\n'
    '  width: %dpx;\n'
    '}\n' % PANEL_WIDTH)


def build(theme, surface, workdir, dock=False):
    """A copy of the real panel, wearing theme + surface, with the caption fixture."""
    for name in os.listdir(PANEL):
        src = os.path.join(PANEL, name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(workdir, name))
    for sub in ('themes', 'fonts', 'backdrops'):
        sdir = os.path.join(PANEL, sub)
        if os.path.isdir(sdir):
            os.makedirs(os.path.join(workdir, sub), exist_ok=True)
            for fn in os.listdir(sdir):
                s = os.path.join(sdir, fn)
                if os.path.isfile(s):
                    shutil.copyfile(s, os.path.join(workdir, sub, fn))

    with open(os.path.join(PANEL, 'panel.html'), encoding='utf-8') as fh:
        html = fh.read()

    # THE TAG, NOT THE PROSE. panel.html's own comment quotes data-theme on <html>
    # and data-surface="panel" two lines above the real body tag, so a
    # str.replace(count=1) that starts at the top of the file rewrites the COMMENT
    # and leaves the document on panel/theme-1.
    html, n_theme = re.subn(r'(<html\b[^>]*?)data-theme="[^"]*"',
                            r'\1data-theme="%s"' % theme, html, count=1)
    if n_theme != 1:
        raise SystemExit('panel.html no longer carries the base data-theme attribute')
    html, n_surface = re.subn(r'(<body\b[^>]*?)data-surface="[^"]*"',
                              r'\1data-surface="%s"' % surface, html, count=1)
    if n_surface != 1:
        raise SystemExit('panel.html no longer carries the base data-surface attribute')

    with open(os.path.join(workdir, '_shot.js'), 'w', encoding='utf-8', newline='') as fh:
        fh.write(SHOT_JS % {'theme': theme, 'surface': surface})
    with open(os.path.join(workdir, '_shot.css'), 'w', encoding='utf-8', newline='') as fh:
        fh.write(CSS_COMMON)
        if dock and surface == 'panel':
            fh.write(CSS_DOCK_PANEL)

    inject = ('    <link rel="stylesheet" href="_shot.css">\n'
              '    <script src="_shot.js"></script>\n')
    html = html.replace('</body>', inject + '  </body>', 1)

    # LAST, and only once: the copy loop above already dropped every app/panel/
    # file into workdir, panel.html included. Writing it first is what used to
    # make every shot an unmodified panel.html.
    hp = os.path.join(workdir, 'panel.html')
    with open(hp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)
    return hp


def png_size(path):
    """The PNG's declared pixel box, straight out of the IHDR header.

    The log prints it next to what was asked for, so a frame that drifts is
    visible in the output instead of only in the pixels.
    """
    try:
        with open(path, 'rb') as fh:
            head = fh.read(24)
    except OSError:
        return (0, 0)
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n':
        return (0, 0)
    return struct.unpack('>II', head[16:24])


def shoot(html_path, out_png, w, h, surface, budget=9000):
    # the hash is the documented affordance surface.js reads at boot, and it is
    # what makes the render deterministic: headless Edge has no shell bridge, so
    # the markup and this hash are the only two signals a surface gets.
    url = 'file:///' + html_path.replace(os.sep, '/') + '#' + surface
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
           '--no-default-browser-check', '--hide-scrollbars',
           '--force-device-scale-factor=1', '--default-background-color=00000000',
           '--virtual-time-budget=%d' % budget,
           '--window-size=%d,%d' % (w, h),
           '--screenshot=%s' % out_png, url]
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    try:
        err = (proc.stderr or b'').decode('utf-8', 'replace')[:300]
    except Exception:
        err = ''
    return os.path.isfile(out_png), proc.returncode, err


PRESETS = {
    # name: (themes, surface, (w, h), dock)
    'panel5': ('theme-1,theme-2,theme-3,theme-4,theme-5', 'panel', PANEL_SIZE, False),
    'strip5': ('theme-1,theme-2,theme-3,theme-4,theme-5', 'strip', STRIP_SIZE, False),
    # the rail on a stage: answers "where does it sit", never "how big is the type"
    'panelctx5': ('theme-1,theme-2,theme-3,theme-4,theme-5', 'panel', (1040, 900), True),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--themes', default='theme-1')
    ap.add_argument('--surface', default='panel', choices=('panel', 'strip'))
    ap.add_argument('--w', type=int, default=0)
    ap.add_argument('--h', type=int, default=0)
    ap.add_argument('--outdir', default='I:/cc-tmp/shots')
    ap.add_argument('--preset', default='')
    ap.add_argument('--dock', action='store_true',
                    help='park the rail at the right edge of a wider stage (NOT the '
                         'app frame: the vw ramp then sizes type against the stage)')
    ap.add_argument('--budget', type=int, default=9000)
    args = ap.parse_args()

    if args.preset:
        try:
            themes, surface, (args.w, args.h), dock = PRESETS[args.preset.lower()]
        except KeyError:
            raise SystemExit('unknown preset %r (%s)' % (
                args.preset, '|'.join(sorted(PRESETS))))
        args.themes, args.surface, args.dock = themes, surface, dock

    if not args.w or not args.h:
        args.w, args.h = STRIP_SIZE if args.surface == 'strip' else PANEL_SIZE

    tag = 'context-' if args.dock else ''
    os.makedirs(args.outdir, exist_ok=True)
    base = tempfile.mkdtemp(prefix='sotto-shot-', dir=args.outdir)
    ok_all = True
    for theme in [t.strip() for t in args.themes.split(',') if t.strip()]:
        workdir = os.path.join(base, theme)
        os.makedirs(workdir, exist_ok=True)
        html = build(theme, args.surface, workdir, args.dock)
        png = os.path.join(args.outdir, '%s%s-%s.png' % (args.surface, tag, theme))
        ok, rc, err = shoot(html, png, args.w, args.h, args.surface, args.budget)
        size = os.path.getsize(png) if os.path.isfile(png) else 0
        pw, ph = png_size(png) if ok else (0, 0)
        print('%-16s %-6s ask=%4dx%-4d png=%-10s %8dB %s' % (
            theme, args.surface, args.w, args.h, '%dx%d' % (pw, ph),
            size, png))
        if not ok:
            ok_all = False
            print('   FAILED: ' + err)
    shutil.rmtree(base, ignore_errors=True)
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
