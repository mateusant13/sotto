#!/usr/bin/env python3
# NO-BUG: instrumento (2026-11-25) da escolha de monitor e do clamp a work area -- corre a funcao pura extraida por AST sobre monitores inventados, nao abre janela nem toca em monitor algum
"""multi-monitor-oracle.py -- the strip's monitor choice is a PURE, falsifiable decision.

WHY THIS EXISTS. The shell used to let `MonitorFromPoint(POINT(0,0),
MONITOR_DEFAULTTOPRIMARY)` decide where the strip opens, and docs/shell-contract.md
said so. The Alt+C path actually goes through `work_area()` -> `target_display()`
(the cursor / foreground window), but neither the choice nor the work-area clamp
had an instrument. This oracle takes the DECISION FUNCTION out of the shipped
module `app/webview/display_geometry.py` by AST, and runs it on invented two/three-monitor
fixtures: no window, no mouse, no monitor, no model, no app. It also checks that
the shipped shell really wires `work_area()` / `geometry_for('strip')` to it.

UNITS (the thing a mixed-DPI bug hides in). `monitors` carry PHYSICAL virtual-screen
rects (negative x is a monitor left of the primary) and a scaleFactor (physical px
per DIP). `point` is physical. `geometry` is DIP: the selector multiplies by the
chosen scale ONCE, clamps in PHYSICAL against that monitor's WORK AREA (not its
full bounds), and divides by the same scale ONCE. A second scaling shows up as a
wrong number in arm 6.

THE SIX ARMS:
  right          point in the secondary to the RIGHT -> that monitor, by containment;
  negative-left  point in a secondary with NEGATIVE x -> that monitor, still containment;
  nearest        point outside every monitor -> MONITOR_DEFAULTTONEAREST semantics;
  empty          no monitors at all -> fall back to the primary, no crash;
  clamp          rect bigger than the work area is clamped at BOTH edges, and to
                 the WORK AREA (1032 high), not the full 1080-high bounds;
  mixed-dpi      a rect that fits is unchanged; an oversized one is clamped once,
                 with the 1.5x secondary's numbers, not twice.

`--neg-arm` mutates ONE line per arm in a COPY of the extracted function and
asserts that arm goes RED. A mutation that does not redden its arm makes the
CONTROL fail -- an oracle that cannot say NO is decoration.

Usage:
  py -3 _main\\multi-monitor-oracle.py
  py -3 _main\\multi-monitor-oracle.py --neg-arm
"""

from __future__ import annotations

import argparse
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
GEOMETRY = os.path.join(ROOT, 'app', 'webview', 'display_geometry.py')

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Physical virtual-screen pixels. The primary is index 0; the right monitor is
# 1.5x, the left (NEGATIVE x) monitor is 1.25x: three scales, one fixture.
PRIMARY = {
    'handle': 1, 'scaleFactor': 1.0,
    'bounds': {'x': 0, 'y': 0, 'width': 1920, 'height': 1080},
    'workArea': {'x': 0, 'y': 0, 'width': 1920, 'height': 1032},
}
RIGHT = {
    'handle': 2, 'scaleFactor': 1.5,
    'bounds': {'x': 1920, 'y': 0, 'width': 1280, 'height': 720},
    'workArea': {'x': 1920, 'y': 0, 'width': 1280, 'height': 672},
}
LEFT = {
    'handle': 3, 'scaleFactor': 1.25,
    'bounds': {'x': -1280, 'y': 0, 'width': 1280, 'height': 800},
    'workArea': {'x': -1280, 'y': 0, 'width': 1280, 'height': 752},
}
MONITORS = [PRIMARY, RIGHT, LEFT]

# Exactly one call in target_placement: if somebody re-wires the strip around
# the pure selector, the wiring arm goes RED even if all six pure arms pass.
WIRE_CALL = ("    result = select_display_for_point(point, monitors, primary_index,\n"
             "                                      geometry=geometry)")
WIRE_MUTANT = "    result = {'display': None, 'geometry': geometry}"


def read_source(path=SHELL):
    """Both halves of the cut: the shell's wiring and the module's selector.

    S1 moved `select_display_for_point` into `display_geometry.py`, but the
    wiring arms below still assert against the shipped shell. One combined
    source keeps the AST arm on the REAL function and every wiring/mutation
    anchor on the REAL caller.
    """
    with open(path, 'r', encoding='utf-8') as handle:
        shell = handle.read()
    with open(GEOMETRY, 'r', encoding='utf-8') as handle:
        geometry = handle.read()
    return shell + '\n' + geometry


