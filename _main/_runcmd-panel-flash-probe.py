"""WHEN does the panel's window go VISIBLE during a normal detached start?

Hit by `_main/run-cmd-exit-oracle.py` while gating `run.cmd`: in one pass its
own census recorded 1 of 219 samples with a VISIBLE top-level window
(`pid=<app> hwnd=... title='Sotto' class='WindowsForms10.Window.8.app...'`),
while the house census driver, run around the SAME pass, printed
`visible_samples_over_tree=0` -- because the app is `start`-detached and its
parent cmd.exe is gone, so a walk of the LIVE process table cannot reach it.
This probe keeps the app pid (taken from the app's OWN log line) and measures
the phase, which the one-line census hit cannot: startup, teardown, or both.

    py -3 _main/_runcmd-panel-flash-probe.py [--runs 4] [--exit-after 8]

READ-ONLY: it starts the app the way the owner does, samples, and lets the app
end by itself (`--exit-after`); it kills only the pid the app published about
itself, and only if that pid is still there at the end.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOTTO = os.path.dirname(HERE)
RUN_CMD = os.path.join(SOTTO, 'app', 'webview', 'run.cmd')
CENSUS = os.path.join(HERE, '_armE-window-census.py')
CREATE_NO_WINDOW = 0x08000000
READY_RE = re.compile(r'shell=webview2[^\n]*?\bpid=(\d+)')
EXIT_RE = re.compile(r'SHELL_EXIT')


def primitives():
    spec = importlib.util.spec_from_file_location('_sotto_census', CENSUS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=4)
    ap.add_argument('--exit-after', type=float, default=8.0)
    ap.add_argument('--cadence-ms', type=int, default=50)
    ap.add_argument('--direct', action='store_true',
                    help='start pythonw on sotto_webview.py DIRECTLY, with no '
                         'run.cmd in the path: the control that says whether a '
                         'flash belongs to the WRAPPER or to the app itself')
    a = ap.parse_args()
    pr = primitives()
    pyw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    shell = os.path.join(SOTTO, 'app', 'webview', 'sotto_webview.py')
    log = os.path.join(HERE, '_runcmd-panel-flash.log')
    for run in range(1, a.runs + 1):
        before = os.path.getsize(log) if os.path.exists(log) else 0
        argv = ([pyw, shell] if a.direct
                else ['cmd', '/c', RUN_CMD])
        argv += ['--log', log, '--no-hotkey', '--no-hot-reload',
                 '--exit-after', str(a.exit_after)]
        if a.direct:
            # No wrapper in the path: Popen, because there is no `start` to
            # detach for us and the app must keep running while we sample.
            subprocess.Popen(argv, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             creationflags=CREATE_NO_WINDOW,
                             cwd=os.path.dirname(RUN_CMD))
        else:
            subprocess.run(argv, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           creationflags=CREATE_NO_WINDOW,
                           cwd=os.path.dirname(RUN_CMD))
        t0 = time.time()
        tracked, ready_at, exit_at, hits = {os.getpid()}, None, None, []
        deadline = t0 + a.exit_after + 15.0
        while time.time() < deadline:
            txt = ''
            if os.path.exists(log):
                with open(log, 'rb') as f:
                    f.seek(before)
                    txt = f.read().decode('utf-8', 'replace')
            if ready_at is None:
                m = READY_RE.search(txt)
                if m:
                    ready_at = time.time()
                    tracked.add(int(m.group(1)))
            if exit_at is None and EXIT_RE.search(txt):
                exit_at = time.time()
            tracked |= pr.tree(os.getpid())
            wins = [w for w in pr.visible_windows() if w[0] in tracked]
            for pid, hwnd, title, cls in wins:
                hits.append({'t': time.time() - t0, 'pid': pid, 'hwnd': hwnd,
                             'title': title, 'class': cls,
                             'rel_ready': (None if ready_at is None
                                           else time.time() - ready_at),
                             'exit_seen': exit_at is not None})
            if exit_at is not None and time.time() - exit_at > 1.0:
                break
            time.sleep(a.cadence_ms / 1000.0)
        for h in hits:
            phase = ('teardown' if h['exit_seen'] else
                     ('startup' if h['rel_ready'] is not None else 'before-ready'))
            print(f"FLASH run={run} phase={phase} t={h['t']:.2f}s "
                  f"rel_ready={h['rel_ready'] if h['rel_ready'] is None else round(h['rel_ready'], 2)}s "
                  f"exit_seen={h['exit_seen']} pid={h['pid']} hwnd={h['hwnd']} "
                  f"title={h['title']!r} class={h['class']!r}", flush=True)
        print(f'RUN {run} flash_samples={len(hits)} ready={"yes" if ready_at else "no"} '
              f'exit={"yes" if exit_at else "no"}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
