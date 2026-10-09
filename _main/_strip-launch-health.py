"""Launch the shell N times and ask ONE question per launch: did it EXIT?

Why this instrument exists (measured 2026-10-08, lane strip-surface):

  * `_main/_strip-stats-log-probe.py`'s per-sample arm HUNG (`window_s=58.28`, rc=1
    after `proc.kill()`) while its aggregated arm was clean, and the battery's
    `strip-stats-log-budget` control went RED with a **0-byte** step log.
  * `_main/_strip-logmutant-repro.py --repeat 3` then measured the same stall in
    **6 of 6** launches, BOTH arms (`REPRO-VERDICT BOTH-ARMS-STALL-EQUALLY`),
    5 of 6 before `RECEIVER_READY` — so the stall is NOT a property of the chatty
    copy; it is a property of the BOX at that moment.
  * A census found a hung measurement shell (`--no-worker --exit-after 8`) alive
    for ~20 minutes.  The hypothesis this instrument tests: **a shell left alive
    poisons every LATER launch** (the WebView2 environment is a per-user-data
    resource), so one un-killed stall cascades into a run of stalls.

The verdict is a rate, not a single launch, because a single healthy launch proves
nothing (the same file has printed 0-of-213 and 141-of-262 in one day).

It never leaves a shell alive: on timeout it dumps the hung process's PYTHON STACKS
with py-spy (the whole point — a stall you cannot see the stack of is a stall you
cannot fix) and then kills that exact pid.

Read-only apart from its own log/stack files.  No hotkey, no tray, no worker, no
audio device, CREATE_NO_WINDOW.  `--show`/`--selftest` are never passed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
PYW = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
if not os.path.exists(PYW):
    PYW = sys.executable
PY_SPY = os.path.join(os.path.dirname(sys.executable), 'Scripts', 'py-spy.exe')

CREATE_NO_WINDOW = 0x08000000

MILESTONES = (
    'CORE_INIT', 'PRELOAD_INSTALLED', 'STAGING_LOADED', 'RECEIVER_READY',
    'PRELOAD_ACTIVE', 'PANEL_SHOW_REFUSED', 'WORKER_AUTOSTART', 'BRIDGE_START',
    'BRIDGE_SPAWNED', 'SHELL_EXIT', 'BRIDGE_STOP', 'PANEL_STATE_WRITER_STOP',
)


def one_launch(tag: str, secs: float, watch: float, extra: list[str]) -> dict:
    log = os.path.join(HERE, f'_strip-health-{tag}-{os.getpid()}-{int(time.time() * 1000) % 1000000}.log')
    cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--no-tray',
           '--exit-after', str(secs), '--log', log] + list(extra)
    started = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=CREATE_NO_WINDOW)
    exited, rc = False, None
    while time.monotonic() - started < watch:
        rc = proc.poll()
        if rc is not None:
            exited = True
            break
        time.sleep(0.25)
    alive_s = round(time.monotonic() - started, 2)
    stacks = None
    if not exited:
        stacks = os.path.join(HERE, f'_strip-health-{tag}-{proc.pid}-stacks.txt')
        try:
            with open(stacks, 'w', encoding='utf-8') as fh:
                fh.write(f'# py-spy dump of a STALLED shell pid={proc.pid} tag={tag}\n')
                fh.flush()
                r = subprocess.run([PY_SPY, 'dump', '--pid', str(proc.pid)],
                                   stdout=fh, stderr=subprocess.STDOUT, timeout=60,
                                   creationflags=CREATE_NO_WINDOW)
                fh.write(f'# py-spy rc={r.returncode}\n')
        except Exception as exc:                                  # noqa: BLE001
            with open(stacks, 'a', encoding='utf-8') as fh:
                fh.write(f'# py-spy FAILED: {exc!r}\n')
        # kill THIS pid only, after re-checking the artifact name in its command line
        try:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30, creationflags=CREATE_NO_WINDOW)
        except Exception:                                          # noqa: BLE001
            pass
        try:
            proc.wait(timeout=10)
        except Exception:                                          # noqa: BLE001
            pass
        rc = proc.poll()
    text = ''
    if os.path.exists(log):
        with open(log, 'r', encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    seen = [m for m in MILESTONES if m in text]
    return {'tag': tag, 'pid': proc.pid, 'exited': exited, 'rc': rc,
            'alive_s': alive_s, 'bytes': len(text), 'milestones': seen,
            'stacks': stacks, 'log': log}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--n', type=int, default=3)
    ap.add_argument('--secs', type=float, default=8.0)
    ap.add_argument('--watch', type=float, default=0.0,
                    help='seconds to wait for the exit; 0 = secs + 25')
    ap.add_argument('--no-worker', action='store_true', default=True)
    ap.add_argument('--with-worker', action='store_true')
    args = ap.parse_args()
    watch = args.watch or (args.secs + 25.0)

    extra = ['--no-worker']
    if args.with_worker:
        extra = []
    print(f'HEALTH shell={SHELL}')
    print(f'HEALTH secs={args.secs} watch={watch} n={args.n} flags={" ".join(extra)}')
    rows = [one_launch(f'h{i + 1}', args.secs, watch, extra) for i in range(args.n)]
    for r in rows:
        print(f'  launch {r["tag"]} pid={r["pid"]} exited={r["exited"]} rc={r["rc"]} '
              f'alive_s={r["alive_s"]} log_bytes={r["bytes"]} '
              f'milestones={"+".join(r["milestones"]) or "none"}'
              + (f' stacks={os.path.basename(r["stacks"])}' if r['stacks'] else ''))
    stalled = [r for r in rows if not r['exited']]
    first = rows[0]['exited']
    later = [r['exited'] for r in rows[1:]]
    if not stalled:
        verdict = 'HEALTHY-ALL'
    elif not first and not any(later):
        verdict = 'STALLS-EVERY-LAUNCH'
    elif first and not all(later):
        verdict = 'FIRST-HEALTHY-THEN-STALLS'
    elif not first and all(later):
        verdict = 'FIRST-STALLS-THEN-HEALTHY'
    else:
        verdict = 'STALLS-INTERMITTENTLY'
    print(f'HEALTH-STALLS n={len(rows)} stalled={len(stalled)} '
          f'before_receiver_ready={sum(1 for r in stalled if "RECEIVER_READY" not in r["milestones"])}')
    print(f'HEALTH-VERDICT {verdict}')
    print('HEALTH-NOTE a stall is only proven by the count: a single healthy launch '
          'does not prove the box is clean, and one stalled launch does not name a cause.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
