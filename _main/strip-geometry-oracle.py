#!/usr/bin/env python3
"""THE STRIP WINDOW GEOMETRY, AND THE Alt+C DOUBLE -- both colours in one run.

Two owner reports, both measured 2026-10-12, both from his own words:

  *"eu to vendo div com cor solida inves de invisivel"*
      The strip WINDOW was STRIP_WIDTH = 1040 wide while
      body[data-surface="strip"] .panel is width: max-content -- a small pill.
      The shell paints every pixel the page does not with the form opaque
      #0B0F14, so a 1040-wide window holding a ~400px pill IS a solid colour
      slab with the real bottom panel in the middle of it. The width must come
      from the CONTENT, exactly as the height already did.

  *"o alt c apertado 2x nao ta abrindo o painel da direita"*
      The double branch made a double on a HIDDEN panel a no-op. A stale
      _last_hotkey_press makes the owner FIRST press the double, so the pair was
      consumed doing nothing and his SECOND press landed as a single and only
      opened the strip. Two presses showed the strip and never the right panel.

NOTHING IS LAUNCHED. The real methods are called on a fake object; the module
is imported, never run as a program. --neg-arm loads COPIES with each fix
reverted and requires the matching arm to go RED.
"""
import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WORK = {'x': 0, 'y': 0, 'width': 1920, 'height': 1080}

RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append((label, bool(ok), str(detail)))
    print(('  ok   ' if ok else '  FAIL ') + label
          + ('  -- ' + str(detail) if detail else ''))


def load(path, name):
    # sotto_webview.py imports its siblings by bare name (hot_reload), so the
    # shell own directory has to be importable before it is loaded.
    here = os.path.dirname(os.path.abspath(path))
    if here not in sys.path:
        sys.path.insert(0, here)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeShell(object):
    """Just enough of the shell for the two methods under test."""

    def __init__(self, sw, saved=None, width_dom=420, height=100):
        self._sw = sw
        self._work = dict(WORK)
        self.saved_geometry = saved
        self.strip_height = height
        self.strip_width_dom = width_dom
        self.hwnd = 1
        self.panel_mode = 'strip'
        self._last_hotkey_press = 0.0
        self.calls = []

    def work_area(self):
        return dict(self._work)

    def strip_width_live(self):
        return self._sw.SottoShell.strip_width_live(self)

    def hide_panel(self, reason):
        self.calls.append(('hide', reason))
        return True

    def show_side(self, reason):
        self.calls.append(('side', reason))
        return True

    def show_strip(self, reason):
        self.calls.append(('strip', reason))
        return True

    def geometry_for(self, surface):
        return self._sw.SottoShell.geometry_for(self, surface)

    def hotkey_pressed(self):
        return self._sw.SottoShell.hotkey_pressed(self)


def strip_rect(width, x, y=966, height=100):
    return {'surface': 'strip', 'x': x, 'y': y, 'width': width,
            'height': height, 'workX': 0, 'workY': 0, 'workWidth': 1920,
            'workHeight': 1080, 'docked': 'bottom-strip'}


def run_arms(sw, tag):
    # A1 -- THE SOLID SLAB. A 1040-wide saved rect with a 420px pill must come
    # back as a 420-wide window, centred.
    f = FakeShell(sw, saved=strip_rect(1040, 440))
    g = f.geometry_for('strip')
    check(tag + 'A1 slab 1040 -> content 420', g.get('width') == 420,
          'width=%s' % g.get('width'))
    check(tag + 'A1b and it is re-centred',
          g.get('x') == round((1920 - 420) / 2), 'x=%s' % g.get('x'))

    # A2 -- A PLACEMENT THE OWNER MADE IS KEPT. 500 is neither the slab constant
    # nor 90% of the work area, so the x survives; only the width is the content.
    f = FakeShell(sw, saved=strip_rect(500, 100))
    g = f.geometry_for('strip')
    check(tag + 'A2 owner placement kept',
          g.get('x') == 100 and g.get('width') == 420,
          'x=%s width=%s' % (g.get('x'), g.get('width')))

    # A3 -- FLOATED: the caption is left:0/right:0 inside the window and needs
    # the room, so no content width is adopted and the wide dock stands.
    f = FakeShell(sw, saved=None, width_dom=None)
    g = f.geometry_for('strip')
    check(tag + 'A3 floated keeps the wide dock', g.get('width') == 1040,
          'width=%s' % g.get('width'))

    # A4 -- NO SAVED RECT AT ALL: a fresh install must not open a slab either.
    f = FakeShell(sw, saved=None, width_dom=420)
    g = f.geometry_for('strip')
    check(tag + 'A4 fresh install is not a slab', g.get('width') == 420,
          'width=%s' % g.get('width'))

    # B1/B2/B4 -- Alt+C. The owner contract: TWO PRESSES OPEN THE RIGHT PANEL.
    f = FakeShell(sw, width_dom=None)
    sw.window_visible = lambda hwnd: False
    f._last_hotkey_press = 0.0
    f.hotkey_pressed()
    check(tag + 'B1 single from hidden opens the strip',
          f.calls and f.calls[-1][0] == 'strip', str(f.calls))

    f = FakeShell(sw, width_dom=None)
    sw.window_visible = lambda hwnd: False
    f._last_hotkey_press = time.monotonic() - 0.10
    f.hotkey_pressed()
    check(tag + 'B2 double from HIDDEN opens the RIGHT panel',
          f.calls and f.calls[-1][0] == 'side', str(f.calls))

    f = FakeShell(sw, width_dom=None)
    sw.window_visible = lambda hwnd: True
    f.panel_mode = 'side'
    f._last_hotkey_press = time.monotonic() - 0.10
    f.hotkey_pressed()
    check(tag + 'B3 double while on SIDE still hides it',
          f.calls and f.calls[-1][0] == 'hide', str(f.calls))

    f = FakeShell(sw, width_dom=None)
    sw.window_visible = lambda hwnd: False
    f._last_hotkey_press = time.monotonic() - 5.0
    f.hotkey_pressed()
    check(tag + 'B4 two presses far apart are two singles',
          f.calls and f.calls[-1][0] == 'strip', str(f.calls))


