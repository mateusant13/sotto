#!/usr/bin/env python3
"""Measure what the per-direction chrome animations COST the live panel.

THE OWNER'S CONDITION, from this lane's brief: the live box is rewritten on every
partial, so an animation there must be `opacity`/`transform`/`filter` ÔÇö never a
property that forces a relayout ÔÇö and the cost has to be MEASURED with the
animation on and off. *"O dono acabou de levar com stutter causado por n├│s: um
painel que engasga ├® uma entrega falhada."*

WHAT IS MEASURED, three independent channels, all over the same 6 s caption
stream at 8 partials/s driven into the REAL `panel.js`:

  * `frame`  ÔÇö every `requestAnimationFrame` delta: p50 / p95 / max, and how many
    frames ran over 33.4 ms and over 50 ms;
  * `loaf`   ÔÇö Chromium's LONG ANIMATION FRAME entries: their total `duration`,
    their `blockingDuration`, and their **style+layout** share
    (`startTime + duration - styleAndLayoutStart`). That last number is the
    "layout count" this brief asks for in the only form a page can read it: the
    time each long frame spent in style and layout. A frame that only composites
    adds nothing to it;
  * `push`   ÔÇö `performance.now()` around every `pushCaption`: the panel's own
    synchronous main-thread cost per partial, whatever the compositor does.

THE ARMS, each a separate browser launch, same page, same stream:
  reduced   the box AS IT IS. This machine has Windows animations DISABLED
            (`SPI_GETCLIENTAREAANIMATION` = false, read with user32) and Chromium
            derives `prefers-reduced-motion` from exactly that, so the theme's
            animations are OFF. This is the arm the owner's own app is on.
  on        the same page with motion EMULATED on
            (`--blink-settings=prefersReducedMotion=false`): the theme's real
            animations run. Nothing about the machine is changed.
  relayout  THE CONTROL. The same two elements, the same cadence, but the
            animation is re-declared on `width` ÔÇö a property that changes the box
            and forces a relayout on every frame.

THE VERDICT IS SELF-VALIDATING: one threshold set, applied twice. The `on` arm
must pass it against `reduced`, and the `relayout` CONTROL must FAIL it against
`on`. An instrument whose own control passes its thresholds cannot certify
anything.

Usage:
  py -3 _main\\_panel-anim-cost-arm.py
  py -3 _main\\_panel-anim-cost-arm.py --themes theme-5,theme-2
"""

import argparse
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir))
PANEL = os.path.join(REPO, 'app', 'panel')
OUTDIR = os.path.join(HERE, '_audit-render')
REL = '../../app/panel/'

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

EDGE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
CHROME_CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]

ASSETS = ('panel.css', 'caption-formulation.js', 'history-source.js', 'surface.js',
          'panel.js', 'theme-switcher.js', 'themes/themes.js', 'themes/fonts.css',
          'themes/theme-1.css', 'themes/theme-2.css', 'themes/theme-3.css',
          'themes/theme-4.css', 'themes/theme-5.css')

SECONDS = 6
RATE_HZ = 8

# The ONE threshold set, applied to the real arm AND to the control.
LIMITS = {
    ('loaf', 'styleAndLayout'): 4.0,   # ms of style+layout the animation may add
    ('loaf', 'blocking'): 5.0,         # ms of blocking time it may add
    ('loaf', 'duration'): 6.0,         # ms of long-frame time it may add
    ('frame', 'p95'): 4.0,             # ms on the 95th percentile frame
    ('frame', 'over50'): 2,            # frames over 50 ms it may add
    ('push', 'mean'): 0.30,            # ms per partial on the panel's own path
}


def find_browser(which):
    cands = CHROME_CANDIDATES if which == 'chrome' else EDGE_CANDIDATES
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit('no browser found in %r' % cands)


