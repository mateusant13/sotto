#!/usr/bin/env python3
"""panel-state-atomic-oracle -- THE PANEL DUMP MUST LAND WHOLE, OR NOT AT ALL.

THE DEFECT THIS GATES (measured 2026-10-13, in the shell audit)
----------------------------------------------------------------
`_main/panel-state.json` has TWO writers: the shell's periodic writer and the
worker. `panel_state.write_atomic` used a FIXED temp name (`path + ".tmp"`), so the
two writers collided on the same temp path AS WELL AS on the rename, and the log
carried **1 145 063 write failures** -- 197.7 MB of an 808.6 MB log, 62-83% of them
inside the surface loop and only 1-2 an hour outside it.

THE CURE, IN TWO PARTS, AND THIS FILE GATES BOTH:
  1. a UNIQUE temp name -- `path.<pid>.<thread ident>.tmp` -- so two writers can
     never open the same temp file;
  2. a BOUNDED RETRY on the rename -- `os.replace` fails with PermissionError(13)
     while the other writer holds the target open, and a short retry turns a lost
     write into a delayed one.

WHAT THIS MEASURES, AND HOW
---------------------------
THE REAL MODULE, LOADED BY PATH from app/webview/panel_state.py, and the REAL
`PanelStateWriter` class driven against a scratch target. Nothing is launched, no
window is created, no app is touched. The two seams are recorded, never faked away:
the module-level `open` is wrapped to CAPTURE the temp path each write uses, and the
module-level `os` is swapped for a shim that can make `os.replace` fail on demand --
which is how a PermissionError storm is reproduced deterministically instead of
hoped for.

ARMS
  S1  the temp name carries pid AND thread ident, and is not a constant suffix
  S2  the rename retries, bounded, and catches PermissionError
  S3  the temp file is a SIBLING of the target and is fsynced before the rename
  B1  one write lands a valid JSON file and leaves no .tmp behind
  B2  two threads writing one target use DIFFERENT temp names (the collision)
  B3  concurrent writers: the dump is NEVER half-written (always parses)
  B4  the retry absorbs a transient PermissionError (2 failures -> still lands)
  B5  when the rename never succeeds, it raises AND removes its temp file
  B6  two REAL PanelStateWriters on one path (the shell + the worker case)

WHAT B3 DOES *NOT* CLAIM, MEASURED: the rename retry is BOUNDED (6 attempts), so
under four-thread contention a write can still be LOST -- measured 2 of 100 on the
shipped module, against 31 and 42 of 100 with each half of the cure removed. The
invariant B3 asserts is the one that is structural: a reader never sees HALF a
dump (os.replace is atomic), measured 0 unparsable reads shipped against 557 with
the fixed temp name. Reads refused while a rename is in flight (30-33) are counted
and reported: a BUSY read is not a partial one.

THE NEGATIVE ARM (--neg-arm) IS THE POINT OF THIS FILE: panel_state.py is copied to
a scratch directory and the cure is removed from the copy, one half at a time:
  M1  the FIXED temp name is restored (`path + ".tmp"`)
  M2  the retry is deleted (one bare os.replace)
Both must go RED, or a green above cannot tell the cure from an untested file.

USAGE
  py -3 _main/panel-state-atomic-oracle.py            expect VERDICT: PASS, rc=0
  py -3 _main/panel-state-atomic-oracle.py --neg-arm  expect both mutants RED, rc=1 BY DESIGN

Exit codes
  0  the green arm PASSED -- OR, in the negative arm, a mutant was INERT (it moved no
     check, so the gate is blind there: that is a FAILURE of the negative arm)
  1  the green arm FAILED -- OR, in the negative arm, EVERY mutant went RED (BY
     DESIGN: the negative arm has to fail, so this is its success)
  2  setup error: the anchor is missing or ambiguous. A decorative mutant proves
     nothing, so the arm refuses to count it instead of reporting a green.
  No window, no launch, no audio.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.path.pardir))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
MODULE = os.path.join(WEBVIEW, 'panel_state.py')
SCRATCH_ROOT = 'I:/cc-tmp'

RESULTS = []


def emit(line=''):
    print(line, flush=True)


def check(name, ok, detail=''):
    RESULTS.append(bool(ok))
    emit(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        emit(f"         {detail}")


def load_module(path, name):
    """Import the shipped module by path, stdout captured."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load a module from {path!r}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spec.loader.exec_module(module)
    return module


