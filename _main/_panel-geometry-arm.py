#!/usr/bin/env python3
"""Measure the REAL panel's arrangement at the shell's own 380x900, before/after.

WHY THIS EXISTS. The owner looked at the running panel and said *"o painel do alt c
nao ta estruturado certo ... parece que ta wip mesmo, inves de terminado. o
layout."* Arrangement is a claim about GEOMETRY, so it needs an instrument that
publishes numbers, not an opinion: per block `x/y/w/h`, the DOM order, the
overlap area between laid-out blocks, and what leaves the panel's own box.

WHAT IT MEASURES, all from the LIVE document (`app/panel/panel.html`, `panel.css`,
`panel.js`, the five themes, served byte-for-byte):
  * `blocks`   — x/y/w/h + computed display/visibility + scrollHeight/clientHeight;
  * `order`    — the direct children of `.panel` in DOCUMENT order (the row
                 template is assigned in this order, which is why a markup move
                 is a layout move);
  * `overlaps` — pairwise intersection area between laid-out top-level blocks;
  * `clipped`  — blocks whose rect leaves the panel's content box, and blocks whose
                 content is taller than their box while the box cannot scroll.

THE FRAME. `--window-size=380,900` was measured NOT to set the viewport here
(`innerWidth=492`), so the arm runs in a 380x900 `<iframe>` and the probe asserts
`innerWidth === 380 && innerHeight === 900` from inside and reports both. A wrong
viewport is therefore a FAILURE in the payload, not a silent re-measurement.

THE CONTROLS (`--neg-arm`), both halves in ONE command, so the instrument has to
prove it can say NO:
  * `neg-order` — the DOM order reverted (the live box back ABOVE the transcript)
    while the row template is the new one: the order channel must go RED;
  * `neg-rows`  — the row template reverted to the old one while the DOM order is
    the new one, so the transcript takes the `1fr` row and the live box collapses:
    the height/flexible-row channel must go RED.

Usage:
  py -3 _main\\_panel-geometry-arm.py --label before
  py -3 _main\\_panel-geometry-arm.py --label after --neg-arm
  py -3 _main\\_panel-geometry-arm.py --compare before after
"""

import argparse
import json
import os
import re
import shutil
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

THEMES = ('theme-1', 'theme-2', 'theme-3', 'theme-4', 'theme-5')
# The owner's rule, as a machine-readable expectation.
LIVE_FLOOR = 140.0          # `.panel` grid's own floor on the live row
ROW_TEMPLATE_NEW = 'auto auto minmax(140px, 1fr) auto'
ROW_TEMPLATE_OLD = 'auto minmax(140px, 1fr) auto auto'


def find_browser(which):
    cands = CHROME_CANDIDATES if which == 'chrome' else EDGE_CANDIDATES
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit('no browser found in %r' % cands)


class Server(BaseHTTPRequestHandler):
    payload = None
    log = []
    err = None
    # ── WHY THIS TIMEOUT IS LOAD-BEARING ─────────────────────────────────────
    # `HTTPServer` is single-threaded on purpose (this lane's budget is <= 2
    # threads and the runner is the other one). A browser opens SPECULATIVE
    # sockets: it connects and sends nothing yet. The handler then blocks in
    # `handle_one_request` reading that silent socket, every other request queues
    # behind it, and the beacon — the ONLY way this arm reports — never arrives.
    # Measured: the same arm reported a payload twice and then reported
    # `NO BEACON` with an empty request log and no error anywhere. `timeout`
    # makes `socketserver` set a socket timeout, so an idle connection is dropped
    # and the server moves on. Still ONE thread.
    timeout = 2

    def do_GET(self):  # noqa: N802
        Server.log.append(self.path.split('?')[0])
        m = re.search(r'[?&]payload=([^&]*)', self.path)
        if m:
            try:
                Server.payload = json.loads(urllib.parse.unquote(m.group(1)))
            except Exception as exc:
                Server.err = '%s (raw %d chars)' % (exc, len(m.group(1)))
                Server.payload = None
            self.send_response(204)
            self.end_headers()
            return
        route = self.path.split('?')[0]
        for prefix, root in (('/panel/', PANEL), ('/probe/', HERE), ('/arm/', OUTDIR)):
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

    def log_message(self, *a):
        return


def _sections(src):
    """The `#captions` and `#history` `<section>` blocks, verbatim."""
    out = {}
    for key, marker in (('live', '<section class="captions" id="captions"'),
                        ('history', '<section class="history')):
        i = src.index(marker)
        j = src.index('</section>', i) + len('</section>')
        out[key] = src[i:j]
    return out


