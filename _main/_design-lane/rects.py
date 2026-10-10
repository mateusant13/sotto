# -*- coding: utf-8 -*-
"""Inventory EVERY visible element's box in the shipped panel, per surface.

WHY. The PNGs are the deliverable, but a PN G cannot name its own parts: the strip
shots show ink at y=2, y=14-22, y=42-66, y=93-119 and a 7x7 glyph at y=132, and
only the DOM says which element each of those is. This probe renders the SAME
document (same caption fixture as shot.py, same forced theme) with a measuring
script injected, prints the numbers into the DOM, and --dump-dom prints them back.

USAGE
  python _main/_design-lane/rects.py --theme theme-3 --surface strip
  python _main/_design-lane/rects.py --theme theme-1 --surface panel
  python _main/_design-lane/rects.py --size 1040x150 --surface strip

--size WxH asks Edge for a window other than the per-surface default.

THE WINDOW IS NOT THE VIEWPORT. This probe runs --dump-dom, so Edge chrome costs
24 px of the requested width and 92 px of its height (MEASURED: window 992 ->
inner 900 tall, 1064 -> 1040 wide). shot.py pays no such price: its PNG IS the
viewport. Never copy these offsets into shot.py.

THE PANEL ARM CANNOT MEASURE 380 px. Edge clamps the LAYOUT VIEWPORT at 492 px
(a window width of 516): every request at or under 515 renders 492 inner whatever
was asked -- MEASURED 380/404/410/440/480/500/510/515 -> 492 -- and from 516 up
the -24 arithmetic holds exactly (516 -> 492, 520 -> 496, 700 -> 676). The panel
numbers below are therefore 492 wide, NOT the shipped 380 (PANEL_WIDTH,
app/webview/sotto_webview.py:84-85); the header line prints what Edge really
measured, and only that number belongs in a report. shot.py's --screenshot arm
has no such floor and IS the 380 proof.

"""

# The window this probe asks Edge for, per surface. NOT the viewport: under
# --dump-dom Edge chrome takes 24 px off the width and 92 px off the height, and a
# requested width at or under 515 is clamped to a 492 inner viewport (see the module
# docstring). The header prints the MEASURED inner size, which is the only one worth
# citing.
DEFAULT_SIZES = {'panel': (380 + 24, 900 + 92), 'strip': (1040 + 24, 150 + 92)}

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PANEL = os.path.join(REPO, 'app', 'panel')
EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
PROBE_PATH = os.path.join(HERE, '_rects.js')


def build(theme, surface, workdir):
    # EVERY top-level file of app/panel/, panel.css INCLUDED. Copying only the
    # subdirectories left the document with its theme CSS but no panel.css, and
    # the first run of this probe then measured the UNSTYLED document -- a 491 px
    # vertical stack in a 150 px window, `.stripbar` visible, nothing hidden. A
    # probe whose subject silently lost its stylesheet reports the stylesheet's
    # absence as the subject's defect, so check what the copy really contains
    # before naming what it found.
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
    html, n_t = re.subn(r'(<html\b[^>]*?)data-theme="[^"]*"',
                        lambda m: m.group(1) + 'data-theme="%s"' % theme, html, count=1)
    html, n_s = re.subn(r'(<body\b[^>]*?)data-surface="[^"]*"',
                        lambda m: m.group(1) + 'data-surface="%s"' % surface, html, count=1)
    if n_t != 1 or n_s != 1:
        raise SystemExit('tag rewrite failed (theme=%d surface=%d)' % (n_t, n_s))
    probe = (open(PROBE_PATH, encoding='utf-8').read()
             .replace('%(theme)s', theme).replace('%(surface)s', surface))
    with open(os.path.join(workdir, '_rects.js'), 'w', encoding='utf-8', newline='') as fh:
        fh.write(probe)
    html = html.replace('</body>',
                        '    <script src="_rects.js"></script>\n  </body>', 1)
    hp = os.path.join(workdir, 'panel.html')
    with open(hp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)
    return hp


def measure(html_path, w, h, surface):
    # --dump-dom emulates a window WITH browser chrome: MEASURED on this box
    # 2026-10-09, the viewport is the request minus 24 px wide and 92 px tall,
    # at every size tried. --screenshot does NOT subtract (the PNG IS the
    # viewport), so these offsets are dump-dom-only and must never be copied
    # into shot.py.
    url = 'file:///' + html_path.replace(os.sep, '/') + '#' + surface
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
           '--no-default-browser-check', '--hide-scrollbars',
           '--force-device-scale-factor=1', '--virtual-time-budget=8000',
           '--window-size=%d,%d' % (w, h), '--dump-dom', url]
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    return (proc.stdout or b'').decode('utf-8', 'replace')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--size', default=None, help='window WxH (default: per surface, see DEFAULT_SIZES)')
    ap.add_argument('--theme', default='theme-3')
    ap.add_argument('--surface', default='strip', choices=('panel', 'strip'))
    ap.add_argument('--work', default=None)
    args = ap.parse_args()

    # The panel fixture contains glyphs (arrows, quotes) that cp1252 stdout cannot
    # encode; without this the WHOLE run dies after producing nothing.
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    work = args.work or os.path.join(os.environ.get('TMPDIR', 'I:/cc-tmp'), 'rects-work')
    wd = os.path.join(work, args.theme + '-' + args.surface)
    if os.path.isdir(wd):
        shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(wd, exist_ok=True)
    hp = build(args.theme, args.surface, wd)
    size = DEFAULT_SIZES[args.surface]
    if args.size:
        try:
            w, h = args.size.lower().split('x')
            size = (int(w), int(h))
        except ValueError:
            raise SystemExit('--size wants WxH, got %r' % args.size)
    dom = measure(hp, size[0], size[1], args.surface)
    m = re.search(r'<pre id="rects-out">(.*?)</pre>', dom, re.S)
    if not m:
        print('NO PROBE OUTPUT')
        return 1
    data = json.loads(m.group(1))
    inner = data.get('inner') or {}
    asked = (size[0] - 24, size[1] - 92)
    got = (inner.get('w'), inner.get('h'))
    note = '' if got == asked else ('   <-- CLAMPED: asked %dx%d, Edge rendered %sx%s'
                                     % (asked[0], asked[1], got[0], got[1]))
    print('inner=%sx%s  dpr=%s  theme=%s surface=%s  window=%dx%d%s'
          % (got[0], got[1], data.get('dpr'), data.get('theme'),
             data.get('surface'), size[0], size[1], note))
    print('%-6s %-22s %7s %7s %6s %6s  %-6s %-8s %-22s %s'
          % ('tag', 'class/id', 'x', 'y', 'w', 'h', 'fs', 'color', 'bg', 'text'))
    for e in data['els']:
        print('%-6s %-22s %7s %7s %6s %6s  %-6s %-8s %-22s %s'
              % (e['tag'], (e['id'] or e['cls'])[:22], e['x'], e['y'], e['w'], e['h'],
                 e['fs'], e['color'], e['bg'][:22], e['txt']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
