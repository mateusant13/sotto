"""Does `os._exit(9)` terminate a process that has a thread blocked in a
blocking pipe read? And does `TerminateProcess(self)` do what `os._exit`
fails to do?

FOUR ARMS, each an INDEPENDENT child process (CREATE_NO_WINDOW, no window, no
audio, no second Sotto instance):

  arm=quiet        no blocked thread, `os._exit(9)`          -> expect exit 9
  arm=pipe-os      thread blocked in readline() on a live pipe,
                   then `os._exit(9)`                          -> HYPOTHESIS: does
                                                                  NOT exit
  arm=pipe-tp      same blocked thread, `TerminateProcess`    -> expect exit 9
                   on the CURRENT process
  arm=pipe-os-wait a bounded reap of the offender (close the pipe /
                   terminate it) BEFORE `os._exit(9)`          -> expect exit 9

The child announces itself in a JSONL file (`--out`) so the parent measures a
STATE (process alive?) and not an assumption. The blocked pipe's writer is a
grandchild that sleeps 600 s: a live writer is exactly the state the shell is
in when it exits while `sotto-worker-stdout`/`-stderr` pump threads sit in
`readline()` (sotto_webview.py:18140-18150 spawns one per stream).

Run: python _main/_deadexit-oracle.py [--arm NAME] [--out PATH] [--json]
Exit code of the runner: 0 when every arm settled as its arm predicts.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SELF = os.path.abspath(__file__)

#: How long the runner waits for a child that SAID it was exiting.
SETTLE_S = 8.0

CREATE_NO_WINDOW = 0x08000000


def _now():
    return time.strftime('%H:%M:%S.') + '%03d' % (int(time.time() * 1000) % 1000)


def _note(out, event, **fields):
    row = {'t': _now(), 'mono': round(time.monotonic(), 3), 'event': event}
    row.update(fields)
    with open(out, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(row) + '\n')


def _terminate_self(code):
    """The candidate primitive: TerminateProcess on our OWN process."""
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    k32.TerminateProcess(ctypes.c_void_p(k32.GetCurrentProcess()), int(code))


def _spawn_writer_that_never_writes():
    """A grandchild holding the write end open, saying nothing for 600 s."""
    code = ('import sys,time\n'
            'sys.stdout.write("")\n'
            'sys.stdout.flush()\n'
            'time.sleep(600)\n')
    return subprocess.Popen([sys.executable, '-c', code],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL,
                            creationflags=CREATE_NO_WINDOW,
                            startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))


def _child(arm, out):
    _note(out, 'child_start', arm=arm, pid=os.getpid())
    writer = None
    if arm in ('pipe-os', 'pipe-tp', 'pipe-os-wait'):
        writer = _spawn_writer_that_never_writes()
        _note(out, 'writer_spawned', pid=writer.pid)

        def _block():
            # exactly what `_pump` does: a blocking readline on the child's pipe
            try:
                writer.stdout.readline()
            except Exception:
                pass
            _note(out, 'reader_returned')

        threading.Thread(target=_block, name='pump-like', daemon=True).start()
        time.sleep(0.4)
        _note(out, 'reader_blocked', threads=threading.active_count())

    if arm == 'pipe-os-wait':
        # BOUNDED REAP: kill the writer, then close the pipe the reader sits on.
        # This is the "every blocking wait gets a bounded timeout" half.
        t0 = time.monotonic()
        writer.kill()
        try:
            writer.wait(timeout=2.0)
        except Exception:
            pass
        try:
            writer.stdout.close()
        except Exception:
            pass
        _note(out, 'reaped', pid=writer.pid, ms=round((time.monotonic() - t0) * 1000))

    _note(out, 'exiting', arm=arm)
    time.sleep(0.05)
    if arm == 'pipe-tp':
        _note(out, 'terminate_self', code=9)
        _terminate_self(9)
        time.sleep(5.0)          # unreachable if the primitive works
        _note(out, 'terminate_self_RETURNED')
        os._exit(9)
    _note(out, 'os_exit', code=9)
    os._exit(9)


def _read_events(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


def _run_arm(arm, root):
    out = os.path.join(root, 'arm-%s.jsonl' % arm)
    if os.path.exists(out):
        os.remove(out)
    proc = subprocess.Popen([sys.executable, SELF, '--arm', arm, '--out', out],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL,
                            creationflags=CREATE_NO_WINDOW,
                            startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    t0 = time.monotonic()
    exited_at = None
    rc = None
    while time.monotonic() - t0 < SETTLE_S:
        rc = proc.poll()
        if rc is not None:
            exited_at = round((time.monotonic() - t0) * 1000.0, 1)
            break
        time.sleep(0.05)
    alive = proc.poll() is None
    events = _read_events(out)
    stray = []
    for row in events:
        if row.get('event') == 'writer_spawned':
            # the grandchild must not outlive a correct exit
            stray.append(row['pid'])
    stray_alive = [pid for pid in stray if _pid_alive(pid)]
    result = {
        'arm': arm,
        'rc': rc,
        'alive_after_s': SETTLE_S if alive else exited_at,
        'settled': not alive,
        'events': [(e['t'], e['event']) for e in events],
        'stray_grandchildren_alive': stray_alive,
    }
    if alive:
        # kill ONLY the process this runner launched
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass
        result['killed_by_runner'] = True
    for pid in stray_alive:
        try:
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x0001, False, int(pid))  # PROCESS_TERMINATE
            if h:
                k32.TerminateProcess(h, 1)
                k32.CloseHandle(h)
        except Exception:
            pass
    return result


def _pid_alive(pid):
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    h = k32.OpenProcess(0x1000, False, int(pid))     # QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_uint(0)
    ok = k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
    k32.CloseHandle(ctypes.c_void_p(h))
    return bool(ok) and code.value == 259            # STILL_ACTIVE


#: What each arm MUST do for the theory to stand.
EXPECT = {
    'quiet': 'settled',
    'pipe-os': 'still-alive',        # EXIT DOES NOT COMPLETE
    'pipe-tp': 'settled',            # TerminateProcess(self) does the job
    'pipe-os-wait': 'settled',        # a bounded reap before exiting does too
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm')
    ap.add_argument('--out')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    if args.arm:
        _child(args.arm, args.out)
        return 0

    root = os.path.join(HERE, '_deadexit')
    os.makedirs(root, exist_ok=True)
    results = [_run_arm(arm, root) for arm in EXPECT]
    verdicts = []
    for r in results:
        observed = 'settled' if r['settled'] else 'still-alive'
        verdicts.append({'arm': r['arm'], 'expected': EXPECT[r['arm']],
                         'observed': observed,
                         'ok': observed == EXPECT[r['arm']]})
    ok = all(v['ok'] for v in verdicts)
    report = {'verdict': 'PASS' if ok else 'FAIL',
              'settle_s': SETTLE_S, 'arms': results, 'verdicts': verdicts}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for r in results:
            print('arm=%-13s rc=%-5s alive_after_s=%-6s events=%s' % (
                r['arm'], r['rc'], r['alive_after_s'],
                ' -> '.join('%s %s' % (t, e) for t, e in r['events'])))
        print('VERDICT %s' % report['verdict'])
        for v in verdicts:
            print('  %-13s expected=%-11s observed=%-11s %s'
                  % (v['arm'], v['expected'], v['observed'],
                     'ok' if v['ok'] else 'MISMATCH'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