def build_copy(arm, control=None):
    """The arm's copy of `panel.html`; the ONLY differences are stated here."""
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
    src = src.replace(marker, marker + '\n    <script src="/probe/_panel-geometry.js"></script>')

    if control == 'neg-order':
        # THE ORDER REVERTED: the live box back ABOVE the transcript. The live
        # section is lifted out and put immediately BEFORE the transcript block,
        # which is the shipped order this lane inverted. (The first version of
        # this control re-inserted the block immediately AFTER the transcript —
        # i.e. exactly where it already was — so the control was a no-op and came
        # back GREEN. A control that does not change the subject is not a control.)
        sec = _sections(src)
        assert src.count(sec['live']) == 1 and src.count(sec['history']) == 1
        src = src.replace(sec['live'], '', 1)
        i = src.index(sec['history'])
        src = src[:i] + sec['live'] + '\n\n      ' + src[i:]
    elif control == 'neg-rows':
        # THE ROW TEMPLATE REVERTED while the DOM keeps the new order, so the
        # transcript takes the `1fr` and the live box collapses to its content.
        #
        # AS A LINKED FILE AND NOT AN INLINE `<style>`: the panel's own CSP is
        # `style-src 'self'`, so an inline style element is REFUSED and the control
        # is a silent no-op — measured, and it is why the first version of this
        # control came back GREEN. A same-origin stylesheet is what `'self'`
        # allows.
        css = os.path.join(OUTDIR, 'panel-geometry-neg-rows.css')
        with open(css, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('/* CONTROL COPY — the row template reverted to the shipped\n'
                     '   one while the markup keeps the new order. */\n'
                     '.panel { grid-template-rows: %s !important; }\n'
                     % ROW_TEMPLATE_OLD)
        marker = '<link rel="stylesheet" href="/panel/panel.css" />'
        assert marker in src, 'panel.css link not found for the neg-rows control'
        src = src.replace(
            marker, marker + '\n    <link rel="stylesheet" href="/arm/panel-geometry-neg-rows.css" />')

    out = os.path.join(OUTDIR, 'panel-geometry-%s.html' % arm)
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(src)
    return out


def build_frame(page_name, theme, state, port, arm, surface='', hold=False):
    out = os.path.join(OUTDIR, 'panel-geometry-frame.html')
    src = ('/arm/%s#theme=%s&state=%s&port=%d&arm=%s&surface=%s&hold=%s'
           % (page_name, theme, state, port, arm, surface, '1' if hold else ''))
    doc = """<!doctype html>
<html><head><meta charset="utf-8"><title>Sotto panel geometry frame</title>
<style>html,body{margin:0;padding:0;background:#000}
iframe{width:380px;height:900px;border:0;display:block}</style></head><body>
<iframe id="arm" src="%s"></iframe>
</body></html>""" % src
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(doc)
    return out


def run_arm(browser, page, theme, state, port, arm, direct=False, surface='',
            shot=None, hold=False):
    Server.payload = None
    Server.log = []
    Server.err = None
    prof = tempfile.mkdtemp(prefix='sotto-geom-')
    if direct:
        # DEBUG ONLY: no 380x900 frame, so `viewport.exact` is false by
        # construction and the judge refuses the arm. It exists to tell a broken
        # TRANSPORT apart from a broken PROBE.
        url = ('http://127.0.0.1:%d/arm/%s#theme=%s&state=%s&port=%d&arm=%s'
               '&surface=%s&hold=%s'
               % (port, page, theme, state, port, arm, surface, '1' if hold else ''))
    else:
        build_frame(page, theme, state, port, arm, surface, hold)
        url = 'http://127.0.0.1:%d/arm/panel-geometry-frame.html' % port

    cmd = [browser, '--headless=new', '--disable-gpu', '--no-first-run',
           '--disable-background-timer-throttling',
           '--disable-renderer-backgrounding',
           '--enable-logging=stderr', '--v=0',
           '--user-data-dir=' + prof]
    if shot:
        # ── A PICTURE OF THE PAINTED PANEL ────────────────────────────────────
        # `--virtual-time-budget` runs the page's own timers (the caption stream
        # this probe drives) as fast as it can and screenshots AFTER them, so the
        # frame shows committed AND forming lines rather than the empty state. The
        # window is larger than the 380x900 frame on purpose: `--window-size` does
        # not set the viewport on this box (measured: asking for 380 gave
        # `innerWidth=492`), so the frame is what fixes the size and the window
        # only has to be big enough not to crop it.
        cmd += ['--screenshot=' + shot, '--window-size=460,980',
                '--virtual-time-budget=9000', '--hide-scrollbars',
                '--force-device-scale-factor=2']
    cmd += [url]
    errlog = open(os.path.join(HERE, '_panel-geometry-browser.log'), 'wb')
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=errlog)
    pid = proc.pid
    deadline = time.time() + 60
    try:
        while time.time() < deadline and Server.payload is None:
            time.sleep(0.2)
    finally:
        # ── THE KILL NAMES THE ARTIFACT AND THE EXACT PID ──────────────────────
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        errlog.close()
        shutil.rmtree(prof, ignore_errors=True)
    if os.environ.get('SOTTO_GEOM_DEBUG'):
        print('   requests: %s' % (Server.log,))
        print('   beacon err: %s' % (Server.err,))
    return Server.payload


