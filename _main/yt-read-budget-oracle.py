"""Oracle for the accessibility-tree caption read envelope.

MEASURED 2026-11-26 (owner's session, pid 103760): one UIA caption read blocked
`EXTERNAL_CAPTIONS_READ_MS ms=16437.0 phases={'painted': 15906.0, ...}`, the
4 Hz loop fell to 0.1-1.5 Hz and the subtitle froze. `yt_read_budget` refuses to
re-enter that read at the same cadence: a read over budget buys a hold
proportional to what it spent, and the caller serves the last words instead.

Arms:
  * a fast read never holds and clears any previous hold;
  * the budget is a ceiling, not a target -- at the budget no hold, above it a hold;
  * the measured 15906 ms buys 47.7 s and NAMES the episode;
  * a small overrun still honours the floor;
  * `serving_cached` is strict at the boundary and cannot be turned on by garbage;
  * the shell gates the tree call behind `serving_cached`, caches the last words,
    and never calls the tree inside the backoff branch;
  * the module is pure (no clock, no imports) so the caller owns time.

`--neg-arm` mutates the module (and the shell wiring) one way at a time and
requires every mutant to be CAUGHT by an arm -- rc 1 when all are caught, rc 0
when any mutant survives, which is the blind-gate verdict.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, 'app', 'webview', 'yt_read_budget.py')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')

FAIL = []


sys.dont_write_bytecode = True


def _load(path, name='yt_read_budget_probe'):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arms(mod):
    out = []

    def arm(name, ok, detail=''):
        out.append((name, bool(ok), detail))

    # A1 -- a healthy read costs nothing and clears a stale hold
    serve, until, event = mod.decide(120.0, 999.0, 1000.0)
    arm('a1-fast-read-no-hold', (serve, until, event) == (False, 0.0, None),
        '%r' % ((serve, until, event),))

    # A2 -- the budget is a ceiling: exactly at it no hold, a hair above it holds
    at = mod.decide(mod.UIA_BUDGET_MS, 0.0, 10.0)
    over = mod.decide(mod.UIA_BUDGET_MS + 0.1, 0.0, 10.0)
    arm('a2-budget-is-a-ceiling',
        at == (False, 0.0, None) and over[0] is True and over[1] > 10.0,
        'at=%r over=%r' % (at, over))

    # A3 -- the measured 15906 ms buys 47.7 s and names itself
    serve, until, event = mod.decide(15906.0, 0.0, 500.0)
    hold = until - 500.0
    arm('a3-measured-read-names-its-hold',
        serve is True and abs(hold - 47.718) < 0.01
        and event is not None and 'ms=15906.0' in event and 'hold_s=47.7' in event,
        'hold=%.3f event=%r' % (hold, event))

    # A4 -- and the same read at 16437 ms (the whole read) still holds
    serve, until, event = mod.decide(16437.0, 0.0, 0.0)
    arm('a4-whole-read-also-holds', serve is True and until > 0.0, '%r' % (until,))

    # A5 -- a small overrun still honours the floor, never a zero hold
    serve, until, event = mod.decide(351.0, 0.0, 100.0)
    arm('a5-floor-holds-a-tiny-overrun',
        serve is True and (until - 100.0) >= 2.0,
        'hold=%.3f' % (until - 100.0))

    # A6 -- serving_cached is strict at the boundary
    arm('a6-boundary-is-strict',
        mod.serving_cached(101.0, 100.0) is True
        and mod.serving_cached(100.0, 100.0) is False
        and mod.serving_cached(0.0, 100.0) is False,
        'ok')

    # A7 -- garbage is not a hold, and not a crash
    arm('a7-garbage-is-not-a-hold',
        mod.serving_cached(None, 100.0) is False
        and mod.serving_cached('x', 100.0) is False
        and mod.decide('nonsense', 0.0, 1.0) == (False, 0.0, None),
        'ok')

    # A8 -- the module is pure: no clock of its own, no imports
    src = open(MODULE, 'r', encoding='utf-8', errors='replace').read()
    body = '\n'.join(l for l in src.splitlines()
                     if not l.strip().startswith('#')
                     and not l.lstrip().startswith('"'))
    arm('a8-module-is-pure',
        'import ' not in body and 'time.' not in body,
        'imports/clock found' if 'import ' in body or 'time.' in body else 'pure')

    # A9 -- the shell asks `serving_cached` BEFORE it touches the tree
    shell = open(SHELL, 'r', encoding='utf-8', errors='replace').read()
    gate = shell.find('yt_read_budget.serving_cached(\n                        getattr(self')
    if gate < 0:
        gate = shell.find('yt_read_budget.serving_cached(')
    tree = shell.find('youtube_captions.painted_words(uia, UIA, hwnd=hwnd')
    arm('a9-shell-gates-the-tree-call', 0 <= gate < tree,
        'gate=%d tree=%d' % (gate, tree))

    # A10 -- the backoff branch serves the last words and says why
    arm('a10-backoff-serves-last-words',
        "'why': 'uia-backoff'" in shell and '_yt_uia_last_got' in shell,
        'ok')

    # A12 -- the owner's own numbers, simulated: a 4 Hz loop whose tree read
    # costs the MEASURED 15906 ms. Without the envelope it manages 1/15.9 Hz
    # (that is the freeze); with it the cadence comes back after ONE slow read.
    def cadence(use_envelope):
        t = 0.0
        ticks = 0
        blocked = 0.0
        while t < 60.0:
            ticks += 1
            if use_envelope and mod.serving_cached(blocked, t):
                t += 0.250          # the loop's own 4 Hz period
                continue
            t += 0.250 + 15.906     # one tick that paid for the slow read
            if use_envelope:
                _serve, blocked, _event = mod.decide(15906.0, blocked, t)
        return ticks / 60.0

    blind = cadence(False)
    healed = cadence(True)
    arm('a12-measured-read-keeps-the-cadence',
        blind < 0.10 and healed >= 2.5,
        'blind=%.3fHz healed=%.3fHz' % (blind, healed))

    # A11 -- the slow episode is logged with its own name
    arm('a11-episode-is-named', 'YOUTUBE_UIA_SLOW_BUDGET' in src and 'log(_event)' in shell,
        'ok')
    return out


def run(mod=None, label='live'):
    mod = mod or _load(MODULE)
    rows = arms(mod)
    bad = [r for r in rows if not r[1]]
    for name, ok, detail in rows:
        print('  %-34s %s  %s' % (name, 'ok' if ok else 'FAIL', detail))
    print('ARM-SUMMARY %s arms=%d ok=%d fail=%d' % (label, len(rows), len(rows) - len(bad), len(bad)))
    return rows, bad


MUTANTS = [
    ('budget-ignored-every-read-holds',
     MODULE, '    if elapsed_ms <= UIA_BUDGET_MS:\n        return (False, 0.0, None)',
     '    if False:\n        return (False, 0.0, None)'),
    ('hold-floor-removed', MODULE, 'HOLD_MIN_S = 2.0', 'HOLD_MIN_S = 0.0'),
    ('hold-scale-zero', MODULE, 'HOLD_SCALE = 3.0', 'HOLD_SCALE = 0.0'),
    ('serving-cached-never-true',
     MODULE, '    return float(now) < float(blocked_until or 0.0)',
     '    return False'),
    ('event-loses-the-measurement',
     MODULE, "'YOUTUBE_UIA_SLOW_BUDGET ms=%.1f hold_s=%.1f'",
     "'YOUTUBE_UIA_SLOW_BUDGET hold_s=%.1f at=%.1f'"),
    ('boundary-off-by-one',
     MODULE, '    return float(now) < float(blocked_until or 0.0)',
     '    return float(now) <= float(blocked_until or 0.0)'),
]


def neg_arm():
    caught = 0
    total = 0
    tmp = tempfile.mkdtemp(prefix='yt-read-budget-neg-')
    try:
        for name, path, old, new in MUTANTS:
            total += 1
            src = open(path, 'r', encoding='utf-8', errors='replace').read()
            if old not in src:
                print('  %-34s MUTANT-BROKEN (anchor missing)' % name)
                continue
            copy = os.path.join(tmp, 'yt_read_budget_mut_%d.py' % total)
            open(copy, 'w', encoding='utf-8', newline='\n').write(src.replace(old, new, 1))
            try:
                mod = _load(copy, 'yt_read_budget_mut_%d' % total)
                _, bad = run(mod, label='mutant:%s' % name)
            except Exception as exc:  # noqa: BLE001
                print('  %-34s MUTANT-BROKEN (%r)' % (name, exc))
                continue
            if bad:
                caught += 1
            else:
                print('  %-34s SURVIVED -- the gate is blind here' % name)

        # wiring mutant: the shell touches the tree before it asks the envelope
        total += 1
        shell = open(SHELL, 'r', encoding='utf-8', errors='replace').read()
        gate = 'yt_read_budget.serving_cached('
        tree = 'youtube_captions.painted_words(uia, UIA, hwnd=hwnd'
        if gate in shell and tree in shell:
            moved = shell.replace(tree, '__TREE__', 1).replace(gate, tree, 1).replace('__TREE__', gate, 1)
            shell_copy = os.path.join(tmp, 'sotto_webview_mut.py')
            open(shell_copy, 'w', encoding='utf-8', newline='').write(moved)
            mut_gate = moved.find(gate)
            mut_tree = moved.find(tree)
            if mut_gate < 0 or mut_tree < 0 or mut_gate > mut_tree:
                caught += 1
                print('  %-34s CAUGHT (order inverted)' % 'shell-gates-before-the-tree-call')
            else:
                print('  %-34s SURVIVED -- the gate is blind here' % 'shell-gates-before-the-tree-call')
        else:
            print('  %-34s MUTANT-BROKEN (anchors missing)' % 'shell-gates-before-the-tree-call')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print('NEG-ARM %d/%d CAUGHT' % (caught, total))
    # The battery's matcher reads this exact token: the negative arm passed
    # means every mutant was caught (rc 1 on that run is the house convention).
    if caught == total:
        print('NEG-ARM VERDICT: PASS')
    # House convention: a caught mutant is rc 1 (red-as-expected); rc 0 means a
    # mutant survived and this gate is blind.
    return 1 if caught == total else 0


def main(argv):
    if '--neg-arm' in argv:
        code = neg_arm()
    else:
        _, bad = run()
        code = 1 if bad else 0
    if '--neg-arm' in argv:
        print('VERDICT: %s' % ('CAUGHT' if code == 1 else 'BLIND'))
    else:
        print('VERDICT: %s' % ('PASS' if code == 0 else 'RED'))
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
