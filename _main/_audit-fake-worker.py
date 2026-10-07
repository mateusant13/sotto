#!/usr/bin/env python3
"""A fake worker for `_main/_audit-probe-20261007.py` — the audit only.

It writes ONLY the two line shapes the REAL worker writes (`worker/sotto_worker.py`
`_event()` → `{"type":"caption","text":...,"start":...,"end":...,"final":bool}`
and `{"type":"status","state":...}`), one JSON object per line on stdout, so the
shell's own `_consume()` path handles it unchanged. Nothing here is a shell-side
stand-in and no audio device is opened: it exists so the panel can be photographed
in its POPULATED state (committed line + provisional tail) without loading a 1 GB
model or touching the sound card.

The stream is a synthesised one, and that is disclosed wherever its output is
cited: it is shaped like the real one (a growing partial, then the `final:true`
line the second pass closes), not captured from a real run.
"""

import json
import sys
import time

DEVICE = 'Audit Fake Endpoint'


def emit(obj):
    sys.stdout.write(json.dumps(obj) + '\n')
    sys.stdout.flush()


def main():
    emit({'type': 'status', 'state': 'model-loading'})
    time.sleep(0.4)
    emit({'type': 'status', 'state': 'model-loaded'})
    time.sleep(0.4)
    emit({'type': 'status', 'state': 'capture-started',
          'device': DEVICE, 'api': 'MME'})
    time.sleep(0.8)

    # The LIVE channel: the growing line, `final:false` (the worker still holds it).
    emit({'type': 'caption', 'text': 'o rato roeu', 'start': 0.0, 'end': 1.2,
          'final': False})
    time.sleep(0.5)
    emit({'type': 'caption', 'text': 'o rato roeu a rolha', 'start': 0.0,
          'end': 2.4, 'final': False})
    time.sleep(0.5)

    # The TRANSCRIPT channel: the worker CLOSED this line, so it carries the
    # second pass' text with `final:true`. This is the line the history feed is
    # reserved for.
    emit({'type': 'caption',
          'text': 'O rato roeu a rolha da garrafa do rei da Russia.',
          'start': 0.0, 'end': 4.0, 'final': True})
    time.sleep(0.4)
    emit({'type': 'status', 'state': 'done', 'verdict': 'captions-emitted',
          'captions': 2})
    time.sleep(0.5)

    # A provisional tail that is NEVER closed, so the panel is photographed with
    # the unstable line on screen too (dashed rail, italic, dimmed).
    emit({'type': 'caption', 'text': 'a prova dos nove', 'start': 5.0, 'end': 6.4,
          'final': False})

    # Stay up quietly past the probe's capture window.
    time.sleep(120.0)


if __name__ == '__main__':
    main()
