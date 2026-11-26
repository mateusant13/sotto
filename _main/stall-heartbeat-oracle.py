# NO-BUG: observability: measures whether the heartbeat tells a machine stall from the shell's own GIL -- the line carries n/t/m, a planted hole is found while a clean minute stays clean, garbage and missing/empty files are never called clean, a file with a hole reads back, the child ticks at 1 Hz and dies with its pipe, the first tick is immediate and the shell starts it first with stdin; no ledger id
"""The heartbeat can tell a machine stall from the shell's own GIL — or it cannot.

The instrument is `app/webview/stall_heartbeat.py`: a separate process writing one
line a second to its own file. This oracle is what makes that file trustworthy.

WHAT IT REFUSES TO ACCEPT
  * a reader that reports "no holes" for a file it could not read — absence is
    `no-heartbeat`, never clean;
  * a hole scanner that is asked to find a planted hole and does not;
  * a tick that is not 1 Hz-ish, or a counter that stops counting;
  * a child that survives its parent's pipe (an orphan heartbeat would outlive
    the app and quiet every future session with a stale file).

Usage:
    python _main/stall-heartbeat-oracle.py            # positive arms, rc 0 = PASS
    python _main/stall-heartbeat-oracle.py --neg-arm   # 7 mutants must die, rc 1
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODULE = os.path.join(ROOT, 'app', 'webview', 'stall_heartbeat.py')

sys.dont_write_bytecode = True


def _load(path, name='stall_heartbeat'):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _arm(name, ok, detail=''):
    print('  %-38s %s  %s' % (name, 'ok' if ok else 'FAIL', detail))
    return (name, bool(ok), detail)


def _spawn(mod_path, path):
    """Start the real child the way the shell does: stdin PIPE, hidden."""
    flags = 0x08000000 if os.name == 'nt' else 0     # CREATE_NO_WINDOW
    si = None
    if os.name == 'nt':
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
    return subprocess.Popen([sys.executable, '-u', mod_path, '--path', path],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=flags,
                            startupinfo=si)


def arms(mod=None, mod_path=MODULE):
    out = []
    mod = mod or _load(mod_path)

    # H1 — the line carries the three fields the reader depends on.
    line = mod.record(7, 1795682543.693, 12345.678)
    row = __import__('json').loads(line)
    out.append(_arm('h1-line-has-n-t-m', set(row) == set(mod.KEYS) and row['n'] == 7
                    and abs(row['t'] - 1795682543.693) < 0.002, line))

    # H2 — A PLANTED HOLE IS FOUND. This is the arm the whole file exists for.
    rows = [{'n': i, 't': 1000.0 + i, 'm': i} for i in range(10)]
    rows += [{'n': 17, 't': 1016.0, 'm': 16}]        # 7 s hole after n=9
    holes = mod.scan(rows, gap_s=2.5)
    out.append(_arm('h2-planted-hole-is-found',
                    len(holes) == 1 and abs(holes[0]['gap_s'] - 7.0) < 0.01
                    and holes[0]['n0'] == 9 and holes[0]['n1'] == 17,
                    str(holes[:1])))

    # H3 — and a clean minute is clean (a scanner that always shouts is useless).
    clean = [{'n': i, 't': 2000.0 + i, 'm': i} for i in range(60)]
    out.append(_arm('h3-clean-minute-is-clean', mod.scan(clean, 2.5) == [], 'ok'))

    # H4 — garbage rows cannot blind the reader.
    dirty = [{'n': 1, 't': 3000.0}, 'x', {}, {'n': 4, 't': 'zz'},
             {'n': 5, 't': 3001.0}]
    out.append(_arm('h4-garbage-rows-skipped', mod.scan(dirty, 2.5) == [], 'ok'))

    # H5 — a file that does not exist is NO-HEARTBEAT, never "clean".
    tmp = tempfile.mkdtemp(prefix='hb-oracle-')
    try:
        missing = os.path.join(tmp, 'nope.log')
        holes, span = mod.tail_gaps(missing)
        out.append(_arm('h5-missing-file-is-not-clean',
                        holes == [] and span is None, 'span=None'))

        # H6 — the file path, end to end: write rows with a hole, read it back.
        p = os.path.join(tmp, 'hb.log')
        with open(p, 'w', encoding='utf-8', newline='\n') as fh:
            for i, t in enumerate([5000.0, 5001.0, 5002.0, 5030.0, 5031.0]):
                fh.write(mod.record(i, t, float(i)) + '\n')
        holes, span = mod.tail_gaps(p)
        out.append(_arm('h6-file-with-hole-read-back',
                        len(holes) == 1 and abs(holes[0]['gap_s'] - 28.0) < 0.01
                        and span is not None and span[2] == 5, str(holes[:1])))

        # H7 — the REAL child: ~1 Hz, counter counts, and it dies with its pipe.
        live = os.path.join(tmp, 'live.log')
        child = _spawn(mod_path, live)
        time.sleep(5.2)
        child.stdin.close()
        t0 = time.time()
        try:
            rc = child.wait(timeout=6.0)
        except subprocess.TimeoutExpired:
            child.kill()
            rc = None
        gone_s = time.time() - t0
        holes2, span2 = mod.tail_gaps(live)
        n_rows = span2[2] if span2 else 0
        nums = []
        try:
            with open(live, encoding='utf-8') as fh:
                nums = [__import__('json').loads(x)['n'] for x in fh if x.strip()]
        except OSError:
            pass
        out.append(_arm('h7-child-ticks-1hz-and-dies-with-pipe',
                        4 <= n_rows <= 9 and not holes2 and gone_s < 2.5
                        and rc == 0 and nums == list(range(1, len(nums) + 1)),
                        'rows=%d holes=%d gone_s=%.2f rc=%s' %
                        (n_rows, len(holes2), gone_s, rc)))

        # H8 — an empty file says so too (absence has one name, not two).
        empty = os.path.join(tmp, 'empty.log')
        open(empty, 'w').close()
        holes3, span3 = mod.tail_gaps(empty)
        out.append(_arm('h8-empty-file-is-not-clean',
                        holes3 == [] and span3 is None, 'span=None'))
        # H10 — THE FIRST TICK EXISTS ALMOST IMMEDIATELY. MEASURED 2026-11-26:
        # a zero-byte heartbeat file appeared with no child behind it, and a
        # clock file that exists and says nothing is worse than no file.
        fast = os.path.join(tmp, 'fast.log')
        c2 = _spawn(mod_path, fast)
        time.sleep(0.6)
        got = 0
        try:
            with open(fast, encoding='utf-8') as fh:
                got = len([x for x in fh if x.strip()])
        except OSError:
            got = -1
        try:
            c2.stdin.close()
        except Exception:                 # noqa: BLE001
            pass
        try:
            c2.wait(timeout=6.0)
        except subprocess.TimeoutExpired:
            c2.kill()
        out.append(_arm('h10-first-tick-arrives-at-once', got >= 1, 'lines=%d' % got))

        # H9 — THE SHELL ACTUALLY STARTS IT, FIRST, AND OWNS ITS STDIN. An
        # instrument nobody launches is not an instrument; a heartbeat started
        # after the worker would miss exactly the startup stall it exists for.
        ok9, why9 = shell_wiring()
        out.append(_arm('h9-shell-starts-it-first-with-stdin', ok9, why9))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')


def shell_wiring(text=None):
    """The heartbeat is the FIRST step of the ordered pipeline and owns its pipe."""
    if text is None:
        with open(SHELL, 'r', encoding='utf-8', errors='replace', newline='') as fh:
            text = fh.read()
    i = text.find('def _start_stall_heartbeat(self):')
    if i < 0:
        return False, 'the launcher is gone'
    j = text.find('\r\ndef ', i)
    if j < 0:
        j = text.find('\ndef ', i)
    body = text[i:j if j > 0 else len(text)]
    pipe = 'stdin=subprocess.PIPE' in body
    spawned = ("'--path', self.STALL_HEARTBEAT_LOG" in body
               and "'--parent-pid', str(os.getpid())" in body)
    logged = 'STALL_HEARTBEAT pid=%d path=%s' in body
    k = text.find('steps = (')
    order = text[k:k + 300] if k > 0 else ''
    hb, cdp = order.find("('heartbeat'"), order.find("('cdp'")
    first = 0 <= hb < cdp
    return (pipe and spawned and logged and first,
            'first=%s stdin_pipe=%s spawned=%s logged=%s' % (first, pipe, spawned, logged))


def run(mod=None, label='live', mod_path=MODULE):
    rows = arms(mod, mod_path)
    bad = [r for r in rows if not r[1]]
    print('ARM-SUMMARY %s arms=%d ok=%d fail=%d'
          % (label, len(rows), len(rows) - len(bad), len(bad)))
    return rows, bad


#: Mutantes do TEXTO da shell: o h9 le a ordem e o lancamento, e so' vale se um
#: mutante do texto o derrubar.
SHELL_MUTANTS = [
    ('heartbeat-step-last',
     "        steps = (\r\n            ('heartbeat', _hb_step),\r\n            ('cdp', _cdp_step),",
     "        steps = (\r\n            ('cdp', _cdp_step),\r\n            ('heartbeat', _hb_step),"),
    ('heartbeat-does-not-own-stdin',
     "                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,",
     "                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,"),
    ('no-parent-pid-ownership', "'--parent-pid', str(os.getpid())", "'--x', '0'"),
    ('heartbeat-not-spawned',
     "'--path', self.STALL_HEARTBEAT_LOG", "'--nope', self.STALL_HEARTBEAT_LOG"),
]


MUTANTS = [
    # The scanner must report, and the planted hole is the arm that says so.
    ('hole-never-reported', 'if gap > gap_s:', 'if False:'),
    ('gap-threshold-ignored', 'GAP_S = 2.5', 'GAP_S = 1e9'),
    # The line must carry wall time and the tick number.
    ("record-loses-wall-time", "'t': round(float(wall_s), 3)", "'t': 0.0"),
    ("record-loses-monotonic", "KEYS = ('n', 't', 'm')", "KEYS = ('n', 't')"),
    # The child must tick at 1 Hz and must die with the pipe.
    ('tick-is-a-busy-loop', 'TICK_S = 1.0', 'TICK_S = 0.0'),
    ('counter-does-not-count', 'n += 1', 'n += 0'),
    ('child-outlives-the-pipe', '    stop.set()', '    pass'),
    ('child-never-ticks', 'while not stop.is_set():\n            stop.wait(max(0.05, tick))',
     'while False:\n            stop.wait(max(0.05, tick))'),
]


def neg_arm():
    caught = total = 0
    tmp = tempfile.mkdtemp(prefix='hb-neg-')
    try:
        src = open(MODULE, 'r', encoding='utf-8', newline='').read()
        for name, old, new in MUTANTS:
            total += 1
            if old not in src:
                print('  %-38s MUTANT-BROKEN (anchor missing)' % name)
                continue
            copy = os.path.join(tmp, 'm_%d.py' % total)
            with open(copy, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(src.replace(old, new, 1))
            try:
                mod = _load(copy, 'stall_heartbeat_mut_%d' % total)
                _, bad = run(mod, label='mutant:%s' % name, mod_path=copy)
            except Exception as exc:        # noqa: BLE001
                print('  %-38s MUTANT-BROKEN (%r)' % (name, exc))
                continue
            if bad:
                caught += 1
            else:
                print('  %-38s SURVIVED -- the gate is blind here' % name)
        for name, old, new in SHELL_MUTANTS:
            total += 1
            live = open(SHELL, 'r', encoding='utf-8', errors='replace', newline='').read()
            if old not in live:
                print('  %-38s MUTANT-BROKEN (anchor missing)' % name)
                continue
            ok, _why = shell_wiring(live.replace(old, new, 1))
            if ok:
                print('  %-38s SURVIVED -- the gate is blind here' % name)
            else:
                caught += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('NEG-ARM %d/%d CAUGHT' % (caught, total))
    if caught == total:
        print('NEG-ARM VERDICT: PASS')
    return 1 if caught == total else 0


def main(argv):
    if '--neg-arm' in argv:
        code = neg_arm()
        print('VERDICT: %s' % ('CAUGHT' if code == 1 else 'BLIND'))
    else:
        _, bad = run()
        code = 1 if bad else 0
        print('VERDICT: %s' % ('PASS' if code == 0 else 'RED'))
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
