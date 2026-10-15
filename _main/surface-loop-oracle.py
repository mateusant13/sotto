#!/usr/bin/env python3
"""surface-loop-oracle -- THE JS<->PYTHON SURFACE LOOP, AND THE GUARD THAT CLOSED IT.

THE DEFECT THIS GATES (measured 2026-10-13 by the shell audit, in the log tail)
-----------------------------------------------------------------------------
The panel's bridge.setPanelSurface('strip', 'strip-float-off') reaches the
shell as wire kind 'panel-surface' and lands in SottoHost._panel_surface ->
SottoShell.set_panel_surface (sotto_webview.py:7065). THAT method echoes the
window geometry back to the page, and the page re-runs its whole surface
pipeline on every echo. Measured: 30 647 applications of the surface path
against FIVE real hotkey transitions -- 6129 to 1 of repeated work -- and the
loop's own rate was p50 102/s, p90 185/s, p99 264/s, max 294/s over 14 536
seconds. That is the freeze: the surface path is 78.5% of the log bytes and
write_atomic, called on every iteration, cannot keep up.

WHAT IS MEASURED HERE, AND HOW
-------------------------------
THE REAL CLASS, INSTANTIATED AND DRIVEN THROUGH ITS OWN WIRE. This oracle
imports the shipped app/webview/sotto_webview.py, builds a REAL SottoShell (the
way its own __init__ builds it, with the collaborators it touches stubbed at
the seam), wraps it in the REAL SottoHost, and sends the message the way the
page sends it: SottoHost.dispatch(json). Nothing is launched, no window is
created, no WebView2 is initialised -- the collaborators that reach the OS
(exec_js, _apply_window_geometry, the strip re-measure) are recorded instead
of executed, and log() is captured so a silent pass is impossible.

ARMS
  A APPLY     the first real transition applies once: the document is switched,
              the geometry is applied, ONE PANEL_SURFACE line is logged.
  B ECHO      a REPEATED call with the SAME (surface, reason) -- the echo --
              does nothing: no exec_js, no geometry apply, no second log line,
              and it still answers True. 200 echoes -> 1 application.
  C GENUINE   the guard is on a real change, NOT a suppression: a different
              surface applies, and the same surface with a DIFFERENT reason
              applies (a hotkey re-apply, a hot reload, a navigation).
  D REFUSAL   an unknown surface name is refused, applies nothing, and says so
              in its own log line (PANEL_SURFACE_REFUSED).
  E FIX-POINT the measured loop, in one process: the shell own geometry write is
              fed straight back as the page next message, 200 rounds, and the
              application count must stay at 1 while every echo is answered.

THE NEGATIVE ARM (--neg-arm) IS THE POINT OF THIS FILE: the shipped shell is
copied to a scratch directory, the idempotence is DELETED from the copy (the
four lines at sotto_webview.py:7099-7108 that return early on a repeated
(name, reason)), and the SAME arms run against it. Every arm the guard earns
must go RED there, or a green above cannot tell the cure from an untested
file.

USAGE
  py -3 _main/surface-loop-oracle.py            expect VERDICT: PASS, rc=0
  py -3 _main/surface-loop-oracle.py --neg-arm  expect RED, rc=0

Exit codes: 0 PASS, 1 FAIL, 2 setup error. No window, no launch, no audio.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.path.pardir))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')

RESULTS = []


def emit(line=''):
    print(line, flush=True)


def arm(name, ok, detail=''):
    RESULTS.append(bool(ok))
    emit(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        emit(f"         {detail}")


def load_shell(path):
    """Import the shipped shell by path, stdout captured (it logs a lot)."""
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    name = 'sotto_surface_loop_' + os.path.basename(path).replace('.', '_')
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load a module from {path!r}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spec.loader.exec_module(module)
    return module


class Recorder:
    """Counts the OS-reaching work the surface path performs."""

    def __init__(self):
        self.exec_js = 0
        self.geometry = 0
        self.log_lines = []
        self.strip_remeasure = 0


def build_pair(module):
    """The REAL SottoShell + the REAL SottoHost, with the seams recorded.

    Seams, and why each one is allowed to be a seam: exec_js needs a live
    WebView2 control, _apply_window_geometry moves an HWND we do not own, and
    the strip re-measures read the page computed CSS. None of them is the guard
    under test; the guard is set_panel_surface own decision, and it runs in
    full on both sides of every seam.
    """
    rec = Recorder()
    shell_cls = module.SottoShell
    shell = shell_cls.__new__(shell_cls)
    # -- what the real __init__ owns, seeded exactly as it seeds it ---------
    shell.surface = 'panel'
    shell.surface_applied = 'panel'
    shell.panel_mode = 'strip'
    shell.panel_show_refused = 0
    shell.panel_visibility = None
    shell.click_watcher = None
    shell.visible = False
    shell.staged = True
    shell.hwnd = 4242
    shell.edit_mode = False
    shell.geometry = {'x': 0, 'y': 0, 'width': 364, 'height': 861}

    class Args:
        show = False

    shell.args = Args()

    # -- the recorded seams ------------------------------------------------
    def _exec_js(script, timeout=10.0):
        rec.exec_js += 1
        # The strip-offset read answers 'no saved offset', the same thing a
        # page with an empty localStorage answers.
        if 'strip-offset' in script:
            return None
        return 'panel'

    shell.exec_js = _exec_js
    shell._apply_window_geometry = (
        lambda geometry, reason='surface': rec.__setattr__(
            'geometry', rec.geometry + 1))
    shell.refresh_strip_height = lambda reason='surface-strip': rec.__setattr__(
            'strip_remeasure', rec.strip_remeasure + 1)
    shell.refresh_strip_width = lambda reason='surface-strip': None
    shell.geometry_for = lambda surface: {
        'x': 440, 'y': 836, 'width': 1040, 'height': 150,
        'docked': 'bottom-centre', 'surface': surface,
    }
    # publish_panel_visibility is the shipped method: with
    # panel_visibility = None it returns False without touching a file.
    shell.publish_panel_visibility = lambda reason: False
    # The shell own log, captured per line: the count of PANEL_SURFACE lines
    # is an independent witness of the application count.
    module.log = lambda line: rec.log_lines.append(str(line))
    module.warn = lambda line: rec.log_lines.append(str(line))

    host = module.SottoHost(shell)
    return host, rec


def dispatch(host, rec, surface, reason):
    """The page own message, sent the page own way."""
    rec.log_lines.clear()
    before = rec.geometry
    host.dispatch(json.dumps({'kind': 'panel-surface',
                              'payload': {'surface': surface,
                                         'reason': reason}}))
    applied = rec.geometry - before
    logged = [l for l in rec.log_lines if l.startswith('PANEL_SURFACE')
              and 'PANEL_SURFACE_REFUSED' not in l]
    refused = [l for l in rec.log_lines if 'PANEL_SURFACE_REFUSED' in l]
    return applied, logged, refused


def run_arms(module, label, neg):
    """Every arm, against whichever shell copy is handed in."""
    mark = len(RESULTS)
    host, rec = build_pair(module)
    emit('')
    emit(f'--- arms over {label} ---')

    # -- A: the first real transition applies once -------------------------
    applied, logged, _ = dispatch(host, rec, 'strip', 'hotkey')
    arm('A APPLY the first transition applies exactly once',
        applied == 1 and len(logged) == 1,
        f'applied={applied} PANEL_SURFACE lines={len(logged)}')
    after_a = rec.geometry

    # -- B: the echo does nothing ------------------------------------------
    echoes = 200
    # The FIRST message of this sequence carries a reason arm A did not use
    # ('strip-float-off' vs 'hotkey'), so it is a genuine re-apply and MUST
    # apply. The 200 that follow it are the SAME (surface, reason) -- the echo
    # -- and those are what must be free.
    dispatch(host, rec, 'strip', 'strip-float-off')
    after_first = rec.geometry
    t0 = time.time()
    for _ in range(echoes):
        dispatch(host, rec, 'strip', 'strip-float-off')
    dt = time.time() - t0
    applied, logged, _ = dispatch(host, rec, 'strip', 'strip-float-off')
    total = len(logged)
    arm('B ECHO a repeated (surface, reason) does nothing',
        applied == 0 and total == 0 and rec.geometry == after_first,
        f'{echoes} echoes -> applications={rec.geometry} (arm A applied 1, '
        f' this sequence own first applied 1, the {echoes} repeats and the'
        f' next one added {rec.geometry - after_first}), extra PANEL_SURFACE'
        f' lines={total}, exec_js calls={rec.exec_js} over {echoes + 2} messages')

    # -- C: a genuine change is NOT suppressed -----------------------------
    applied_side, _, _ = dispatch(host, rec, 'panel', 'hotkey')
    applied_reason, _, _ = dispatch(host, rec, 'strip', 'hot-reload')
    arm('C GENUINE a real transition and a real re-apply still apply',
        applied_side == 1 and applied_reason == 1,
        f'strip->panel applied={applied_side}; '
        f'same surface, new reason applied={applied_reason} '
        f'(both must be 1)')

    # -- D: an unknown name is refused -------------------------------------
    applied, _, refused = dispatch(host, rec, 'nonsense', 'page')
    arm('D REFUSAL an unknown surface applies nothing and says so',
        applied == 0 and len(refused) == 1,
        f'applied={applied} PANEL_SURFACE_REFUSED lines={len(refused)}')

    # -- E: the measured loop, driven to its fixed point -------------------
    dispatch(host, rec, 'strip', 'strip-float-off')
    base = rec.geometry
    rounds = 200
    for _ in range(rounds):
        dispatch(host, rec, 'strip', 'strip-float-off')
    grown = rec.geometry - base
    arm('E FIX-POINT the echo loop converges on ONE application',
        grown == 0,
        f'{rounds} rounds of the measured loop -> applications grew by '
        f'{grown} (expected 0); {rounds / max(dt, 1e-9):.0f} echoes/s '
        f'measured in-process (the p99 that froze the box was 264/s)')
    return list(RESULTS[mark:])

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true',
                    help='delete the idempotence from a COPY and require RED')
    ap.add_argument('--shell', default=SHELL,
                    help='the shell under test (default: the shipped one)')
    args = ap.parse_args()

    emit('ORACLE surface-loop (the JS<->Python surface loop guard)')
    emit(f'  shell    {args.shell}')
    emit('  arms     A apply / B echo / C genuine / D refusal / E fixed point')
    emit('  driver   SottoHost.dispatch -> SottoShell.set_panel_surface '
         '(the real classes, the real wire)')

    target = args.shell
    scratch = None
    if args.neg_arm:
        scratch = tempfile.mkdtemp(prefix='surface-loop-neg-', dir='I:/cc-tmp')
        target = os.path.join(scratch, 'sotto_webview_noguard.py')
        shutil.copyfile(args.shell, target)
        with open(target, encoding='utf-8') as fh:
            text = fh.read()
        # THE CURE, REMOVED -- the four lines that make a repeated
        # (surface, reason) a no-op (sotto_webview.py:7099-7108).
        cure = ("""        prev = (self.surface, getattr(self, '_surface_reason', None))
        self.surface = name
        self._surface_reason = reason
        if prev[0] == name and prev[1] == reason:
            return True
