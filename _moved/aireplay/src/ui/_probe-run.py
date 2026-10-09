#!/usr/bin/env python3
"""SCRATCH runner: launch one hud-shell variant, poll for exit, print its log.

Launched with pythonw.exe (GUI subsystem, no console) so a measurement run can
never put a console window on the owner's desk. `--exit-after` is the shell's own
failsafe; this adds a HARD kill so a hung variant cannot outlive the probe.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

PYTHONW = os.path.join(sys.prefix, 'pythonw.exe')
CREATE_NO_WINDOW = 0x08000000


def run(script: str, log: str, secs: float, extra: list) -> dict:
    for p in (log,):
        if os.path.exists(p):
            os.remove(p)
    script = os.path.abspath(script)
    # GEOMETRY IS LEFT ALONE ON PURPOSE. Parking the window off-screen
    # (x=-10000) is the fix the house FORBIDS: the sibling shell measured that
    # WebView2 never completes the navigation for a window created off-screen,
    # so `_on_loaded` never fires. Measured here too — every off-screen launch of
    # this shell ends `panel_loaded=false` after 16-30 s.
    log = os.path.abspath(log)  # cwd below is the script's dir, so a relative
    # --log would land in the wrong tree and the run would look "silent"
    args = [script, '--exit-after', str(secs), '--log', log] + extra
    t0 = time.perf_counter()
    proc = subprocess.Popen([PYTHONW] + args, creationflags=CREATE_NO_WINDOW,
                            cwd=os.path.dirname(os.path.abspath(script)))
    killed = False
    while proc.poll() is None and time.perf_counter() - t0 < secs + 20:
        time.sleep(0.2)
    if proc.poll() is None:
        proc.kill()
        killed = True
    text = ''
    if os.path.exists(log):
        with open(log, encoding='utf-8', errors='replace') as f:
            text = f.read()
    return {'rc': proc.returncode, 'killed': killed,
            'wall_s': round(time.perf_counter() - t0, 2), 'log': text}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('script')
    ap.add_argument('--log', required=True)
    ap.add_argument('--secs', type=float, default=20.0)
    # The shell's own flags (`--no-gate`, `--opaque`, …) are passed straight
    # through, so this parser must not treat them as its own options.
    a, extra = ap.parse_known_args()
    r = run(a.script, a.log, a.secs, list(extra))
    print(f"--- rc={r['rc']} killed={r['killed']} wall={r['wall_s']}s "
          f"args={' '.join(extra)}")
    print(r['log'])
    loaded = 'HUD_LOADED' in r['log']
    print(f"LOADED={loaded}")
    return 0 if loaded else 2


if __name__ == '__main__':
    sys.exit(main())