# --------------------------------------------------------------------------- #
# The judge. Every channel is a claim, and each one names what it saw.
# --------------------------------------------------------------------------- #
def judge(p):
    """Return (problems, facts) for one payload."""
    problems = []
    f = {}
    if p.get('crashed'):
        problems.append('THE PROBE CRASHED: %s at %s' % (p.get('message'), p.get('at')))
        return problems, {'crashed': True, 'message': p.get('message'), 'at': p.get('at')}
    vp = p.get('viewport') or {}
    if not vp.get('exact'):
        problems.append('viewport %sx%s (must be 380x900)' % (vp.get('innerWidth'), vp.get('innerHeight')))
    d = p.get('derived') or {}
    b = p.get('blocks') or {}

    f['order'] = ' > '.join([o for o in p.get('orderIds', []) if o not in ('<header>',)])
    f['liveBelowHistoryDom'] = d.get('historyAboveLiveDom')
    f['liveBelowHistoryY'] = d.get('historyAboveLiveY')
    f['liveH'] = d.get('liveHeight')
    f['liveBodyH'] = d.get('liveBodyHeight')
    f['historyH'] = d.get('historyHeight')
    f['flexible'] = d.get('flexibleBlock')
    f['liveRows'] = d.get('liveRows')
    f['expanded'] = d.get('historyExpanded')
    f['gap'] = d.get('gapHistoryToLive')
    f['overlaps'] = p.get('overlaps') or []
    f['clipped'] = p.get('clipped') or []
    f['cutInside'] = p.get('cutInside') or []
    f['stripVar'] = p.get('stripVar')
    f['controls'] = d.get('controlsInHeader')

    # ── THE STRIP SURFACE makes DIFFERENT claims, so it gets its own judge. The
    # owner's rule about the transcript does not apply there: the strip has no
    # transcript and no header by construction. What must hold is that the LIVE
    # box takes the height, the strip's own control row is present, and nothing
    # overlaps or is cut.
    if p.get('surfaceRequested') == 'strip':
        if b.get('stripbar', {}).get('display') == 'none':
            problems.append('the strip surface does not show its own control row')
        if b.get('header', {}).get('display') != 'none':
            problems.append('the header is not hidden on the strip surface')
        if b.get('history', {}).get('display') != 'none':
            problems.append('the transcript is not hidden on the strip surface')
        if d.get('flexibleBlock') != 'live':
            problems.append('the flexible row is %r, not the live box'
                            % d.get('flexibleBlock'))
        if (d.get('liveHeight') or 0) < 72.0 - 0.5:
            problems.append('live box height %s < the strip\'s own 72px floor'
                            % d.get('liveHeight'))
        if f['overlaps']:
            problems.append('%d overlapping block pair(s): %s'
                            % (len(f['overlaps']), f['overlaps']))
        if f['clipped']:
            problems.append('%d block(s) leave the panel box: %s'
                            % (len(f['clipped']), [c['block'] for c in f['clipped']]))
        if f['cutInside']:
            problems.append('content cut inside: %s' % f['cutInside'])
        if not f['stripVar']:
            problems.append('--strip-height is not exposed on :root')
        # THE NAME ON THE STRIP (owner: *"bota o nome 'sotto' em todos os temas"*,
        # and the strip is one of the two surfaces). The strip hides the header, so
        # this is the only place the name can live there.
        br = p.get('brand') or {}
        if br.get('stripCount') != 1:
            problems.append('the strip does not paint the name exactly once: count=%s '
                            'text=%r' % (br.get('stripCount'), br.get('stripText')))
        if br.get('carrierTransform') not in (None, 'none'):
            problems.append('the strip name is being transformed (%s) — it must stay '
                            'lowercase' % br.get('carrierTransform'))
        return problems, f

    # 1. THE OWNER'S RULE: live BELOW, history ABOVE — in the DOM and on the y axis.
    if d.get('historyAboveLiveDom') is not True:
        problems.append('DOM order: the live box is NOT below the transcript')
    if d.get('historyAboveLiveY') is not True:
        problems.append('geometry: the transcript is NOT above the live box on y')
    # 2. THE PRODUCT KEEPS THE HEIGHT: the live row is the flexible one and holds
    #    its own floor.
    if d.get('flexibleBlock') != 'live':
        problems.append('the flexible row is %r, not the live box' % d.get('flexibleBlock'))
    if (d.get('liveHeight') or 0) < LIVE_FLOOR - 0.5:
        problems.append('live box height %s < its own %s floor'
                        % (d.get('liveHeight'), LIVE_FLOOR))
    # 3. NOTHING OVERLAPS, NOTHING IS CUT.
    if f['overlaps']:
        problems.append('%d overlapping block pair(s): %s'
                        % (len(f['overlaps']), f['overlaps']))
    if f['clipped']:
        problems.append('%d block(s) leave the panel box: %s'
                        % (len(f['clipped']), [c['block'] for c in f['clipped']]))
    if f['cutInside']:
        problems.append('content cut inside: %s' % f['cutInside'])
    # 4. ALL CONTROLS ON THE TOP ROW.
    c = f['controls']
    if not c or not c.get('insideHeader') or not c.get('onHeaderRow'):
        problems.append('the control cluster is not on the header row: %r' % (c,))
    # 5. THE STRIP'S HEIGHT IS A NUMBER THE SHELL CAN SET.
    if not f['stripVar']:
        problems.append('--strip-height is not exposed on :root')

    # ── THE OWNER'S ITEM 1, AS A CLAIM ABOUT THE SCREEN ────────────────────────
    # "o numero a esquerda … nao é pra ter mais ele" — the row ordinal must not be
    # PAINTED, on any row. And the pair is the proof: the CLOCK must still be
    # there, with the live row's colour differing from the closed row's, because
    # "I removed the index" is worth nothing if the clock went with it.
    paint = p.get('paint') or {}
    if paint:
        if paint.get('indexElements'):
            problems.append('the row ordinal is STILL PAINTED: %d element(s), texts=%s'
                            % (paint['indexElements'], paint.get('indexTexts')))
        if (paint.get('rows') or 0) < 2:
            problems.append('only %s caption row(s) painted — the clock claim cannot '
                            'be tested' % paint.get('rows'))
        elif (paint.get('timeElements') or 0) < 2:
            problems.append('the CLOCK is missing: %d of %s row(s) carry a time'
                            % (paint.get('timeElements'), paint.get('rows')))
        if paint.get('liveRowTimeColor') and paint.get('closedRowTimeColor') \
                and paint['liveRowTimeColor'] == paint['closedRowTimeColor']:
            problems.append('the live row\'s clock is the SAME colour as the closed '
                            'rows\' (%s) — the owner\'s yellow/grey pair is gone'
                            % paint['liveRowTimeColor'])
        if paint.get('rows') and not any(paint.get('dataIndex') or []):
            problems.append('the ordinal did not survive as STATE: no row carries '
                            'data-index')

    # ── THE NAME `sotto` IN EVERY THEME, COUNTED IN THE PAINTED DOM ────────────
    # The owner asked for it in all five and on both surfaces. A screenshot shows
    # one theme; this shows the count. PAINTED means rendered — the four hidden
    # chrome blocks hold their own text and must not be counted.
    brand = p.get('brand') or {}
    if brand:
        if brand.get('headerCount') != 1:
            problems.append('the header paints the name %s time(s), not once: text=%r'
                            % (brand.get('headerCount'), brand.get('headerText')))
        if brand.get('carrierTransform') not in (None, 'none'):
            problems.append('the name is being text-transformed (%s) — the owner '
                            'wrote it lowercase' % brand.get('carrierTransform'))
        if brand.get('carrier') and 'sotto' not in (brand.get('carrier') or ''):
            problems.append('the carrier element does not hold the lowercase name: %r'
                            % brand.get('carrier'))
    return problems, f


