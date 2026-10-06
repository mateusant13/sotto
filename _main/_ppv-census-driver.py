"""Drive the HOUSE window census at THIS probe's cadence, for THIS probe's run.

Enumerates NOTHING itself. It shells the same instrument the governor runs
(`I:/!manager/scripts/window-census.ps1`, which counts handles that went from
absent to present and stay present), with its own `-Log`/`-Estado` so the
shared state file is not disturbed, and prints one receipt per tick.

    py -3 _main/_ppv-census-driver.py bootstrap        # snapshot BEFORE the run
    py -3 _main/_ppv-census-driver.py sample <secs>    # N ticks, one per 15 s

A PowerShell child is spawned with CREATE_NO_WINDOW ALONE (AGENTS.md). The
DETACHED_PROCESS trap is explicitly NOT used: detached, that same child returns
an EMPTY channel with rc 0, and an empty channel is NOT a zero -- a tick whose
output is empty is reported as CEGO, never as "clean".
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

CREATE_NO_WINDOW = 0x08000000
PS = 'powershell.exe'
CENSUS = 'I:/!manager/scripts/window-census.ps1'
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   '_ppv-window-census.log')
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '_ppv-window-census-state.json')
CADENCE_S = 15.0


def tick(tag: str) -> str:
    t0 = time.time()
    proc = subprocess.run(
        [PS, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
         '-File', CENSUS, '-Log', LOG, '-Estado', STATE],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW, timeout=90)
    out = proc.stdout.decode('utf-8', 'replace').strip()
    head = f'[{tag}] rc={proc.returncode} ms={int((time.time() - t0) * 1000)}'
    if not out:
        # Never read an empty channel as a zero.
        print(f'{head} CEGO - the census returned an EMPTY channel; that is '
              f'not a clean census')
        return ''
    print(f'{head}\n{out}')
    return out


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'sample'
    if mode == 'bootstrap':
        tick('bootstrap')
        print(f'state file: {STATE}')
        return 0
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    for i in range(n):
        tick(f'sample-{i + 1:02d}')
        if i != n - 1:
            time.sleep(CADENCE_S)
    return 0


if __name__ == '__main__':
    sys.exit(main())