def load_selector(source):
    """AST-extract the SHIPPED function; exec only that function, nothing else."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'select_display_for_point':
            segment = ast.get_source_segment(source, node)
            namespace = {}
            exec(compile(segment, '<select_display_for_point>', 'exec'), namespace)
            return namespace['select_display_for_point']
    raise RuntimeError('select_display_for_point is GONE from the geometry module source')


def check(label, got, want):
    return (label, got == want, 'got=%r want=%r' % (got, want))


def arm_right(sel):
    r = sel((2400, 300), MONITORS, 0)
    return [
        check('right/index', r.get('index'), 1),
        check('right/reason', r.get('reason'), 'point'),
        check('right/work-area-DIP', (r.get('display') or {}).get('workArea'),
              {'x': 1280, 'y': 0, 'width': 853, 'height': 448}),
    ]


def arm_negative_left(sel):
    r = sel((-500, 400), MONITORS, 0)
    return [
        check('negative-left/index', r.get('index'), 2),
        check('negative-left/reason', r.get('reason'), 'point'),
        check('negative-left/work-area-DIP', (r.get('display') or {}).get('workArea'),
              {'x': -1024, 'y': 0, 'width': 1024, 'height': 602}),
    ]


def arm_nearest(sel):
    r = sel((4000, 4000), MONITORS, 0)
    return [
        check('nearest/index', r.get('index'), 1),
        check('nearest/reason', r.get('reason'), 'nearest'),
    ]


def arm_empty(sel):
    r = sel((100, 100), [], 0, geometry={'width': 10, 'height': 10})
    return [
        check('empty/index', r.get('index'), None),
        check('empty/reason', r.get('reason'), 'primary'),
        check('empty/display', r.get('display'), None),
        check('empty/unclamped-geometry', r.get('geometry'), None),
    ]


def arm_clamp(sel):
    r = sel((100, 100), MONITORS, 0, geometry={
        'x': -500, 'y': -50, 'width': 3000, 'height': 2000, 'surface': 'strip'})
    g = r.get('geometry') or {}
    r2 = sel((100, 100), MONITORS, 0, geometry={
        'x': 5000, 'y': 5000, 'width': 100, 'height': 100})
    g2 = r2.get('geometry') or {}
    return [
        check('clamp/left-edge', g.get('x'), 0),
        check('clamp/top-edge', g.get('y'), 0),
        check('clamp/width', g.get('width'), 1920),
        check('clamp/work-area-height-not-bounds', g.get('height'), 1032),
        check('clamp/extra-key-kept', g.get('surface'), 'strip'),
        check('clamp/right-edge', g2.get('x'), 1820),
        check('clamp/bottom-edge', g2.get('y'), 932),
    ]


def arm_mixed_dpi(sel):
    fit = sel((2400, 300), MONITORS, 0, geometry={
        'x': 1300, 'y': 10, 'width': 100, 'height': 50, 'docked': 'bottom-strip'})
    g = fit.get('geometry') or {}
    big = sel((2400, 300), MONITORS, 0, geometry={
        'x': 1300, 'y': 10, 'width': 2000, 'height': 100})
    g2 = big.get('geometry') or {}
    display = fit.get('display') or {}
    dip = display.get('workArea') or {}
    return [
        check('mixed-dpi/index', fit.get('index'), 1),
        # The reported work area is in DIP: the 1.5x monitor's 1280 physical
        # pixels are 853 DIP wide. Without this the `as_dip` division had no
        # arm at all and a mutant that skips it survived the control.
        check('mixed-dpi/workarea-dip-width', dip.get('width'), 853),
        check('mixed-dpi/workarea-dip-height', dip.get('height'), 448),
        check('mixed-dpi/once-x', g.get('x'), 1300),
        check('mixed-dpi/once-y', g.get('y'), 10),
        check('mixed-dpi/once-width', g.get('width'), 100),
        check('mixed-dpi/once-height', g.get('height'), 50),
        check('mixed-dpi/key-kept', g.get('docked'), 'bottom-strip'),
        check('mixed-dpi/clamped-x', g2.get('x'), 1280),
        check('mixed-dpi/clamped-width', g2.get('width'), 853),
        check('mixed-dpi/clamped-height', g2.get('height'), 100),
    ]


ARMS = [
    ('right', arm_right),
    ('negative-left', arm_negative_left),
    ('nearest', arm_nearest),
    ('empty', arm_empty),
    ('clamp', arm_clamp),
    ('mixed-dpi', arm_mixed_dpi),
]


def wiring(source):
    """The shell must USE the selector, not merely carry a copy of it."""
    return [
        ('wiring/target_placement-calls-selector', WIRE_CALL in source,
         'the pure call is gone from target_placement'),
        ('wiring/work_area-reads-placement',
         'placement = target_placement(geometry=geometry)' in source
         and 'self._placement = placement' in source,
         'work_area() no longer routes through target_placement'),
        ('wiring/strip-clamps-through-selector',
         'self._clamped_strip_geometry(' in source
         and 'select_display_for_point(\n            placement.get(\'point\')' in source,
         'geometry_for(\'strip\') no longer clamps through the selector'),
        ('wiring/primary-definition-kept',
         'def primary_display() -> dict:' in source,
         'primary_display() is GONE -- the docked startup would raise NameError'),
        ('wiring/docked-panel-still-primary',
         'self.display = primary_display()' in source
         and "self.geometry = dock_right(self.display['workArea'])" in source,
         'the docked panel startup now picks a different monitor'),
    ]


# One mutation per arm. Each old string is asserted present in the SHIPPED
# source before it is replaced -- a stale anchor is an INVALID control, not a
# quiet pass.
MUTATIONS = [
    ('right', 'if xy is not None and x <= xy[0] < x + w and y <= xy[1] < y + h:',
     'if False:'),
    ('negative-left', 'x <= xy[0] < x + w', '0 <= xy[0] < x + w'),
    ('nearest', 'if best is None or dist < best[0]:', 'if False:'),
    ('empty', "'index': index, 'reason': reason, 'point': xy,",
     "'index': index, 'reason': 'nearest', 'point': xy,"),
    ('clamp', 'pw = min(max(1.0, gw * scale), ww)', 'pw = max(1.0, gw * scale)'),
    # The other two thirds of the same one-clamp: the HEIGHT and the DIP
    # conversion. Without these the control only proves the width line.
    ('clamp', 'ph = min(max(1.0, gh * scale), wh)', 'ph = max(1.0, gh * scale)'),
    ('mixed-dpi', "'width': max(1, round(w / scale)),", "'width': max(1, round(w)),"),
    ('mixed-dpi', 'px = gx * scale', 'px = gx'),
    ('wiring', WIRE_CALL, WIRE_MUTANT),
    ('wiring-primary', 'def primary_display() -> dict:',
     'def _primary_gone() -> dict:'),
    ('wiring-docked', 'self.display = primary_display()',
     'self.display = target_display()'),
]


def run_negative(source):
    bad = 0
    for name, old, new in MUTATIONS:
        if old not in source:
            print('MUTANT %-14s CONTROL INVALID -- anchor %r is gone' % (name, old[:48]))
            bad += 1
            continue
        mutant = source.replace(old, new, 1)
        if mutant == source:
            print('MUTANT %-14s CONTROL INVALID -- mutation changed nothing' % name)
            bad += 1
            continue
        if name.startswith('wiring'):
            rows = wiring(mutant)
        else:
            fn = dict(ARMS)[name]
            rows = fn(load_selector(mutant))
        red = [row for row in rows if not row[1]]
        print('MUTANT %-14s red=%d/%d %s'
              % (name, len(red), len(rows),
                 ' '.join(row[0] for row in red[:4])))
        if not red:
            bad += 1
    print('CONTROL ' + ('PASS -- all %d mutants reddened their own arm'
                        % len(MUTATIONS) if not bad
                        else 'FAIL -- %d mutant(s) survived' % bad))
    # A CONTROL RUN EXITS 1 WHEN IT PASSES: the house convention (`:expectred`
    # in the battery) is that the negative arm finds its defects and exits 1,
    # while 0 means the control did not go red. 2 is a setup error.
    return 2 if bad else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--neg-arm', action='store_true',
                        help='mutate each arm in a COPY; every arm must go RED')
    args = parser.parse_args(argv)
    source = read_source()
    if args.neg_arm:
        return run_negative(source)

    selector = load_selector(source)
    failures = []
    for name, fn in ARMS:
        rows = fn(selector)
        for label, ok, detail in rows:
            print('%-34s %s  %s' % (label, 'PASS' if ok else 'FAIL', detail))
            if not ok:
                failures.append('%s: %s' % (label, detail))
    for label, ok, detail in wiring(source):
        print('%-34s %s  %s' % (label, 'PASS' if ok else 'FAIL', detail))
        if not ok:
            failures.append('%s: %s' % (label, detail))
    for row in failures:
        print('FAIL ' + row)
    verdict = 'PASS' if not failures else 'FAIL'
    print('MULTI-MONITOR %s -- %d arm(s), %d check(s), %d failure(s)'
          % (verdict, len(ARMS), sum(len(fn(selector)) for _, fn in ARMS),
             len(failures)))
    print('VERDICT: ' + verdict)
    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