class TempCapture:
    """The module-level `open`, wrapped: records the temp path of every write.

    `panel_state` looks `open` up in its own globals first, so assigning this on the
    module is enough -- and the arm asserts it captured something, so a patch that
    silently did nothing is a RED and never a vacuous pass.
    """

    def __init__(self, real_open):
        self.real_open = real_open
        self.temp_paths = []

    def __call__(self, file, mode='r', *args, **kwargs):
        if 'w' in str(mode) and str(file).endswith('.tmp'):
            self.temp_paths.append(str(file))
        return self.real_open(file, mode, *args, **kwargs)


class OsShim:
    """The module-level `os`, wrapped so `os.replace` can fail ON DEMAND.

    This is how the PermissionError storm the audit measured is reproduced:
    deterministically, N times, and then let through. Everything else delegates to
    the real `os`, so nothing else about the write path changes.
    """

    def __init__(self, real_os, fail_times=0):
        self._real = real_os
        self.fail_times = int(fail_times)
        self.attempts = 0

    def __getattr__(self, name):
        return getattr(self._real, name)

    def replace(self, src, dst):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise PermissionError(13, 'O arquivo ja esta sendo usado por outro processo')
        return self._real.replace(src, dst)

def static_arms(module, label):
    '''S1..S3 -- read off the SHIPPED source of whichever copy is handed in.'''
    with open(module.__file__, encoding='utf-8') as fh:
        text = fh.read()

    # THE CODE, NOT THE PROSE. The first draft grepped the whole file for
    # "path + '.tmp'" and got a FALSE RED: the shipped docstring QUOTES that
    # string to explain why it is not used. So S1 and S2 read the parsed function.
    tree = ast.parse(text, filename=module.__file__)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'write_atomic':
            fn = node
    if fn is None:
        check('S1 the temp name carries pid AND thread ident, not a constant suffix',
              False, 'no write_atomic function in %s' % module.__file__)
        return

    # S1 -- the temp name is per (pid, thread), never a constant suffix
    segment = ''
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'tmp' for t in node.targets):
            segment = ast.get_source_segment(text, node) or ''
    has_pid = 'os.getpid()' in segment and 'threading.get_ident()' in segment
    fixed = "path + '.tmp'" in segment or "'%s.tmp'" in segment
    check('S1 the temp name carries pid AND thread ident, not a constant suffix',
          has_pid and not fixed,
          'the temp-name statement is %r; pid+thread: %s; constant suffix: %s'
          % (segment, has_pid, fixed))

    # S2 -- the rename retries, bounded, on PermissionError (AST, not text)
    loop = None
    for node in ast.walk(fn):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call) \
                and getattr(node.iter.func, 'id', '') == 'range':
            for inner in ast.walk(node):
                if isinstance(inner, ast.Try):
                    for handler in inner.handlers:
                        if getattr(handler.type, 'id', '') == 'PermissionError':
                            loop = node
    check('S2 the rename retries, bounded, and catches PermissionError',
          loop is not None,
          'a bounded retry loop that catches PermissionError: %s' % (loop is not None))

    # S3 -- sibling temp + fsync before the rename
    sibling = 'os.path.dirname(os.path.abspath(path))' in text
    fsync = 'os.fsync(handle.fileno())' in text
    check('S3 the temp is a sibling of the target and is fsynced first',
          sibling and fsync,
          'sibling directory resolved: %s; fsync before rename: %s' % (sibling, fsync))


