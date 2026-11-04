#!/usr/bin/env python3
"""Run `_main/_anim-cost2.js` against the real panel, one ablation per launch.

WHAT THIS IS FOR (lane/goal-anim). The shipped runner
(`_main/_lane-profile-paint.py`) answers "animated vs still, one mean per arm".
That mean is not enough to cut the cost, because on this box it is dominated by a
single multi-hundred-millisecond block and it cannot name the animation that
caused it. This runner drives the ATTRIBUTION probe instead:

  * per-push samples with a warm-up stream, so p50 is a steady-state number and
    the start-up block is reported as `warmup` instead of being averaged in;
  * the browser's own `long-animation-frame` attribution (`scripts[]`);
  * a `getAnimations()` census, grouped per animation name and per element;
  * ONE ablation per launch (`--ablations`), applied as a CSSOM write in the page
    so the panel bytes stay the shipped ones. `none` is the control: an ablation
    whose numbers do not move against `none` is not a cost.

THE SERVED PAGE. Every relative `href`/`src` in `panel.html` is rewritten to
`/panel/<name>` and served from `app/panel/` itself, so the document under
measurement is the shipped one plus the probe tag — and nothing 404s. The
shipped runner rewrites only the names in its `ASSETS` list, which leaves
`themes/zipc-panels.css` (69 KB, linked at `panel.html:71`) unreachable from
`/arm/`; that is stated here because it is a difference between the two pages,
not a detail.

    python _main/_anim-cost2.py --ablations none,no-word-anim --repeat 2
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ARM_PATH = os.path.join(HERE, '_panel-anim-cost-arm.py')
OUT = os.path.join(HERE, '_anim-cost2.json')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

REL_ATTR = re.compile(r'(href|src)="(?!https?:|/|#|data:)([^"]+)"')


def load_arm():
    spec = importlib.util.spec_from_file_location('panel_anim_cost_arm', ARM_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_page(arm_mod, probe='_anim-cost2.js'):
    """`panel.html` with every relative asset served from `/panel/`, + the probe.

    The ONLY differences from the shipped document are the absolute asset paths
    and the one extra `<script>`. The CSP is untouched: the probe is a served
    same-origin file and the beacon is same-origin.
    """
    with open(os.path.join(arm_mod.PANEL, 'panel.html'), encoding='utf-8') as fh:
        src = fh.read()
    src, n = REL_ATTR.subn(lambda m: '%s="/panel/%s"' % (m.group(1), m.group(2)), src)
    # THE BRIDGE. `panel.js` reads `window.sotto` and dies silently without it, so
    # the arm installs the audit stub BEFORE `surface.js` — the same insertion
    # point, and the same stub, the shipped harness uses.
    marker = '<script src="/panel/surface.js"></script>'
    if marker not in src:
        raise SystemExit('panel.html no longer loads surface.js; the stub has no seat')
    src = src.replace(marker, '<script src="/arm/stub.js"></script>\n    ' + marker)
    marker = '<script src="/panel/panel.js"></script>'
    if marker not in src:
        raise SystemExit('panel.html no longer loads panel.js from the head of the file')
    src = src.replace(marker, marker + '\n    <script src="/probe/%s"></script>' % probe)
    out = os.path.join(arm_mod.OUTDIR, 'panel-attrib.html')
    os.makedirs(arm_mod.OUTDIR, exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(src)
    return out, n


def sweep_profile(prof):
    """Kill every process that names THIS run's profile dir, then delete it."""
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' } | "
          "ForEach-Object { $_.ProcessId.ToString() + '|' + [string]$_.CommandLine }")
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', ps],
                             capture_output=True, encoding='utf-8', errors='replace',
                             creationflags=0x08000000).stdout or ''
    except OSError:
        out = ''
    for line in out.splitlines():
        if '|' not in line:
            continue
        pid, cmd = line.split('|', 1)
        if prof.lower() not in cmd.lower():
            continue
        subprocess.run(['taskkill', '/F', '/PID', pid.strip()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(6):
        shutil.rmtree(prof, ignore_errors=True)
        if not os.path.isdir(prof):
            break
        time.sleep(0.5)


def run_one(arm_mod, browser, page, theme, motion, ablation, args, port):
    arm_mod.Beacon.payload = None
    prof = tempfile.mkdtemp(prefix='attrib-%s-' % ablation)
    url = ('http://127.0.0.1:%d/arm/%s#mode=attrib&theme=%s&arm=%s&abl=%s&port=%d'
           '&seconds=%d&rate=%d&warmup=%d&side=%s%s'
           % (port, os.path.basename(page), theme, 'on' if motion else 'reduced',
              ablation, port, args.seconds, args.rate, args.warmup,
              ablation, args.extra))
    cmd = [browser, '--headless=new', '--disable-gpu', '--no-first-run',
           '--disable-background-timer-throttling',
           '--disable-renderer-backgrounding',
           '--user-data-dir=' + prof]
    if args.browser_log:
        # A LOST BEACON NEEDS A CAUSE, not a shrug: the page's own console and
        # its uncaught errors go to a file instead of /dev/null.
        cmd += ['--enable-logging=stderr', '--v=0']
    cmd.append(url)
    if motion:
        cmd.insert(1, '--blink-settings=prefersReducedMotion=false')
    logfh = open(args.browser_log, 'w', encoding='utf-8', errors='replace') \
        if args.browser_log else open(os.devnull, 'w')
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=logfh, creationflags=subprocess.CREATE_NO_WINDOW)
    started = time.time()
    try:
        while time.time() - started < args.deadline and arm_mod.Beacon.payload is None:
            time.sleep(0.25)
        waited = round(time.time() - started, 1)
    finally:
        # The exact pid Popen gave us, `/T` for its own children, never a filter:
        # a filter on `chrome` would take the owner's browser with it.
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        # AND THE LEAVINGS. MEASURED 2026-11-01: `/T` on the launcher's pid left
        # FIVE finished arms alive and their profile dirs in `%TEMP%` (rmtree
        # cannot delete a locked dir), and the next arms' beacons were lost to the
        # CPU those processes held. The sweep below names THIS arm's own
        # `--user-data-dir` — a string no other run and no browser of the owner's
        # can carry — so it cannot reach anything that is not this measurement.
        logfh.close()
        sweep_profile(prof)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(prof, ignore_errors=True)
    payload = arm_mod.Beacon.payload
    if payload is not None:
        payload['_waited_s'] = waited
    return payload


def show(name, p):
    if p is None:
        print('  %-22s NO BEACON' % name)
        return
    push = p.get('push') or {}
    win = push.get('window') or {}
    warm = push.get('warmup') or {}
    loaf = p.get('loaf') or {}
    anim = p.get('animations') or {}
    dom = anim.get('dom') or {}
    print('  %-22s applied=%s decls=%s ins=%s' % (
        name, (p.get('ablation') or {}).get('name'), (p.get('ablation') or {}).get('decls'),
        (p.get('ablation') or {}).get('inserted')))
    print('      push  p50=%-6s p95=%-6s mean=%-6s max=%-7s over8=%-3s n=%s | warm p50=%-6s max=%s' % (
        win.get('p50'), win.get('p95'), win.get('mean'), win.get('max'),
        win.get('over8'), win.get('n'), warm.get('p50'), warm.get('max')))
    print('      loaf  count=%s dur=%s block=%s styleAndLayout=%s max=%s' % (
        loaf.get('count'), loaf.get('duration'), loaf.get('blocking'),
        loaf.get('styleAndLayout'), loaf.get('max')))
    print('      anims total=%s | wordSpans=%s inlineBlock=%s animated=%s rowsAnimated=%s' % (
        anim.get('total'), dom.get('wordSpans'), dom.get('wordsInlineBlock'),
        dom.get('wordsAnimated'), dom.get('rowsAnimated')))
    for g in (anim.get('groups') or [])[:5]:
        print('        %3dx %-22s @ %-42s %s %s' % (
            g.get('n'), g.get('name'), g.get('target'), g.get('dur'), g.get('states')))
    for e in (loaf.get('entries') or [])[:4]:
        print('      long frame t=%sms dur=%s block=%s' % (e.get('t'), e.get('dur'), e.get('block')))
        for s in (e.get('scripts') or [])[:4]:
            print('         %-24s %-18s %-8s dur=%-8s forcedLayout=%s' % (
                s.get('f') or '(anonymous)', s.get('url'), s.get('inv'), s.get('dur'), s.get('fsl')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--browser', default='chrome', choices=('edge', 'chrome'))
    ap.add_argument('--theme', default='theme-5')
    ap.add_argument('--ablations', default='none')
    ap.add_argument('--motion', default='on', choices=('on', 'reduced'))
    ap.add_argument('--seconds', type=int, default=6)
    ap.add_argument('--rate', type=int, default=8)
    ap.add_argument('--warmup', type=int, default=2500)
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--deadline', type=float, default=180.0)
    ap.add_argument('--probe', default='_anim-cost2.js',
                    help='the served probe under `_main/` to load after panel.js')
    ap.add_argument('--extra', default='', help='extra hash params, `&k=v&k=v`')
    ap.add_argument('--browser-log', default='',
                    help="write the browser's stderr (console + uncaught errors) here")
    ap.add_argument('--out', default='',
                    help='raw JSON here instead of `_main/_anim-cost2.json` (the '
                         'before/after arms of one page must not overwrite each other)')
    ap.add_argument('--panel', default='',
                    help='SOTTO_PANEL_DIR: measure a COPY of the panel (before/after)')
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass

    if args.panel:
        os.environ['SOTTO_PANEL_DIR'] = os.path.abspath(args.panel)
    arm_mod = load_arm()
    page, rewritten = build_page(arm_mod, args.probe)
    browser = CHROME if args.browser == 'chrome' else EDGE
    if not os.path.exists(browser):
        raise SystemExit('no browser at %r' % browser)
    srv = HTTPServer(('127.0.0.1', 0), arm_mod.Beacon)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print('page    : %s (%d relative assets rewritten to /panel/)' % (page, rewritten))
    print('browser : %s   theme=%s motion=%s window=%ss@%dHz warmup=%sms' % (
        browser, args.theme, args.motion, args.seconds, args.rate, args.warmup))

    results = {}
    for rep in range(args.repeat):
        for name in [a.strip() for a in args.ablations.split(',') if a.strip()]:
            key = name if args.repeat == 1 else '%s#%d' % (name, rep + 1)
            p = run_one(arm_mod, browser, page, args.theme, args.motion == 'on', name, args, port)
            show(key, p)
            results[key] = p
            if args.probe == '_anim-visual.js':
                tl = (p or {}).get('frames') or []
                print('      frames=%d  first=%s  last=%s' % (
                    len(tl), tl[0] if tl else None, tl[-1] if tl else None))
    out = os.path.abspath(args.out) if args.out else OUT
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({'theme': args.theme, 'motion': args.motion, 'seconds': args.seconds,
                   'rateHz': args.rate, 'warmupMs': args.warmup, 'results': results},
                  fh, indent=1)
    print('raw: %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