def fmt_blocks(p):
    rows = []
    for name in ('header', 'controls', 'live', 'liveBar', 'liveBody', 'liveList',
                 'stripbar', 'history', 'historyBar', 'historyBody', 'status',
                 'statusText', 'placeholder'):
        b = (p.get('blocks') or {}).get(name)
        if not b or b.get('missing'):
            rows.append('   %-12s MISSING' % name)
            continue
        r = b['rect']
        rows.append('   %-12s x=%-6s y=%-6s w=%-6s h=%-6s display=%-6s%s%s'
                    % (name, r['x'], r['y'], r['w'], r['h'], b['display'],
                       ' hidden' if b.get('hiddenAttr') else '',
                       ' SCROLLS' if b.get('scrolls') else
                       (' CUT' if b.get('cutInside') else '')))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--browser', default='edge', choices=('edge', 'chrome'))
    ap.add_argument('--label', default='run')
    ap.add_argument('--themes', default=','.join(THEMES))
    ap.add_argument('--state', default='live,expanded')
    ap.add_argument('--surface', default='', help='panel (default) or strip')
    ap.add_argument('--shot', default='', help='write a PNG of the painted panel')
    ap.add_argument('--shot-theme', default='theme-2',
                    help='which theme the screenshot arm uses')
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--direct', action='store_true',
                    help='DEBUG ONLY: no 380x900 frame (the judge will refuse the arm)')
    ap.add_argument('--compare', nargs=2, metavar=('BEFORE', 'AFTER'))
    args = ap.parse_args()

    if args.compare:
        return compare(*args.compare)

    browser = find_browser(args.browser)
    os.makedirs(OUTDIR, exist_ok=True)
    srv = HTTPServer(('127.0.0.1', 0), Server)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    arms = [('real', None)]
    if args.neg_arm:
        arms += [('neg-order', 'neg-order'), ('neg-rows', 'neg-rows')]

    themes = [t.strip() for t in args.themes.split(',') if t.strip()]
    states = [s.strip() for s in args.state.split(',') if s.strip()]

    if args.shot:
        # ── ONE ARM, ONE PICTURE ───────────────────────────────────────────────
        # The screenshot is the owner's own evidence, so it is taken on the SAME
        # document the numbers come from: the real copy, the real theme, the real
        # caption stream, 380x900 inside the frame.
        page = os.path.basename(build_copy('real', None))
        shot = os.path.abspath(args.shot)
        p = run_arm(browser, page, args.shot_theme, 'live', port, 'real',
                    False, args.surface, shot, hold=True)
        srv.shutdown()
        if not p:
            print('NO BEACON')
            return 1
        problems, facts = judge(p)
        paint = p.get('paint') or {}
        print('shot      : %s' % shot)
        print('exists    : %s' % os.path.exists(shot))
        print('theme     : %s' % args.shot_theme)
        print('paint     : rows=%(rows)s indexElements=%(indexElements)s '
              'timeElements=%(timeElements)s' % paint)
        print('            liveTimeColor=%s closedTimeColor=%s'
              % (paint.get('liveRowTimeColor'), paint.get('closedRowTimeColor')))
        print('            liveRail=%s' % (paint.get('liveRowHasLeftRail'),))
        print('            timeTexts=%s' % (paint.get('timeTexts'),))
        print('            timeColors=%s' % (paint.get('timeColors'),))
        print('            lastRowClass=%s' % (paint.get('lastRowClass'),))
        print('            lastRowTimeColor=%s lastRowRail=%s'
              % (paint.get('lastRowTimeColor'), paint.get('lastRowRail')))
        print('            dataIndex=%s' % (paint.get('dataIndex'),))
        print('            rowTextSample=%s' % (paint.get('rowTextSample'),))
        print('geometry  : %s' % ('GREEN' if not problems else 'RED'))
        for pr in problems:
            print('      - %s' % pr)
        return 0

    results = {}
    reds = []
    for arm, control in arms:
        page = os.path.basename(build_copy(arm, control))
        # The neg arms exist to be caught; measure them on one theme, one state.
        arm_themes = themes if arm == 'real' else themes[:1]
        arm_states = states if arm == 'real' else states[:1]
        for theme in arm_themes:
            for state in arm_states:
                key = '%s|%s|%s%s' % (arm, theme, state,
                                      ('|' + args.surface) if args.surface else '')
                p = run_arm(browser, page, theme, state, port, arm, args.direct,
                            args.surface)
                if not p:
                    print('%-24s NO BEACON' % key)
                    reds.append(key)
                    continue
                problems, facts = judge(p)
                results[key] = {'payload': p, 'problems': problems, 'facts': facts}
                if arm == 'real':
                    verdict = 'GREEN' if not problems else 'RED'
                    print('%-24s %-5s order=[%s] liveH=%-6s histH=%-6s flex=%-6s '
                          'overlaps=%d clipped=%d cut=%d'
                          % (key, verdict, facts['order'], facts['liveH'],
                             facts['historyH'], facts['flexible'],
                             len(facts['overlaps']), len(facts['clipped']),
                             len(facts['cutInside'])))
                    for pr in problems:
                        print('      - %s' % pr)
                else:
                    verdict = 'RED-as-expected' if problems else 'GREEN — FAILING CONTROL'
                    if not problems:
                        reds.append(key)
                    print('%-24s %s' % (key, verdict))
                    for pr in problems:
                        print('      - %s' % pr)

    out = os.path.join(HERE, '_panel-geometry-%s.json' % args.label)
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({'label': args.label, 'results': results}, fh, indent=1)
    print()
    print('raw payloads: %s' % out)

    # The real arm's own table, for the receipt.
    for key, r in results.items():
        if not key.startswith('real|'):
            continue
        print()
        print('--- %s ---' % key)
        for line in fmt_blocks(r['payload']):
            print(line)
        print('   orderIds=%s' % (r['payload'].get('orderIds'),))
        print('   derived=%s' % json.dumps(r['facts'], default=str))

    srv.shutdown()
    ok = not reds and all(not r['problems'] for k, r in results.items() if k.startswith('real|'))
    print()
    print('VERDICT: %s' % ('GREEN' if ok else 'RED'))
    return 0 if ok else 1


