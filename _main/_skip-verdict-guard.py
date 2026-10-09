#!/usr/bin/env python3
"""THE SKIP GUARD -- a step that SKIPPED an arm must not be printed as a pass.

WHAT THIS AFFIRMS, in one sentence: after every step of
`_main/_audit-verify-all.cmd` has written its log, NO STEP'S LOG may carry
`VERDICT: SKIPPED` unless that step is DECLARED skip-capable. `:skipped` is the
only recorder that declares a log skip-capable, and it hands the basenames to
this instrument in `--exclude`. A step that skips an arm and still exits 0 is a
skip wearing a pass, and the difference is visible only in its log -- which is
why this sweep exists and why it must be a FAILURE, not a warning.

WHAT IT MUST NOT READ -- measured 2026-10-08, and this is the defect this
revision was written for. The first version globbed `%OUT%/*.log` and excluded
only basenames starting with `_run-`. The battery's OWN CONSOLE, when a lane
keeps it in `%OUT%` (the convention here is `_battery-run-<ts>.log`), contains
the literal string `VERDICT: SKIPPED` -- because `:skipped` ECHOES the skip text
in its own beacon line ("its own words being VERDICT: SKIPPED"). So the guard was
reading its OWN RUN'S TRANSCRIPT and failing the whole battery for a DECLARED
skip. Measured, one command, both files named:

    SKIP-VERDICT IN THE LOG OF A STEP THAT IS NOT DECLARED SKIP-CAPABLE:
    _battery-run-20261007-130942.log,_battery-run-20261007-131528.log

A guard that fails on its own output is not measuring the steps. THE RULE NOW: a
STEP LOG is a `*.log` in `%OUT%` whose basename does NOT start with `_`. Every
artifact the battery itself produces is `_`-prefixed (`_battery-run-*`, `_run-*`,
`_skip-guard.log`, `_battery-summary.txt`), and a run console is a transcript of
the whole run -- not the log of a step. The old `_run-` prefix was a NARROWER
form of the same idea and missed the name the console is actually kept under.

WHY THE CONTROL RUNS ON EVERY INVOCATION. A sweep whose file selection is wrong
fails in both directions: too wide (this defect -- RED on a declared skip) and
too narrow (GREEN because it read nothing). `--control-only` and the always-on
control below pin the second direction: four synthetic logs in a temp dir must
produce exactly one violation, from the undeclared one. If that control ever
stops going RED, this gate exits non-zero and says so, instead of reporting a
green it did not earn.

  python _main/_skip-verdict-guard.py --dir <dir> --exclude ",a.log,b.log,"
      rc 0 = every step log is clean AND the control went RED where it must
      rc 1 = at least one step's log carries an undeclared skip verdict
      rc 2 = the control did not behave -- the sweep cannot be trusted this run
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import tempfile

NEEDLE = b'VERDICT: SKIPPED'
# Every artifact the battery itself writes into %OUT% is prefixed with this. A
# step log never is -- so this single rule excludes the run consoles (the
# self-reference above), the summary and this instrument's own log, and it
# covers names added later without anyone maintaining a list.
BATTERY_ARTIFACT_PREFIX = '_'
NEEDLE_TEXT = 'VERDICT: SKIPPED'


def sweep(dirpath, exclude):
    """(bad, scanned, self_skipped, declared_skipped) for `dirpath`/*.log.

    `bad` are the basenames that carry the skip verdict and are NOT declared
    skip-capable. `scanned` is the count of files this sweep actually READ --
    the number that makes "GREEN" mean something.
    """
    bad = []
    scanned = 0
    self_skipped = 0
    declared_skipped = 0
    for path in sorted(glob.glob(os.path.join(dirpath, '*.log'))):
        name = os.path.basename(path)
        if name.startswith(BATTERY_ARTIFACT_PREFIX):
            self_skipped += 1
            continue
        if name in exclude:
            declared_skipped += 1
            continue
        try:
            with open(path, 'rb') as fh:
                blob = fh.read()
        except OSError:
            continue
        scanned += 1
        if NEEDLE in blob:
            bad.append(name)
    return bad, scanned, self_skipped, declared_skipped


def control():
    """The non-vacuity proof: four synthetic logs, exactly one must be flagged."""
    payload = f'the instrument says it did not run\n{NEEDLE_TEXT}\n'
    with tempfile.TemporaryDirectory(prefix='skipguard-') as d:
        def put(name, text):
            with open(os.path.join(d, name), 'wb') as fh:
                fh.write(text.encode('utf-8'))

        put('undeclared-step.log', payload)             # MUST be flagged
        put('_battery-run-synthetic.log', payload)      # the self-reference: MUST NOT
        put('declared-step.log', payload)               # declared: MUST NOT
        put('clean-step.log', 'the arm really ran\nVERDICT: GREEN\n')
        bad, scanned, self_skipped, declared_skipped = sweep(
            d, {'declared-step.log'})

    cases = [
        ('ARM-C1 an UNDECLARED skip verdict is CAUGHT',
         bad == ['undeclared-step.log']),
        ('ARM-C2 the battery own run console is NOT read (the self-reference)',
         '_battery-run-synthetic.log' not in bad and self_skipped == 1),
        ('ARM-C3 a DECLARED skip log is not a violation',
         'declared-step.log' not in bad and declared_skipped == 1),
        ('ARM-C4 a clean log is not a violation',
         'clean-step.log' not in bad),
        ('ARM-C5 the sweep really read the files (not a vacuous green)',
         scanned == 2),
    ]
    return cases


def main(argv=None):
    ap = argparse.ArgumentParser(description='the battery skip-verdict guard')
    ap.add_argument('--dir', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '_audit-verify'),
        help='directory holding the step logs (%OUT%)')
    ap.add_argument('--exclude', default=',',
                    help='comma-separated basenames DECLARED skip-capable')
    ap.add_argument('--control-only', action='store_true',
                    help='run only the non-vacuity control')
    args = ap.parse_args(argv)

    exclude = {x for x in args.exclude.split(',') if x}
    print(f'cadence : once, after every step has written its log')
    print(f'dir     : {args.dir}')
    print(f'needle  : {NEEDLE_TEXT}')
    print(f'exclude : {sorted(exclude) if exclude else "-none-"}')

    cases = control()
    failed_arms = [w for w, ok in cases if not ok]
    for what, ok in cases:
        print(f'{"PASS" if ok else "FAIL"} {what}')
    print(f'SKIP-GUARD-CONTROL: {"PASS" if not failed_arms else "FAIL"} '
          f'({len(cases) - len(failed_arms)}/{len(cases)})')
    if args.control_only:
        return 0 if not failed_arms else 2

    bad, scanned, self_skipped, declared_skipped = sweep(args.dir, exclude)
    print(f'step logs READ : {scanned}')
    print(f'NOT read (battery artifacts, "_" prefix) : {self_skipped}')
    print(f'NOT read (declared skip-capable)         : {declared_skipped}')
    if bad:
        print('SKIP-VERDICT IN THE LOG OF A STEP THAT IS NOT DECLARED '
              'SKIP-CAPABLE: ' + ','.join(bad))
    else:
        print('no skip verdict outside the declared skip step(s)')

    if failed_arms:
        print('SKIP-GUARD-VERDICT: RED - the control did not behave, so this '
              'sweep cannot be trusted this run')
        return 2
    if bad:
        print(f'SKIP-GUARD-VERDICT: RED - {len(bad)} undeclared skip '
              f'verdict(s) in {scanned} step log(s)')
        return 1
    print(f'SKIP-GUARD-VERDICT: GREEN - {scanned} step log(s) read, no '
          f'undeclared skip verdict, control RED where it must be')
    return 0


if __name__ == '__main__':
    sys.exit(main())