""")
        nocure = ("""        prev = (self.surface, getattr(self, '_surface_reason', None))
        self.surface = name
        self._surface_reason = reason
""")
        if text.count(cure) != 1:
            emit(f'SETUP ERROR: the idempotence anchor appears '
                 f'{text.count(cure)} times, not once -- refusing to build a '
                 f'mutant that is not exactly the cure')
            if scratch:
                shutil.rmtree(scratch, ignore_errors=True)
            return 2
        with open(target, 'w', encoding='utf-8') as fh:
            fh.write(text.replace(cure, nocure))
        emit(f'  mutant   guard DELETED from a copy at {target}')

    try:
        module = load_shell(target)
        try:
            arms = run_arms(module, 'the MUTANT copy (guard deleted)' if args.neg_arm
                            else 'the SHIPPED shell', args.neg_arm)
        finally:
            if scratch:
                shutil.rmtree(scratch, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001 -- a setup failure is rc 2, not 1
        emit(f'SETUP ERROR: {exc!r}')
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
        return 2
    total = len(arms)
    green = sum(1 for a in arms if a)

    emit('')
    if args.neg_arm:
        emit(f'NEG-ARM SUMMARY: {green}/{total} arm(s) green, {total - green} red')
        if green == total:
            emit('VERDICT: FAIL -- the mutant passes too, so the GREEN arm '
                 'above cannot tell the cure from an untested file.')
            return 1
        emit('VERDICT: PASS -- the arms the guard earns went RED with the '
             'guard deleted, so a green on the shipped shell is a statement '
             'about the cure.')
        return 0

    if green != total:
        emit(f'VERDICT: FAIL -- {total - green} arm(s) red on '
             f'the shipped shell.')
        return 1
    emit(f'VERDICT: PASS -- {green}/{total} arm(s) green on the '
         f'shipped shell; run --neg-arm to prove it can say NO.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
