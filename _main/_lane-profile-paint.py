#!/usr/bin/env python3
"""LANE-PROFILE PAINT -- the panel's own cost per caption, on THIS box, today.

WHAT THIS FILE IS, AND WHAT IT IS NOT. It invents no measurement: the arms, the
served page, the stub bridge, the probe (`_main/_panel-anim-cost.js`), the arm
copies and the beacon are the ones `_main/_panel-anim-cost-arm.py` already
shipped, imported VERBATIM. What it changes is ONE number -- the wall clock a
headless Chromium is given -- because that number, on this box, is no longer
true.

MEASURED 2026-11-01 10:00, the reason this wrapper exists:

    chrome --headless=new --dump-dom "data:text/html,<h1>hello</h1>"   -> 100.96 s

A data: URL with one element. `_panel-anim-cost-arm.py:233` gives every arm
`SECONDS + 45` = 51 s, so on this machine all three arms reported `NO BEACON`
(measured twice, edge and chrome) and the harness called it RED. The harness was
not wrong about the panel; it was starved of the clock. So this runner keeps the
harness's threshold set and its own control arm, and waits up to `--deadline`.

ARMS: `reduced` is the box as the owner has it (Windows animations off, which is
what `prefers-reduced-motion` reports here); `relayout` is the harness's own
CONTROL, the same elements animated on a property that forces a relayout. If the
control does not measure worse than the real arm, the instrument is not
resolving anything and this file says so instead of printing a green.

    python _main\\_lane-profile-paint.py --themes theme-5 --deadline 300
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ARM_PATH = os.path.join(HERE, '_panel-anim-cost-arm.py')
OUT = os.path.join(HERE, '_lane-profile-paint.json')

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

#: The panel scripts the served page asks for with a RELATIVE name, so they must
#: exist in the arm's out dir. `build_copy` rewrites only `ASSETS` (the quoted
#: ones) to `/panel/`; everything else resolves to `/arm/<name>` and 404s in a
#: fresh worktree, which kills `panel.js` at load -- MEASURED 2026-11-01 as
#: `Uncaught ReferenceError: StableWords is not defined` at panel.js:992, after
#: which no beacon can ever arrive. `_audit-render/` is populated by
#: `_main/_audit-render/make-harness.py` in the tree that has been used before;
#: a NEW worktree needs this copy, so the runner does it itself.
ARM_ASSETS = (
    'stable-words.js', 'letter-swap.js', 'caption-float.js', 'strip-drag.js',
    'brand-bridge.js', 'theme-tune.js', 'history-gallery.js',
    'caption-float.css', 'button-contract.css', 'hotkey-hold.css',
    os.path.join('themes', 'zipc-panels.js'),
    os.path.join('themes', 'panel-designs.js'),
)


def populate_arm_assets(arm_mod):
    """Copy the page's relative assets into the arm dir -- only the MISSING ones."""
    for rel in ARM_ASSETS:
        dst = os.path.join(arm_mod.OUTDIR, rel)
        if os.path.isfile(dst):
            continue
        src = os.path.join(arm_mod.PANEL, rel)
        if not os.path.isfile(src):
            print('  WARN missing in the app too: %s' % rel)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        print('  populated %s' % rel)


