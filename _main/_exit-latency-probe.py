"""MEASURE THE EXIT, to the millisecond: the tray thread and the process.

The owner, 2026-10-21: *"os travamentos que acontecem quando fechamos o
sotto"*. The exit path has two clocks that the log does not show:

  * the SHELL's OWN exit sequence (BRIDGE_STOP -> SHELL_EXIT): the log's
    timestamps do show it, and the destroy wait is what was three seconds.
  * the PROCESS's actual death: after `SHELL_EXIT` the process still has to
    go. This waits on the process handle, so the number is exact.

Launches its own shell (a MEASUREMENT launch: `--no-hotkey`, an explicit
`--mutex-name` so it coexists with the owner's app, and its OWN log). The
owner's app is NOT touched.

    python _main/_exit-latency-probe.py [--with-worker] [--hold 25]
"""
import argparse
import ctypes
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')
LOG = os.path.join(HERE, 'exit-probe.log')
STAMP = re.compile(r'^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}\.\d{3}) sotto: (.*)$')

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.WaitForSingleObject.restype = ctypes.c_uint
k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102


def log_events(path):
    out = []
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            m = STAMP.match(raw.rstrip('\n'))
            if m:
                out.append((m.group(2), m.group(3)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--with-worker', action='store_true',
                    help='start the worker too, so the exit kills a live child')
    ap.add_argument('--hold', type=float, default=20.0,
                    help='seconds before the shell asks to exit')
    args = ap.parse_args()

    log_path = LOG + '.%d' % int(time.time())
    cmd = [sys.executable, SHELL, '--exit-after', str(args.hold),
           '--no-hotkey', '--mutex-name', r'Local\SottoShell.m.exitlatency',
           '--log', log_path]
    if args.with_worker:
        cmd.append('--with-worker')
    # pythonw: no console window, ever.
    pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    cmd[0] = pythonw if os.path.exists(pythonw) else sys.executable

    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=REPO, creationflags=flags)
    print('probe pid=%d  hold=%ss  worker=%s'
          % (proc.pid, args.hold, args.with_worker))

    handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, proc.pid)
    death = None
    limit = int((args.hold + 90) * 1000)
    waited = k32.WaitForSingleObject(handle, limit)
    if waited == WAIT_OBJECT_0:
        death = time.time() - t0
    else:
        print('TIMEOUT waiting for the process')
        proc.kill()
    proc.wait(timeout=30)

    evs = log_events(log_path)
    print()
    print('%-14s %s' % ('CLOCK', 'EVENT'))
    for clock, msg in evs:
        if any(k in msg for k in ('SHELL_STARTUP_STAGE', 'BRIDGE_START',
                                  'BRIDGE_SPAWNED', 'BRIDGE_LOAD_MS',
                                  'BRIDGE_STOP', 'SHELL_CLOSING',
                                  'VRAM_GUARD stopped', 'SHELL_EXIT')):
            print('%-14s %s' % (clock, msg[:120]))
    if evs:
        def at(name):
            for clock, msg in evs:
                if name in msg:
                    return clock
            return None
        stop, closing, exit_ = at('BRIDGE_STOP'), at('SHELL_CLOSING'), at('SHELL_EXIT')
        def delta(a, b):
            if not a or not b:
                return None
            # seconds since midnight, parsed by hand: `time.mktime` on a bare
            # clock string assumes 1900 and raises on Windows.
            def secs(clock):
                h, m, s = clock.split(':')
                return int(h) * 3600 + int(m) * 60 + float(s)
            return secs(b) - secs(a)
        print()
        print('BRIDGE_STOP -> SHELL_CLOSING : %s s'
              % ('%.3f' % delta(stop, closing) if delta(stop, closing) is not None else '?'))
        print('SHELL_CLOSING -> SHELL_EXIT   : %s s'
              % ('%.3f' % delta(closing, exit_) if delta(closing, exit_) is not None else '?'))
        print('BRIDGE_STOP -> SHELL_EXIT     : %s s'
              % ('%.3f' % delta(stop, exit_) if delta(stop, exit_) is not None else '?'))
    if death is not None:
        print('PROCESS DEATH (from the spawn) : %.3f s' % death)
    print('ORPHAN CHECK: a worker still alive?')
    ps = ('Get-CimInstance Win32_Process | Where-Object { '
          '$_.CommandLine -like \'*sotto_worker.py*\' -and '
          '$_.Name -eq \'python.exe\' } | '
          'ForEach-Object { $_.ProcessId }')
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                         capture_output=True, text=True)
    pids = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    print('  %s' % ('NONE' if not pids else 'pids: ' + ', '.join(pids)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
