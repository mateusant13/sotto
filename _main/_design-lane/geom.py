# -*- coding: utf-8 -*-
"""Measure the SHIPPED panel's geometry in headless Edge, per theme and surface.

WHY A PROBE AND NOT A SCREENSHOT. A PNG can be looked at by the OWNER; it cannot
be read by this session's model. So the very same document is rendered once more
with a measuring script injected, its numbers written into the DOM, and
`--dump-dom` prints them back. What is measured:

  * every `.strip-button`'s box, its border radius and whether its label paints
    (the strip-minimalism rule: glyphs only, except the template name and LIVE);
  * the live caption line's distance from the bottom of the scroll box, after the
    box is scrolled to the newest -- the number that says "middle" or "bottom".

USAGE
  py -3 _main/_design-lane/geom.py --themes theme-3 --surface panel
  py -3 _main/_design-lane/geom.py --themes theme-1,theme-3 --surface strip
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PANEL = os.path.join(REPO, 'app', 'panel')
EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'

# the measuring script lives beside this file, so quoting never fights the
# embedded markup: the probe inserts elements whose attributes carry quotes.
PROBE = open(os.path.join(HERE, '_geom.js'), encoding='utf-8').read()



def build(theme, surface, workdir):
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
    old = 'data-theme="theme-1"'
    if old not in html:
        raise SystemExit('panel.html no longer carries the base data-theme attribute')
    html = html.replace(old, 'data-theme="%s"' % theme, 1)
    # Only the BODY tag is rewritten, and by pattern rather than by a plain
    # replace: the document quotes `data-surface="panel"` in a comment above
    # the markup, so a `str.replace(count=1)` used to paint the COMMENT and
    # leave the body on the panel surface (measured: strip layout, but
    # `body.dataset.surface === 'panel'`, and the theme's radius winning).
    html = re.sub(r'(<body[^>]*?)data-surface="[^"]*"',
                  lambda m: m.group(1) + 'data-surface="%s"' % surface, html, count=1)
    # the probe is told which theme the document is WEARING, not just reading:
    # theme-switcher.js's `apply()` runs in <head> before the body exists and
    # overwrites `<html data-theme>` from its store (empty here) with the
    # fallback theme-1 — measured, a theme-3 document reported `theme-1`.
    # Threading the name through the script tag lets the probe restore it through
    # the module's OWN api (`set(name,{persist:false})`: one attribute write plus a
    # repaint of every label), which is the same path the owner's click takes.
    html = html.replace('  </body>',
                        '    <script src="_geom.js" data-measured-theme="%s"></script>' % theme
                        + '\n' + '  </body>')
    for name in os.listdir(PANEL):
        s = os.path.join(PANEL, name)
        if os.path.isfile(s) and name != 'panel.html':
            shutil.copyfile(s, os.path.join(workdir, name))
    # the rewritten document is written LAST: the copy above would otherwise
    # overwrite it with the shipped bytes
    with open(os.path.join(workdir, 'panel.html'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)
    return os.path.join(workdir, 'panel.html')


def measure(html_path, w, h, surface):
    # the hash is the DOCUMENTED harness affordance (surface.js reads it), and
    # it is what makes the render deterministic: headless Edge has no shell
    # bridge, so the attribute in the markup is the only other signal.
    url = 'file:///' + html_path.replace(os.sep, '/') + '#' + surface
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
           '--no-default-browser-check', '--hide-scrollbars',
           '--force-device-scale-factor=1', '--virtual-time-budget=8000',
           '--window-size=%d,%d' % (w, h), '--dump-dom', url]
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    return (proc.stdout or b'').decode('utf-8', 'replace')


def main():
    # The fixture carries text and identifiers that cp1252 stdout cannot encode;
    # without this the run dies after printing nothing at all.
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--themes', default='theme-1')
    ap.add_argument('--surface', default='panel', choices=('panel', 'strip'))
    ap.add_argument('--work', default=None)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    themes = [t.strip() for t in args.themes.split(',') if t.strip()]
    work = args.work or os.path.join(os.environ.get('TMPDIR', 'I:/cc-tmp'), 'geom-work')
    for theme in themes:
        wd = os.path.join(work, theme + '-' + args.surface)
        if os.path.isdir(wd):
            shutil.rmtree(wd, ignore_errors=True)
        os.makedirs(wd, exist_ok=True)
        with open(os.path.join(wd, '_geom.js'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(PROBE)
        hp = build(theme, args.surface, wd)
        # Edge headless subtracts a fixed frame from --window-size (MEASURED:
        # -24 px wide, -92 px tall, at every size tried), so the requests carry
        # the frame as an offset and the LAYOUT VIEWPORT is the real one --
        # measuring a 150 px strip against a 58 px viewport understates it by 92.
          # AND THE FLOOR: Edge clamps the LAYOUT VIEWPORT at 492 px (a window
          # width of 516), so a request at or under 515 renders an inner width of
          # 492 whatever was asked -- MEASURED 380/404/410/440/480/500/510/515 ->
          # 492; from 516 up the -24 arithmetic holds (516 -> 492, 520 -> 496,
          # 700 -> 676). The 380 px panel viewport is UNREACHABLE with --dump-dom:
          # the panel arm measures 492 wide, NOT the shipped 380 -- say so wherever
          # its numbers are quoted. shot.py's --screenshot arm has no such floor.
        size = (380 + 24, 900 + 92) if args.surface == 'panel' else (1040 + 24, 150 + 92)
        dom = measure(hp, size[0], size[1], args.surface)
        m = re.search(r'<pre id="geom-out">(.*?)</pre>', dom, re.S)
        if not m:
            print('%s  %s  NO-PROBE' % (theme, args.surface))
            continue
        try:
            data = json.loads(m.group(1))
        except Exception as exc:
            print('%s  %s  BAD-JSON %s' % (theme, args.surface, exc))
            continue
        if args.json:
            print(json.dumps({'theme': theme, 'surface': args.surface, 'data': data}))
            continue
        print('=== %s / %s' % (theme, args.surface))
        # the rendered surface and theme, read from the DOM AFTER boot: the two
        # places this instrument used to be able to lie (reporting 'panel' for a
        # strip render, and theme-1 for a theme-3 one) are both attributed here.
        print('  rendered: surface=%s theme=%s (asked %s/%s)'
              % (data.get('surface'), data.get('theme'), args.surface, theme))
        bar = data.get('bar')
        if bar:
            print('  bar %sx%s viewport=%s insets l=%s r=%s b=%s r=%s dots=%s word=%r'
                  % (bar['w'], bar['h'], bar['viewport'], bar['leftInset'],
                     bar['rightInset'], bar['bottomInset'], bar['radius'],
                     bar['dots'], bar['wordmark']))
        print('  pad-bottom=%s  mask=%s' % (data.get('paddingBottom'), data.get('maskImage')))
        rl = data.get('rail')
        if rl:
            print('  rail top=%s scrollH=%s clientH=%s overflow=%s'
                  % (rl['scrollTop'], rl['scrollHeight'], rl['clientHeight'],
                     rl['scrollHeight'] > rl['clientHeight']))
            print('  live fromBottom=%s fromTop=%s  (clientH/2=%.0f)'
                  % (rl['fromBottom'], rl['fromTop'], rl['clientHeight'] / 2.0))
        print('  list children=%s' % (data.get('list') or {}).get('children'))
        for b in data.get('buttons', []):
            print('    %-26s %3sx%-3s r=%-6s %s' % (b['id'], b['w'], b['h'], b['radius'], b['label']))


if __name__ == '__main__':
    main()