def load_arm():
    spec = importlib.util.spec_from_file_location('panel_anim_cost_arm', ARM_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_arm(arm_mod, browser, arm, theme, port, motion, deadline_s):
    """One arm: launch, wait for ITS beacon, kill by the pid this process owns."""
    arm_mod.Beacon.payload = None
    prof = tempfile.mkdtemp(prefix='profile-cost-%s-' % arm)
    page = arm_mod.build_copy(arm)
    url = ('http://127.0.0.1:%d/arm/%s#mode=cost&theme=%s&arm=%s&port=%d&seconds=%d&rate=%d'
           % (port, os.path.basename(page), theme, arm, port,
              arm_mod.SECONDS, arm_mod.RATE_HZ))
    cmd = [browser, '--headless=new', '--disable-gpu', '--no-first-run',
           '--disable-background-timer-throttling',
           '--disable-renderer-backgrounding',
           '--user-data-dir=' + prof, url]
    if motion:
        cmd.insert(1, '--blink-settings=prefersReducedMotion=false')
    started = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        while time.time() - started < deadline_s and arm_mod.Beacon.payload is None:
            time.sleep(0.25)
        waited = round(time.time() - started, 1)
    finally:
        # The kill names the EXACT pid Popen gave me, never a text filter: a
        # filter on `chrome` would take the owner's own browser with it.
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(prof, ignore_errors=True)
    payload = arm_mod.Beacon.payload
    if payload is not None:
        payload['_waited_s'] = waited
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--browser', default='chrome', choices=('edge', 'chrome'))
    ap.add_argument('--themes', default='theme-5')
    ap.add_argument('--arms', default='reduced,relayout')
    ap.add_argument('--deadline', type=float, default=300.0,
                    help='wall-clock budget per arm (the shipped arm uses 51 s)')
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass

    arm_mod = load_arm()
    os.makedirs(arm_mod.OUTDIR, exist_ok=True)
    populate_arm_assets(arm_mod)
    browser = CHROME if args.browser == 'chrome' else EDGE
    if not os.path.exists(browser):
        raise SystemExit('no browser at %r' % browser)
    srv = HTTPServer(('127.0.0.1', 0), arm_mod.Beacon)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print('browser : %s' % browser)
    print('beacon  : http://127.0.0.1:%d/   deadline/arm: %.0f s' % (port, args.deadline))
    print('stream  : %d s at %d partials/s into the REAL panel.js (shipped bytes)'
          % (arm_mod.SECONDS, arm_mod.RATE_HZ))

    results = {}
    for theme in [t.strip() for t in args.themes.split(',') if t.strip()]:
        rows = {}
        for arm in [a.strip() for a in args.arms.split(',') if a.strip()]:
            motion = arm != 'reduced'
            payload = run_arm(arm_mod, browser, arm, theme, port, motion, args.deadline)
            if payload is None:
                print('  %-9s NO BEACON inside %.0f s' % (arm, args.deadline))
                continue
            rows[arm] = payload
            frame = payload.get('frame') or {}
            loaf = payload.get('loaf') or {}
            push = payload.get('push') or {}
            print('  %-9s waited=%5.1fs windowMs=%s reducedMotion=%s' % (
                arm, payload['_waited_s'], payload.get('windowMs'), payload.get('reducedMotion')))
            print('            push  mean=%s p50=%s p95=%s max=%s n=%s' % (
                push.get('mean'), push.get('p50'), push.get('p95'), push.get('max'), push.get('count')))
            print('            frame p50=%s p95=%s max=%s over50=%s n=%s' % (
                frame.get('p50'), frame.get('p95'), frame.get('max'),
                frame.get('over50'), frame.get('n')))
            print('            loaf  count=%s duration=%s blocking=%s styleAndLayout=%s' % (
                loaf.get('count'), loaf.get('duration'), loaf.get('blocking'),
                loaf.get('styleAndLayout')))
        results[theme] = rows

    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump({'seconds': arm_mod.SECONDS, 'rateHz': arm_mod.RATE_HZ,
                   'deadline_s': args.deadline, 'results': results}, fh, indent=1)

    # THE CONTROL GATE: a `relayout` arm that does NOT cost measurably more than
    # `reduced` means the channel is not resolving, so its green means nothing.
    verdict = 'UNKNOWN'
    for theme, rows in results.items():
        red, rel = rows.get('reduced'), rows.get('relayout')
        if not red or not rel:
            verdict = 'INCOMPLETE'
            print('%s: INCOMPLETE - one arm produced no measurement' % theme)
            continue
        d = lambda a, b: (b or 0) - (a or 0)  # noqa: E731
        dpush = d((red.get('push') or {}).get('mean'), (rel.get('push') or {}).get('mean'))
        dstyle = d((red.get('loaf') or {}).get('styleAndLayout'),
                   (rel.get('loaf') or {}).get('styleAndLayout'))
        print('%s: control delta push.mean=%+.3f ms  loaf.styleAndLayout=%+.3f ms'
              % (theme, dpush, dstyle))
        verdict = 'CONTROL-MOVES' if (dpush > 0.05 or dstyle > 1.0) else 'CONTROL-FLAT'
        print('%s: %s' % (theme, verdict))
    print('raw: %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