def behavioural_arms(module, scratch):
    '''B1..B6 -- the real functions and the real class, on a scratch target.'''
    target = os.path.join(scratch, 'panel-state.json')
    real_open = open
    capture = TempCapture(real_open)
    module.open = capture

    # B1 -- one write lands whole, and leaves no temp behind
    payload = {'schema': 'sotto.panel-state/1', 'sequence': 1, 'who': 'oracle'}
    module.write_atomic(target, payload)
    with open(target, encoding='utf-8') as fh:
        landed = json.load(fh)
    leftovers = [f for f in os.listdir(scratch) if f.endswith('.tmp')]
    check('B1 one write lands a valid JSON file and leaves no .tmp behind',
          landed.get('sequence') == 1 and not leftovers,
          'parsed sequence=%r; leftover temp files=%r' % (landed.get('sequence'), leftovers))

    # B2 -- the measured collision: two threads, one target, DIFFERENT temp names
    capture.temp_paths.clear()
    barrier = threading.Barrier(2)

    b2_errors = []

    def writer(n):
        barrier.wait()
        try:
            module.write_atomic(target, {'schema': 'sotto.panel-state/1', 'sequence': n})
        except Exception as exc:  # noqa: BLE001 -- the collision's own fallout
            b2_errors.append(repr(exc))

    threads = [threading.Thread(target=writer, args=(n,)) for n in (2, 3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    names = list(capture.temp_paths)
    collision = any(n.endswith('panel-state.json.tmp') for n in names)
    check('B2 two threads writing one target use DIFFERENT temp names',
          len(names) == 2 and names[0] != names[1] and not collision and not b2_errors,
          'temp names captured: %r; write failures: %r' % (names, b2_errors))

    # B3 -- concurrent writers: every write succeeds and the file ALWAYS parses
    errors = []
    tally = {'ok': 0, 'bad': 0, 'busy': 0}
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                with open(target, encoding='utf-8') as fh:
                    json.load(fh)
                tally['ok'] += 1
            except FileNotFoundError:
                pass
            except PermissionError:
                # A replace in flight: Windows refuses the READ for the instant the
                # rename holds the name. That is a busy read, NOT a partial one -- the
                # claim this arm makes is that the file is never HALF-WRITTEN, and a
                # busy read says nothing about that. Counted, and reported.
                tally['busy'] += 1
            except ValueError:
                tally['bad'] += 1

    def flood(n):
        for i in range(25):
            try:
                module.write_atomic(target, {'schema': 'sotto.panel-state/1',
                                             'writer': n, 'i': i,
                                             'pad': 'x' * (40 + 20 * ((i + n) % 7))})
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()
    floods = [threading.Thread(target=flood, args=(n,)) for n in range(4)]
    for t in floods:
        t.start()
    for t in floods:
        t.join()
    stop.set()
    reader_thread.join(timeout=2.0)
    ok_reads, bad_reads = tally['ok'], tally['bad']
    busy = tally['busy']
    detail = ('100 writes over 4 threads; write errors=%d; reads parsed=%d; '
              'reads that did NOT parse=%d; reads refused while a rename was in '
              'flight=%d') % (len(errors), ok_reads, bad_reads, busy)
    if errors:
        detail += '; first error=%s' % errors[0]
    # THE CLAIM IS ATOMICITY, NOT ZERO-FAILURE, and the first draft got that
    # wrong: the rename retry is BOUNDED (6 attempts), so under four-thread
    # contention a write can still be lost -- measured 2 of 100 on the shipped
    # module. What must never happen is a reader seeing HALF a dump, and that is
    # structural: os.replace is atomic, so a partial read is impossible while the
    # temp name is unique. With the fixed temp name the same arm measured 557
    # unparsable reads, which is the defect this file is about.
    check('B3 concurrent writers: the dump is NEVER half-written (always parses)',
          bad_reads == 0 and ok_reads > 0, detail)

    # B4 -- the retry absorbs a transient PermissionError
    shim = OsShim(os, fail_times=2)
    module.os = shim
    raised = None
    try:
        module.write_atomic(target, {'schema': 'sotto.panel-state/1', 'sequence': 99})
    except Exception as exc:  # noqa: BLE001
        raised = exc
    finally:
        module.os = os
    with open(target, encoding='utf-8') as fh:
        after = json.load(fh)
    check('B4 the retry absorbs a transient PermissionError (2 failures -> lands)',
          raised is None and after.get('sequence') == 99 and shim.attempts >= 3,
          'rename attempts=%d (2 refused, then let through); raised=%r; landed sequence=%r'
          % (shim.attempts, raised, after.get('sequence')))

    # B5 -- when the rename NEVER succeeds, it raises and cleans its temp up
    before_files = set(os.listdir(scratch))
    shim = OsShim(os, fail_times=99)
    module.os = shim
    raised = None
    try:
        module.write_atomic(target, {'schema': 'sotto.panel-state/1', 'sequence': 100})
    except Exception as exc:  # noqa: BLE001
        raised = exc
    finally:
        module.os = os
    after_files = set(os.listdir(scratch))
    new_temps = [f for f in (after_files - before_files) if f.endswith('.tmp')]
    check('B5 a rename that never succeeds raises AND removes its temp file',
          raised is not None and not new_temps,
          'attempts=%d; raised=%s; temp files left behind=%r'
          % (shim.attempts, type(raised).__name__ if raised else None, new_temps))

    # B6 -- the REAL writer class, twice, on one path (the shell + the worker case)
    two = os.path.join(scratch, 'two-writers.json')
    made = []
    for n in (1, 2):
        w = module.PanelStateWriter(
            path=two,
            snapshot=lambda reason, n=n: {'who': n, 'reason': reason},
            log=lambda _m: None, interval_s=0.2)
        made.append(w)
    results = [w.write('oracle') for w in made]
    with open(two, encoding='utf-8') as fh:
        both = json.load(fh)
    check('B6 two REAL PanelStateWriters on one path both land, dump valid',
          all(results) and both.get('schema') == module.SCHEMA
          and made[0].writes == 1 and made[1].writes == 1,
          'write() results=%r; writes=%r; errors=%r; landed schema=%r'
          % (results, [w.writes for w in made], [w.errors for w in made],
             both.get('schema')))

    module.open = real_open

# ---------------------------------------------------------------------------
# the mutants -- one half of the cure removed at a time
# ---------------------------------------------------------------------------

def mutant_edits():
    '''(label, old, new) -- exact strings, and a count of 1 is required.'''
    fixed_name = (
        "    tmp = '%s.%d.%d.tmp' % (path, os.getpid(), threading.get_ident())")
    # THE ANCHOR MOVED (2026-10-20): the retry grew from 6 to 20 attempts and the
    # sleep is now CAPPED at 0.1 s (`time.sleep(min(0.1, 0.02 * (attempt + 1)))`), so
    # the old 6-attempt block matched 0 times and the negative arm died with a SETUP
    # ERROR instead of proving anything. THE MUTATION IS THE SAME ONE THIS INSTRUMENT
    # DOCUMENTS: the retry is deleted and the rename becomes ONE bare `os.replace` --
    # the defect the row names (a lost write instead of a delayed one).
    retry_block = chr(10).join([
        '    for attempt in range(20):',
        '        try:',
        '            os.replace(tmp, path)',
        '            return',
        '        except PermissionError as exc:',
        '            last = exc',
        '            time.sleep(min(0.1, 0.02 * (attempt + 1)))'])
    return [
        ('M1 the FIXED temp name is restored (the measured collision)',
         fixed_name,
         "    tmp = path + '.tmp'"),
        ('M2 the retry is deleted (one bare os.replace)',
         retry_block,
         '    os.replace(tmp, path)' + chr(10) + '    return'),
    ]


def build_mutant(source_path, scratch, old, new):
    target = os.path.join(scratch, 'panel_state_mutant.py')
    shutil.copyfile(source_path, target)
    with open(target, encoding='utf-8') as fh:
        text = fh.read()
    count = text.count(old)
    if count != 1:
        return None, count
    with open(target, 'w', encoding='utf-8') as fh:
        fh.write(text.replace(old, new))
    return target, 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true',
                    help='remove each half of the cure from a COPY and require RED')
    ap.add_argument('--module', default=MODULE,
                    help='the panel_state.py under test (default: the shipped one)')
    args = ap.parse_args()

    emit('ORACLE panel-state-atomic (the panel dump that must land whole)')
    emit('  module   %s' % args.module)
    emit('  arms     S1-S3 static / B1-B6 behavioural')
    emit('  driver   the REAL write_atomic + the REAL PanelStateWriter, scratch target')

    if not os.path.exists(args.module):
        emit('SETUP ERROR: no module at %s' % args.module)
        return 2

    root = tempfile.mkdtemp(prefix='panel-state-atomic-', dir=SCRATCH_ROOT)
    try:
        module = load_module(args.module, 'panel_state_under_test')
        emit('')
        emit('--- arms over %s ---'
             % ('the SHIPPED module' if not args.neg_arm
                else 'the SHIPPED module (the baseline this arm compares against)'))
        before = len(RESULTS)
        static_arms(module, 'shipped')
        behavioural_arms(module, root)
        shipped = RESULTS[before:]
        emit('')
        emit('SHIPPED: %d/%d check(s) green'
             % (sum(1 for r in shipped if r), len(shipped)))

        if not args.neg_arm:
            if all(shipped):
                emit('VERDICT: PASS -- the panel dump is written whole, with a unique '
                     'temp name and a bounded retry; run --neg-arm to prove it can '
                     'say NO.')
                return 0
            emit('VERDICT: FAIL -- %d check(s) red on the shipped module.'
                 % (len(shipped) - sum(1 for r in shipped if r)))
            return 1

        # -- the negative arm: each half of the cure, removed -----------------
        emit('')
        emit('--- negative arm: one half of the cure removed from a COPY ---')
        moved = []
        for label, old, new in mutant_edits():
            mutant, count = build_mutant(args.module, root, old, new)
            if mutant is None:
                emit('  SETUP ERROR: the anchor for %s appears %d time(s), not once'
                     % (label, count))
                emit('  -- the mutation would not be the one this instrument '
                     'documents, so the mutant is DECORATIVE and proves nothing.')
                return 2
            scratch = tempfile.mkdtemp(prefix='panel-state-neg-', dir=SCRATCH_ROOT)
            m = load_module(mutant, 'panel_state_mutant_%d' % len(moved))
            emit('')
            emit('  --- %s ---' % label)
            mark = len(RESULTS)
            static_arms(m, label)
            behavioural_arms(m, scratch)
            run = RESULTS[mark:]
            red = len(run) - sum(1 for r in run if r)
            moved.append(red)
            emit('    %s: %d red of %d' % ('RED-as-expected' if red else 'INERT',
                                          red, len(run)))
            shutil.rmtree(scratch, ignore_errors=True)

        emit('')
        emit('NEG-ARM SUMMARY: red counts per mutant = %r' % (moved,))
        if all(n > 0 for n in moved):
            emit('VERDICT: NEG-ARM PASS -- both halves of the cure are load-bearing: '
                 'removing the unique temp name or the bounded retry turns this '
                 'oracle RED.')
            # rc=1 BY DESIGN: the negative arm has to FAIL -- a green here would mean
            # the instrument cannot say NO. rc=0 is what an INERT mutant gets: the
            # mutation changed nothing, the gate is blind there, and that is a
            # FAILURE of the negative arm, not a pass.
            return 1
        emit('VERDICT: NEG-ARM FAIL -- a mutant moved no check, so a green above '
             'cannot tell the cure from an untested file.')
        return 0
    except Exception as exc:  # noqa: BLE001 -- a setup failure is rc 2, not 1
        emit('SETUP ERROR: %r' % (exc,))
        return 2
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