def compare(before_label, after_label):
    """The before/after table, block by block, from the two saved payloads."""
    def load(label):
        path = os.path.join(HERE, '_panel-geometry-%s.json' % label)
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)['results']

    a = load(before_label)
    b = load(after_label)
    names = ('header', 'controls', 'live', 'liveBody', 'liveList', 'history',
             'historyBody', 'status', 'stripbar')
    for key in sorted(set(a) | set(b)):
        pa = (a.get(key) or {}).get('payload')
        pb = (b.get(key) or {}).get('payload')
        if not pa or not pb:
            print('%-24s MISSING on one side' % key)
            continue
        print('=== %s ===' % key)
        print('   %-12s %-28s %-28s' % ('block', 'BEFORE  x,y  wxh', 'AFTER  x,y  wxh'))
        for n in names:
            ba = (pa.get('blocks') or {}).get(n) or {}
            bb = (pb.get('blocks') or {}).get(n) or {}
            ra = ba.get('rect') or {}
            rb = bb.get('rect') or {}
            fa = '%s,%s  %sx%s' % (ra.get('x'), ra.get('y'), ra.get('w'), ra.get('h'))
            fb = '%s,%s  %sx%s' % (rb.get('x'), rb.get('y'), rb.get('w'), rb.get('h'))
            mark = '' if fa == fb else '   <- moved'
            print('   %-12s %-28s %-28s%s' % (n, fa, fb, mark))
        da = pa.get('derived') or {}
        db = pb.get('derived') or {}
        print('   order      BEFORE %s' % (pa.get('orderIds'),))
        print('              AFTER  %s' % (pb.get('orderIds'),))
        print('   liveBelowHistory  BEFORE dom=%s y=%s   AFTER dom=%s y=%s'
              % (da.get('historyAboveLiveDom'), da.get('historyAboveLiveY'),
                 db.get('historyAboveLiveDom'), db.get('historyAboveLiveY')))
        print('   liveH      BEFORE %s   AFTER %s' % (da.get('liveHeight'), db.get('liveHeight')))
        print('   historyH   BEFORE %s   AFTER %s' % (da.get('historyHeight'), db.get('historyHeight')))
        print('   flexible   BEFORE %s   AFTER %s' % (da.get('flexibleBlock'), db.get('flexibleBlock')))
        print('   overlaps   BEFORE %s   AFTER %s'
              % (len(pa.get('overlaps') or []), len(pb.get('overlaps') or [])))
        print('   clipped    BEFORE %s   AFTER %s'
              % (len(pa.get('clipped') or []), len(pb.get('clipped') or [])))
        print('   cutInside  BEFORE %s   AFTER %s'
              % (pa.get('cutInside'), pb.get('cutInside')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
