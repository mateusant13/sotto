"""Re-run the lane's OWN measurement path: the real app, the real worker, idle.

`_main/_live-launch.py` launches the app the owner's way (windowless: `run.cmd`
-> `pythonw`, and the worker via CREATE_NO_WINDOW), which is how the defect was
measured in `_main/_live_owner3.log`. This script does that, watches the log for
`seconds`, kills the tree, and prints the census of the shell's own lines -- so
the same numbers can be read AFTER the fix as were read BEFORE it.

  py -3 _main/_tap-restart-live-arm.py [log] [seconds]

Reported, all counted from the log:
  spawns            BRIDGE_SPAWNED lines (the panel's own count of worker starts)
  respawns          spawns - 1: the first start is the app starting, the rest
                    are the loop this lane is about
  silent_kills      BRIDGE_SILENT (the old, unconditional kill)
  silent_benign     BRIDGE_SILENT_BENIGN (verdict seen: named, not killed)
  no_audio_state    lines carrying state=no-audio
  no_audio_painted  the panel text the named state paints
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCH = os.path.join(HERE, '_live-launch.py')
SOTTO = os.path.dirname(HERE)


def count(text, needle):
    return text.count(needle)


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        HERE, '_tap-restart-live-after.log')
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 150.0
    if os.path.exists(log):
        os.remove(log)

    rc = subprocess.run([sys.executable, LAUNCH, log],
                        capture_output=True, text=True, errors='replace')
    print(f'  launch rc={rc.returncode} {(rc.stdout or "").strip()} '
          f'{(rc.stderr or "").strip()}')

    # The app is detached and meant to live for days; sample the log as it grows.
    last = ''
    t_end = time.time() + seconds
    while time.time() < t_end:
        time.sleep(5.0)
        try:
            with open(log, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        except FileNotFoundError:
            continue
        if text != last:
            last = text

    text = ''
    try:
        with open(log, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except FileNotFoundError:
        print(f'  no log at {log}: the app never started')
        return 1

    m = re.search(r'shell=webview2[^\n]*pid=(\d+)', text)
    app_pid = m.group(1) if m else None
    spawns = count(text, 'BRIDGE_SPAWNED')
    census = {
        'log': log,
        'app_pid': app_pid,
        'observed_s': seconds,
        'spawns': spawns,
        'respawns': max(0, spawns - 1),
        'silent_kills': count(text, 'BRIDGE_SILENT ms='),
        'silent_benign': count(text, 'BRIDGE_SILENT_BENIGN'),
        'no_audio_state': count(text, 'state=no-audio'),
        'no_audio_logged': count(text, 'BRIDGE_SILENT_BENIGN ms='),
        'no_audio_painted': count(text, 'title="No audio to transcribe"'),
        'device_rotated_flat': count(text, 'device-rotated (flat)'),
        'restart_silent': count(text, 'BRIDGE_RESTART reason=silent'),
        'restart_exit': count(text, 'BRIDGE_RESTART reason=exit'),
        'deaths': count(text, 'BRIDGE_DEATH'),
        'bytes': len(text),
    }
    for k, v in census.items():
        print(f'  {k:20s} {v}')

    if app_pid:
        killed = subprocess.run(['taskkill', '/PID', app_pid, '/T', '/F'],
                                capture_output=True, text=True, errors='replace')
        note = (killed.stdout or killed.stderr or '').strip()
        print(f'  taskkill rc={killed.returncode} {note}')
    else:
        print('  no app pid found in the log: nothing killed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
