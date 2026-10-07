#!/usr/bin/env python3
"""ARM E's fake worker for `_main/panel-exit3-oracle.py`.

It writes ONLY the two line shapes `worker/sotto_worker.py` writes -- a
`status` and a `caption`, one JSON object per line on stdout -- so the shell's
own `_consume` path handles it unchanged; nothing here is a shell-side
stand-in. Mode is chosen by `SOTTO_ARME_MODE`:

  hold     every run writes the silent-device death and exits 3, and no caption
           is EVER emitted. The DOM must show the HELD error.
  recover  run 1 writes the same death and exits 3; run 2 comes back, writes
           `model-loading` (held behind the death), then ONE real caption and
           goes quiet, so the page's own hold timer (`COMMIT_MAX_HOLD_MS`,
           panel.js) commits it. The DOM must show the LIVE state -- which since
           2026-10-08 is the footer's `status--live` class and an EMPTY
           `#status-text`, NOT the sentence 'Receiving captions' the owner had
           removed (*"tira o 'receiving captions'. deixa só um icone dinamico"*).
           The sentence is still pushed by the shell and acknowledged by the page;
           it is the PAINT that changed, so this mode's contract is the class.

It records its own run count in `_armE-worker-runs.txt` so run 1 and run 2 can
differ; the oracle deletes that file before each run.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, '_armE-worker-runs.txt')
MODE = os.environ.get('SOTTO_ARME_MODE', 'hold')
DEVICE = 'Mapeador de som da Microsoft - Input'


def emit(obj):
    sys.stdout.write(json.dumps(obj) + '\n')
    sys.stdout.flush()


def run_index():
    try:
        with open(RUNS, encoding='utf-8') as f:
            n = int((f.read().strip() or '0'))
    except (OSError, ValueError):
        n = 0
    n += 1
    with open(RUNS, 'w', encoding='utf-8') as f:
        f.write(str(n))
    return n


def die():
    # The worker's OWN exit-3 vocabulary, byte-for-byte the shapes the shell
    # classifies: a loud `silent-device` status, then the `done` it exits on.
    emit({'type': 'status', 'state': 'silent-device', 'verdict': 'silent-device',
          'device': DEVICE, 'api': 'MME', 'peak': 0.000122,
          'peak_floor': 0.002, 'blocks': 34, 'captions': 0,
          'detail': f'{DEVICE} [MME] opened and delivered 34 blocks but never '
                    'reached peak 0.002'})
    time.sleep(0.2)
    emit({'type': 'status', 'state': 'done', 'verdict': 'silent-device',
          'blocks': 34, 'peak': 0.000122, 'captions': 0, 'device': DEVICE,
          'device_outcome': 'all-flat'})
    sys.stdout.flush()
    sys.exit(3)


n = run_index()
die() if (MODE == 'hold' or n == 1) else None

# -- recovery: a worker that came back and really transcribed. ONE caption, then
#    silence, so the page's own hold timer commits the line (a caption every
#    second would keep re-arming the timer and it would never commit).
emit({'type': 'status', 'state': 'model-loading'})
time.sleep(3.0)
emit({'type': 'caption', 'text': 'ola mundo', 'start': 0.0, 'end': 1.5})
# Stay up quietly: the silence watchdog (15 s) outlives the dump.
time.sleep(120.0)
