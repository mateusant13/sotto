#!/usr/bin/env python3
"""THE STRIP WINDOW GEOMETRY, AND THE Alt+C CYCLE -- both colours in one run.

Two owner reports, both from his own words:

  *"eu to vendo div com cor solida inves de invisivel"*   (2026-10-12)
      The strip WINDOW was STRIP_WIDTH = 1040 wide while
      body[data-surface="strip"] .panel is width: max-content -- a small pill.
      The shell paints every pixel the page does not with the form opaque
      #0B0F14, so a 1040-wide window holding a ~400px pill IS a solid colour
      slab with the real bottom panel in the middle of it. The width must come
      from the CONTENT, exactly as the height already did.

  *"o alt c ta meio ruim. quando o segundo painel aparece, o proximo alt c deve
  fazer ele sumir. ai, o proximo, independente do tempo, deve fazer o painel de
  baixo aparecer."*   (2026-10-13)
      Each press used to be classified by a 1500 ms double-press window, so what
      the NEXT Alt+C did depended on how fast the last one had come: two slow
      presses were two singles and only toggled the strip, and the RIGHT panel
      was unreachable at that speed. The window and its stamp
      (`HOTKEY_DOUBLE_MS`, `_last_hotkey_press`) are DELETED. One press is one
      step of HIDDEN -> STRIP -> SIDE -> HIDDEN and the interval decides nothing
      -- arms B1..B7, where B6 is the pair that proves it by running the same six
      presses with no gap and with 1.6 s between them.

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
        #: WHAT THE WINDOW READS. The real shell asks `window_visible(hwnd)`;
        #: the arms monkeypatch that, and these two methods keep `visible` and
        #: `panel_mode` in step the way the real `show_strip`/`show_side`/
        #: `hide_panel` do (the mode is written by `place_panel`, which every
        #: show reaches). WITHOUT THIS the cycle arm could not be written at all:
        #: the fake would keep saying 'strip' after a show_side and the fourth
        #: press would repeat the second instead of advancing.
        self.visible = False
        self.calls = []

    def work_area(self):
        return dict(self._work)

    def strip_width_live(self):
        return self._sw.SottoShell.strip_width_live(self)

    def hide_panel(self, reason):
        self.calls.append(('hide', reason))
        self.visible = False
        return True

    def show_side(self, reason):
        self.calls.append(('side', reason))
        self.panel_mode = 'side'
        self.visible = True
        return True

    def show_strip(self, reason):
        self.calls.append(('strip', reason))
        self.panel_mode = 'strip'
        self.visible = True
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

    # B5 -- THE SURFACE NAME `show_side` ACTUALLY PASSES. This is the owner's
    # Alt+C bug and the oracle did not catch it: `show_side` passed the literal
    # 'side', and `normalise_surface_name` refuses it BY DESIGN, so the double
    # press logged PANEL_SURFACE_REFUSED and returned before any geometry. A fake
    # that records the ARGUMENT tests the real method body without a window.
    # NOTE ON HOW THIS ARM IS WRITTEN. The first version called `f.show_side(...)`
    # and measured NOTHING: `FakeShell` carries its OWN `show_side`, so the arm
    # exercised the fake and reported `passed=None`. It was an inert arm, which is
    # an ABSENT control. The real method touches the hwnd (children, foreground,
    # transparency hack) and cannot be driven against a fake window, so this arm
    # reads the SHIPPED BODY instead and asserts the surface name it asks for is
    # one the shell actually accepts. Static, and it flips under M4.
    import inspect
    import re as _re
    body = inspect.getsource(sw.SottoShell.show_side)
    found = _re.search(r"set_panel_surface\(\s*'([^']+)'", body)
    passed = found.group(1) if found else None
    check(tag + 'B5 show_side asks for a surface the shell ACCEPTS',
          sw.normalise_surface_name(passed) == 'panel',
          'passed=%r normalised=%r' % (passed, sw.normalise_surface_name(passed)))
    check(tag + 'B5b and "side" is not a surface name at all',
          sw.normalise_surface_name('side') is None, 'by design')

    # C1/C2 -- THE OWNER'S DRAG. The offset is CUMULATIVE from the dock, and the
    # result is clamped into the work area so the bar can never be dragged off
    # the screen.
    f = FakeShell(sw, width_dom=None)
    docked = {'x': 770, 'y': 872, 'width': 380, 'height': 148}
    g = sw.SottoShell._strip_offset_geometry(f, docked, (60, 30))
    check(tag + 'C1 the drag offset moves the strip',
          (g['x'], g['y']) == (830, 902), 'to=(%s,%s)' % (g['x'], g['y']))
    g2 = sw.SottoShell._strip_offset_geometry(f, docked, (99999, 99999))
    check(tag + 'C2 and it is clamped into the work area',
          (g2['x'], g2['y']) == (1920 - 380, 1080 - 148),
          'to=(%s,%s)' % (g2['x'], g2['y']))

    # C3/C4 -- THE TWO WIRES THAT WERE MISSING, and each is a silent no-op when
    # absent: the page probes `typeof bridge.setStripOffset === 'function'` and
    # skips the shell half in silence, so the bar can only move inside a window
    # that is now exactly the pill.
    # READ THE FILE THE MODULE WAS LOADED FROM, not the SHELL constant. The first
    # version of these two arms scanned `SHELL` and was therefore INERT under
    # --neg-arm: the mutant is loaded from a temp copy while the arm kept reading
    # the live file, so it passed either way. The mutant is what caught it, which
    # is what a control is for.
    src = open(getattr(sw, '__file__', SHELL), 'r', encoding='utf-8').read()
    check(tag + 'C3 the JS bridge object exposes setStripOffset',
          'setStripOffset: function' in src, 'window.sotto entry')
    # RE-BASELINED 2026-10-13: this arm used to look for
    # `'setStripOffset': self._set_strip_offset`, which WAS the live routing and
    # is now a sentence inside a COMMENT at :3841 — so the arm passed while
    # measuring nothing. The dispatch table was reshaped into (receiver, name)
    # tuples by the lazy-ask fix, and the receiver for this kind is the SHELL
    # (`('shell', '_set_strip_offset')`), resolved against `self._shell`.
    # The pairing with M6 is the point: the arm reads the ROUTING, the mutant
    # breaks it, and the verdict now counts an inert mutant.
    check(tag + 'C4 the dispatch map routes it to the SHELL receiver',
          "'setStripOffset': ('shell', '_set_strip_offset')" in src
          and "'sotto:setStripOffset': ('shell', '_set_strip_offset')" in src,
          'both kinds carry the shell receiver')

    # B1..B4/B6/B7 -- Alt+C IS A THREE-STATE CYCLE AND THE CLOCK IS GONE.
    #
    # THE OWNER, 2026-10-13, verbatim: *"o alt c ta meio ruim. quando o segundo
    # painel aparece, o proximo alt c deve fazer ele sumir. ai, o proximo,
    # independente do tempo, deve fazer o painel de baixo aparecer."*
    #
    # ONE press, ONE step: HIDDEN -> STRIP -> SIDE -> HIDDEN. What a press does
    # is a function of the STATE ON SCREEN and of nothing else.
    #
    # WHAT THESE ARMS REPLACED, and why the old ones could not simply be
    # re-tuned: they drove `_last_hotkey_press` to 0.10 s and 5.0 s to select the
    # double and the single branch, i.e. they PINNED the timing dependence the
    # owner is complaining about. B6/B7 are the pair that proves it is gone:
    # the SAME presses, one run with no gap and one with 1.6 s between them
    # (longer than the 1500 ms window the deleted `HOTKEY_DOUBLE_MS` used to
    # split on), must produce the IDENTICAL call list -- the owner's own words
    # *"independente do tempo"*, asserted instead of assumed.

    def cycle(start_visible=False, start_mode='strip', presses=1, gap=0.0):
        f = FakeShell(sw, width_dom=None)
        f.visible = start_visible
        f.panel_mode = start_mode
        sw.window_visible = lambda hwnd, f=f: f.visible
        for _ in range(presses):
            f.hotkey_pressed()
            if gap:
                time.sleep(gap)
        return [c[0] for c in f.calls]

    got = cycle()
    check(tag + 'B1 HIDDEN -> STRIP', got == ['strip'], str(got))

    got = cycle(start_visible=True, start_mode='strip')
    check(tag + 'B2 STRIP -> SIDE', got == ['side'], str(got))

    got = cycle(start_visible=True, start_mode='side')
    check(tag + 'B3 SIDE -> HIDDEN', got == ['hide'], str(got))

    got = cycle(presses=6)
    check(tag + 'B4 six presses walk the whole cycle',
          got == ['strip', 'side', 'hide', 'strip', 'side', 'hide'], str(got))

    quick = cycle(presses=6)
    slow = cycle(presses=6, gap=1.6)
    check(tag + 'B6 the SAME six presses 1.6 s apart are the SAME cycle',
          slow == quick and slow == ['strip', 'side', 'hide', 'strip', 'side', 'hide'],
          'quick=%s slow=%s' % (quick, slow))

    quick2 = cycle(presses=2)
    slow2 = cycle(presses=2, gap=1.6)
    check(tag + 'B7 the two-press pair is strip-then-SIDE at any speed',
          quick2 == slow2 == ['strip', 'side'], 'quick=%s slow=%s' % (quick2, slow2))


MUTANTS = [
    # M1 -- THE SIDE PANEL MADE UNREACHABLE, which is the defect the owner's
    # 2026-10-13 message names. This is the anchor the OLD M1 had to move off:
    # it reverted the double branch ("a double on a hidden panel is a no-op"),
    # and that branch no longer exists. The new mutant collapses the cycle to a
    # plain strip toggle -- exactly the behaviour the owner got when he pressed
    # slowly under the deleted double-press window, and exactly what B2 catches.
    ('M1 side-unreachable',
     "        return self.show_side('hotkey')",
     "        return self.hide_panel('hotkey')",
     'B2 STRIP -> SIDE'),
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
    ('M4 side-surface-name-restored',
     "        self.set_panel_surface('panel', reason)",
     "        self.set_panel_surface('side', reason)",
     'B5 show_side asks for a surface the shell ACCEPTS'),
    ('M5 bridge-entry-removed',
     'setStripOffset: function',
     'setStripOffsetX: function',
     'C3 the JS bridge object exposes setStripOffset'),
    # M6 -- the entry renamed. Its anchor had gone STALE when the dispatch table
    # was reshaped by the lazy-ask fix, and the oracle printed
    # "anchor missing -- the mutant would be INERT" while the VERDICT still read
    # PASS; the verdict now counts that row, so this can never pass silently
    # again. The mutation is the same one: the page's `setStripOffset` post
    # lands in BRIDGE_UNKNOWN_KIND and the drag never reaches the shell.
    ('M6 dispatch-entry-renamed',
     "            'setStripOffset': ('shell', '_set_strip_offset'),",
     "            'setStripOffsetX': ('shell', '_set_strip_offset'),",
     'C4 the dispatch map routes it to the SHELL receiver'),
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
        # AN INERT MUTANT IS NOT A CONTROL, AND IT IS NOW COUNTED AS A FAILURE.
        # Measured 2026-10-13: M6's anchor had gone stale when another lane
        # reshaped the dispatch table, the oracle PRINTED
        # "FAIL neg-arm M6 ... anchor missing -- the mutant would be INERT", and
        # the VERDICT still said PASS because only the 'goes RED' rows were
        # counted. A gate that reports a dead control in its own output and
        # green in its verdict is the failure mode this repo keeps being bitten
        # by -- see the M4 note above, where an earlier version of these arms was
        # INERT under --neg-arm for exactly this reason.
        anchor_checks = [r for r in RESULTS
                         if r[0].startswith('neg-arm ') and 'anchor found' in r[0]]
        failed = (control_failed + [r for r in red_checks if not r[1]]
                  + [r for r in anchor_checks if not r[1]])
        total = len(control) + len(red_checks) + len(anchor_checks)
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