# --------------------------------------------------------------------------- #
# The beacon receiver. ONE thread (`HTTPServer` is single-threaded on purpose ÔÇö
# this lane's budget is <= 2 threads and the main thread is the other one), and
# it only ever answers 204 to a GET whose `payload=` parses as JSON.
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# THE TRANSPORT, AND WHY THE ARMS ARE SERVED OVER 127.0.0.1 AND NOT `file://`.
#
# This arm runs on REAL time (virtual time would make every frame delta a
# fiction), so there is no moment at which `--dump-dom` could be taken: the
# result has to be pushed out of the page. The first version beacons to a local
# HTTP server from a `file://` document and the beacon never arrived ÔÇö a
# `file://` origin is not allowed to reach a loopback address under Chromium's
# private-network rules, and the workaround (a CSP exception plus a
# `--disable-features` flag) would have meant measuring a document that differs
# from the shipped panel in two more ways.
#
# So the arms are SERVED instead: one `HTTPServer` on 127.0.0.1 serves
#   /panel/<file>   ÔåÆ `app/panel/<file>`          (the real panel assets)
#   /probe/<file>   ÔåÆ `_main/<file>`              (the cost probe)
#   /arm/<file>     ÔåÆ `_main/_audit-render/<file>` (the arm copies + the stub)
# and the page is loaded from `http://127.0.0.1:<port>/arm/...`. The beacon is
# then SAME-ORIGIN, `img-src 'self'` already covers it, and the arm copy differs
# from the shipped `panel.html` by exactly the two extra `<script>` tags ÔÇö no CSP
# change at all. What that costs in honesty: the document is `http://` and not
# `file://`, so its `localStorage` behaves differently. Nothing in this
# measurement reads storage, and `panel.css` / the five theme files / `panel.js`
# are the shipped bytes.
# --------------------------------------------------------------------------- #
class Beacon(BaseHTTPRequestHandler):
    payload = None

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler's own spelling)
        m = re.search(r'[?&]payload=([^&]*)', self.path)
        if m:
            try:
                # `self.path` is the RAW request target, so the JSON is still
                # PERCENT-encoded: `html.unescape` alone left `%7B%22theme%22ÔÇª`
                # and `json.loads` refused it, which made a working transport look
                # like a lost beacon. Measured, twice.
                Beacon.payload = json.loads(urllib.parse.unquote(m.group(1)))
            except Exception:
                Beacon.payload = None
            self.send_response(204)
            self.end_headers()
            return
        route = self.path.split('?')[0]
        for prefix, root in (('/panel/', os.path.join(REPO, 'app', 'panel')),
                             ('/probe/', HERE),
                             ('/arm/', OUTDIR)):
            if route.startswith(prefix):
                rel = route[len(prefix):].replace('/', os.sep)
                path = os.path.normpath(os.path.join(root, rel))
                if not path.startswith(os.path.normpath(root)):
                    break
                if os.path.isfile(path):
                    ctype = ('text/css' if path.endswith('.css') else
                             'text/javascript' if path.endswith('.js') else
                             'font/woff2' if path.endswith('.woff2') else
                             'text/html')
                    with open(path, 'rb') as fh:
                        body = fh.read()
                    self.send_response(200)
                    self.send_header('Content-Type', ctype + '; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *a):  # silence the per-request stderr line
        return


def build_copy(arm):
    """The arm's copy of `panel.html`, with the panel's assets served, not linked.

    The ONLY difference from the shipped document is the stub bridge and this
    lane's probe: the CSP is untouched (the beacon is same-origin), and every
    other byte is the file the app loads.
    """
    with open(os.path.join(PANEL, 'panel.html'), encoding='utf-8') as fh:
        src = fh.read()
    for asset in ASSETS:
        if '"%s"' % asset not in src:
            raise SystemExit('panel.html no longer references %r' % asset)
        src = src.replace('"%s"' % asset, '"/panel/%s"' % asset)
    marker = '<script src="/panel/surface.js"></script>'
    assert marker in src, 'surface.js tag not found'
    src = src.replace(marker, '<script src="/arm/stub.js"></script>\n    ' + marker)
    marker = '<script src="/panel/panel.js"></script>'
    assert marker in src, 'panel.js tag not found'
    src = src.replace(marker, marker + '\n    <script src="/probe/_panel-anim-cost.js"></script>')
    out = os.path.join(OUTDIR, 'panel-cost-%s.html' % arm)
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(src)
    return out


def run_arm(browser, page, theme, arm, port, motion):
    """Launch one arm, wait for its beacon, and return the payload."""
    Beacon.payload = None
    prof = tempfile.mkdtemp(prefix='sotto-cost-%s-' % arm)
    url = ('http://127.0.0.1:%d/arm/%s#mode=cost&theme=%s&arm=%s&port=%d&seconds=%d&rate=%d'
           % (port, os.path.basename(page), theme, arm, port, SECONDS, RATE_HZ))
    cmd = [browser, '--headless=new', '--disable-gpu', '--no-first-run',
           '--disable-background-timer-throttling',
           '--disable-renderer-backgrounding',
           '--user-data-dir=' + prof, url]
    if motion:
        cmd.insert(1, '--blink-settings=prefersReducedMotion=false')
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid = proc.pid
    deadline = time.time() + SECONDS + 45
    try:
        while time.time() < deadline and Beacon.payload is None:
            time.sleep(0.2)
    finally:
        # ÔöÇÔöÇ THE KILL NAMES THE ARTIFACT AND THE EXACT PID ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        # `taskkill /PID <the pid Popen gave me>` rooted at the process THIS
        # script started, `/T` for its own children. No text filter anywhere: a
        # filter on the word `msedge` would take the owner's browser with it.
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(prof, ignore_errors=True)
    return Beacon.payload


def delta(a, b, path):
    """`a - b` for a dotted path, or None when either side is missing."""
    x = a
    y = b
    for key in path:
        x = (x or {}).get(key)
        y = (y or {}).get(key)
    if x is None or y is None:
        return None
    try:
        return float(x) - float(y)
    except (TypeError, ValueError):
        return None


def violations(cand, base):
    out = []
    for path, limit in LIMITS.items():
        d = delta(cand, base, path)
        if d is None:
            out.append(('%s.%s' % path, None, limit))
        elif d > limit:
            out.append(('%s.%s' % path, round(d, 3), limit))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--browser', default='edge', choices=('edge', 'chrome'))
    ap.add_argument('--themes', default='theme-5,theme-2',
                    help='the two directions that actually animate (inst, bcast)')
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()

    browser = find_browser(args.browser)
    os.makedirs(OUTDIR, exist_ok=True)

    srv = HTTPServer(('127.0.0.1', 0), Beacon)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    pages = {a: build_copy(a) for a in ('reduced', 'on', 'relayout')}
    print('arm copies:')
    for a, p in pages.items():
        print('   %-9s %s' % (a, p))
    print('beacon: http://127.0.0.1:%d/  (one thread; the arm script is the other)' % port)
    print('stream: %d s at %d partials/s, into the REAL panel.js' % (SECONDS, RATE_HZ))

    results = {}
    all_ok = True
    for theme in [t.strip() for t in args.themes.split(',') if t.strip()]:
        print()
        print('=== %s ===' % theme)
        rows = {}
        for arm, motion in (('reduced', False), ('on', True), ('relayout', True)):
            payload = run_arm(browser, pages[arm], theme, arm, port, motion)
            if not payload:
                print('   %-9s NO BEACON ÔÇö the arm produced no measurement' % arm)
                all_ok = False
                continue
            rows[arm] = payload
            print('   %-9s reducedMotion=%-5s loaf=%s styleAndLayout=%s blocking=%s '
                  'frame.p50=%s p95=%s max=%s over50=%s push.mean=%s'
                  % (arm, payload.get('reducedMotion'), payload['loaf']['count'],
                     payload['loaf']['styleAndLayout'], payload['loaf']['blocking'],
                     (payload.get('frame') or {}).get('p50'),
                     (payload.get('frame') or {}).get('p95'),
                     (payload.get('frame') or {}).get('max'),
                     (payload.get('frame') or {}).get('over50'),
                     payload['push']['mean']))
            if not payload.get('loafSupported'):
                print('        NOTE: no long-animation-frame entries at all ÔÇö the '
                      'style/layout channel is empty for this arm')
        results[theme] = rows

        if 'reduced' in rows and 'on' in rows:
            v = violations(rows['on'], rows['reduced'])
            if v:
                all_ok = False
                print('   ANIMATION-ON vs OFF: FAIL ÔÇö the animation added:')
                for name, d, lim in v:
                    print('     - %s +%s (limit %s)' % (name, d, lim))
            else:
                print('   ANIMATION-ON vs OFF: PASS ÔÇö nothing the animation adds '
                      'exceeds the limits %r' % {('%s.%s' % k): v2 for k, v2 in LIMITS.items()})
        else:
            all_ok = False

        if 'on' in rows and 'relayout' in rows:
            v = violations(rows['relayout'], rows['on'])
            if v:
                print('   CONTROL (width-animated copy) vs ON: RED-as-expected ÔÇö the '
                      'same limits catch it:')
                for name, d, lim in v:
                    print('     - %s +%s (limit %s)' % (name, d, lim))
            else:
                all_ok = False
                print('   CONTROL (width-animated copy) vs ON: GREEN ÔÇö THAT IS A '
                      'FAILING CONTROL: the instrument cannot tell a relayout-forcing '
                      'animation from a compositor-only one, so its PASS means nothing')
        else:
            all_ok = False

    srv.shutdown()
    out = os.path.join(HERE, '_panel-anim-cost.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({'seconds': SECONDS, 'rateHz': RATE_HZ, 'limits': {
            '%s.%s' % k: v for k, v in LIMITS.items()}, 'results': results}, fh, indent=1)
    print()
    print('raw payloads: %s' % out)
    print('VERDICT: %s' % ('GREEN ÔÇö the chrome animations are compositor-only within the '
                           'measured limits, and the relayout control proves the '
                           'instrument can see the difference'
                           if all_ok else 'RED'))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
