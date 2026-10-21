# WHICH HEADLESS MODE CARRIES THE 492 px FLOOR? And can anything escape it?
#
# WHY. rects.py measures the panel DOM through --dump-dom, and that path clamps the
# layout viewport at 492 px inner (a window width of 516): every request at or under 515
# renders 492 whatever was asked. So the SHIPPED panel width -- PANEL_WIDTH = 380,
# app/webview/sotto_webview.py:84-85 -- is UNREACHABLE by DOM measurement, and every
# number the panel arm reports is 492 wide. That is a hole in the instrument, not a
# fact about the app.
#
# THE QUESTION IS WHETHER THE FLOOR BELONGS TO THE MODE. rects.py asks for
# --headless=new. THIS probe runs the SAME document, the SAME build, the SAME chrome
# offsets, through three modes -- --headless=new, plain --headless, --headless=old --
# at three window widths, and prints the inner size each one really measured.
# Whatever the answer, it is measured here, not assumed.
#
# RUN:  pyw -3 _main/_design-lane/_floor-arms.py [--sizes 404x992 540x992 620x992]
#                       [--themes theme-3] [--surface panel]
#
# It imports rects.py own build(), so the fixture is IDENTICAL to the one the shipped
# probe measures -- only the headless flag differs.

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rects  # noqa: E402  (the shipped probe: build() only, main() stays guarded)

EDGE = rects.EDGE
# --dump-dom chrome offsets, MEASURED on this box 2026-10-09 (rects.py:96-100):
# the viewport is the request minus 24 px wide and 92 px tall.
OFF_W, OFF_H = 24, 92

# The three modes, in run order. Plain --headless has mapped to --headless=new in
# recent Edge builds, so it may be an ALIAS, not a distinct arm -- that is exactly
# what this probe decides.
MODES = ('--headless=new', '--headless', '--headless=old')


def measure(html_path, w, h, surface, mode):
    url = 'file:///' + html_path.replace(os.sep, '/') + '#' + surface
    cmd = [EDGE, mode, '--disable-gpu', '--no-first-run',
           '--no-default-browser-check', '--hide-scrollbars',
           '--force-device-scale-factor=1', '--virtual-time-budget=8000',
           '--window-size=%d,%d' % (w, h), '--dump-dom', url]
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    return ((proc.stdout or b'').decode('utf-8', 'replace'),
            (proc.stderr or b'').decode('utf-8', 'replace'))


def inner_of(dom):
    m = re.search(r'<pre id="rects-out">(.*?)</pre>', dom, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1)).get('inner') or {}
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sizes', nargs='*', default=['404x992', '540x992', '620x992'])
    ap.add_argument('--themes', default='theme-3')
    ap.add_argument('--surface', default='panel', choices=('panel', 'strip'))
    ap.add_argument('--work', default=None)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

    work = args.work or os.path.join(os.environ.get('TMPDIR', 'I:/cc-tmp'), 'floor-arms')
    sizes = []
    for s in args.sizes:
        w, h = s.lower().split('x')
        sizes.append((int(w), int(h)))

    print('modes=%s  sizes=%s  surface=%s' % (list(MODES), args.sizes, args.surface))
    print('%-14s %-12s %-22s %-22s %s'
          % ('mode', 'window', 'asked inner (w-24)', 'MEASURED inner', 'verdict'))
    rows = []
    for mode in MODES:
        for (w, h) in sizes:
            wd = os.path.join(work, mode.strip('-').replace('=', '+'), '%dx%d' % (w, h))
            if os.path.isdir(wd):
                shutil.rmtree(wd, ignore_errors=True)
            os.makedirs(wd, exist_ok=True)
            hp = rects.build(args.themes, args.surface, wd)
            dom, err = measure(hp, w, h, args.surface, mode)
            inner = inner_of(dom)
            asked = (w - OFF_W, h - OFF_H)
            if not inner:
                print('%-14s %-12s %-22s %-22s %s'
                      % (mode, '%dx%d' % (w, h), '%dx%d' % asked, 'NO-PROBE-OUTPUT',
                         'no data (dom %d B, err %d B)' % (len(dom), len(err))))
                rows.append((mode, w, h, None))
                continue
            got = (inner.get('w'), inner.get('h'))
            verdict = 'follows -24' if got == asked else (
                'CLAMPED to %s' % got[0] if got[0] == 492 else 'DIFFERS')
            print('%-14s %-12s %-22s %-22s %s'
                  % (mode, '%dx%d' % (w, h), '%dx%d' % asked, '%dx%d' % got, verdict))
            rows.append((mode, w, h, got))

    print('')
    print('--- can ANY mode render 380 inner? ---')
    for mode, w, h, got in rows:
        if got:
            print('  %-14s %dx%d -> inner %sx%s' % (mode, w, h, got[0], got[1]))
    hit = sorted({r[0] for r in rows if r[3] and r[3][0] == 380})
    if hit:
        print('  YES: %s reach 380 -- the floor is a property of the MODE' % ', '.join(hit))
    else:
        print('  NO: every mode clamps. The 492 floor is not a --headless=new artefact')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
