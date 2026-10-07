#!/usr/bin/env python3
"""The NEGATIVE ARM for lane/cap2panel: a worker that behaves like one and
NEVER emits a caption.

A gate that cannot say NO is useless. The delivery arm proves a caption can
reach the panel; this arm proves the measurement is not simply always-true.
It is the same shell, the same panel, the same JSONL channel, the same wait --
the ONLY difference is that this process prints a `status` and then goes quiet.

It deliberately prints the `status` line, so the panel DOES leave "Starting the
worker" exactly as in the delivery arm. If the delivery measurement were an
artefact of the panel merely being up, this arm would pass the same check and
the gate would go RED.
"""
from __future__ import annotations

import json
import os
import sys
import time

SECS = float(os.environ.get('SOTTO_SILENT_SECS', '90'))


def main() -> int:
    sys.stdout.write(json.dumps({
        'type': 'status', 'state': 'capture-started',
        'detail': 'negative arm: a worker that never emits a caption'}) + '\n')
    sys.stdout.flush()
    deadline = time.time() + SECS
    while time.time() < deadline:
        time.sleep(0.25)
    return 0


if __name__ == '__main__':
    sys.exit(main())