MUTANTS = [
    # M1 -- the hotkey fix reverted: a double on a hidden panel is a no-op again.
    ('M1 hotkey-double-ignored',
     "                return self.show_side('hotkey-double')",
     "                return False",
     'B2 double from HIDDEN opens the RIGHT panel'),
    # M2 -- THE SAVED-RECT WIDTH CORRECTION removed. This is the arm that carries
    # the owner slab: without it a 1040-wide saved rect stays 1040. NOTE: the
    # first version of this mutant reverted the FALLBACK instead and was INERT
    # for A1 -- it changed nothing A1 could see, which is an ABSENT control.
    ('M2 saved-rect-width-not-content',
     '                if old_w != want_w:',
     '                if False:',
     'A1 slab 1040 -> content 420'),
    # M3 -- EVERY SAVED RECT IS TREATED AS A SLAB, so a placement the owner made
    # by hand is re-centred out from under him. NOTE: the mutant this replaces
    # reverted the FALLBACK dock width and was INERT, and not by accident -- the
    # fallback is only reached when strip_width_live() answers None, which is
    # exactly when there is no content width to pass. That path cannot carry a
    # width by construction, so no mutant on it can ever flip.
    ('M3 owner-placement-recentred',
     '                    slab = (old_w <= 0 or old_w == STRIP_WIDTH\n'
     '                            or old_w >= int(work_w * 0.9))',
     '                    slab = True',
     'A2 owner placement kept'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    sw = load(SHELL, 'sotto_shell_live')
    print('live shell %s  (%d B)' % (SHELL, os.path.getsize(SHELL)))
    print('-- control: the fixes as shipped --')
    run_arms(sw, '')
    control = list(RESULTS)

    if args.neg_arm:
        print('-- neg-arm: each fix reverted in a COPY --')
        tmp = tempfile.mkdtemp(prefix='sotto-strip-geom-')
        try:
            src = open(SHELL, 'r', encoding='utf-8').read()
            for label, old, new, arm in MUTANTS:
                if old not in src:
                    check('neg-arm %s anchor found' % label, False,
                          'anchor missing -- the mutant would be INERT')
                    continue
                path = os.path.join(tmp, label.replace(' ', '_') + '.py')
                open(path, 'w', encoding='utf-8').write(src.replace(old, new, 1))
                m = load(path, 'mut_' + label.replace('-', '_'))
                before = len(RESULTS)
                print('   mutant %s:' % label)
                run_arms(m, '  ')
                red = [r for r in RESULTS[before:] if not r[1]]
                matched = any(arm in r[0] for r in red)
                check('neg-arm %s goes RED on its own arm' % label, matched,
                      'red=%s' % [r[0].strip() for r in red])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    control_failed = [r for r in control if not r[1]]
    if args.neg_arm:
        # A mutant own arms MUST fail; what must not fail is the control and the
        # goes-RED checks. Counting the mutant failures as the verdict would make
        # a working control read as a broken gate.
        red_checks = [r for r in RESULTS
                      if r[0].startswith('neg-arm ') and 'goes RED' in r[0]]
        failed = control_failed + [r for r in red_checks if not r[1]]
        total = len(control) + len(red_checks)
    else:
        failed = control_failed
        total = len(control)
    print('')
    print('VERDICT: %s -- %d check(s), %d fail'
          % ('PASS' if not failed else 'FAIL', total, len(failed)))
    for r in failed:
        print('   FAILED: ' + r[0] + '  -- ' + r[2])
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
